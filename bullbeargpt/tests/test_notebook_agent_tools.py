import importlib
import os

from app import create_app
from services.agent_tool_service import AgentToolService


def _reset_notebook_service():
    module = importlib.import_module("services.notebook_service")
    module._notebook_service = None
    return module


def test_list_recent_theses_builds_preview_and_excludes_current_session(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    service_module = _reset_notebook_service()
    service = service_module.get_notebook_service()

    session_a = service.create_session("NVDA", company_name="NVIDIA", user_id="user-1")
    session_b = service.create_session("NVDA", company_name="NVIDIA", user_id="user-1")
    session_c = service.create_session("NVDA", company_name="NVIDIA", user_id="user-1")

    dcf_snapshot = {
        "companyDTO": {
            "estimatedValuePerShare": 120.0,
            "price": 90.0,
        }
    }

    service.save_thesis(
        session_id=session_a.id,
        ticker="NVDA",
        company_name="NVIDIA",
        title="Old thesis",
        summary="Older summary",
        cells_snapshot=[],
        dcf_snapshot=dcf_snapshot,
        user_id="user-1",
    )
    service.save_thesis(
        session_id=session_b.id,
        ticker="NVDA",
        company_name="NVIDIA",
        title="New thesis",
        summary="Newer summary",
        cells_snapshot=[],
        dcf_snapshot=dcf_snapshot,
        user_id="user-1",
        preview_json={
            "title": "Structured thesis",
            "summary": "Structured summary",
            "conviction": "high",
            "key_assumptions": ["Revenue growth stays above 15%"],
            "risks": ["Margin compression"],
            "fair_value": 130.0,
            "current_price": 95.0,
            "upside": 36.8,
            "timeframe": "12m",
        },
    )

    recent = service.list_recent_theses_for_ticker(
        user_id="user-1",
        ticker="NVDA",
        limit=2,
        exclude_session_id=session_c.id,
    )

    assert len(recent) == 2
    assert recent[0]["title"] == "New thesis"
    assert recent[0]["preview_json"]["title"] == "Structured thesis"
    assert recent[0]["preview_json"]["key_assumptions"] == ["Revenue growth stays above 15%"]
    assert recent[1]["preview_json"]["fair_value"] == 120.0
    assert recent[1]["preview_json"]["current_price"] == 90.0


def test_message_route_creates_tool_plan_then_executes_on_yes(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    service_module = _reset_notebook_service()
    service = service_module.get_notebook_service()

    session = service.create_session(
        "NVDA",
        company_name="NVIDIA",
        user_id="user-1",
        valuation_data={"ticker": "NVDA"},
        valuation_input_json={"segments": {"segments": []}},
        valuation_output_json={"companyDTO": {"estimatedValuePerShare": 110.0, "price": 90.0}},
        valuation_id="valuation-123",
    )

    monkeypatch.setattr(
        "services.llm_service.LLMService.rewrite_query",
        lambda self, message, context, provider=None: message,
    )
    monkeypatch.setattr(
        "services.llm_service.LLMService.select_tools",
        lambda self, message, context, available_tools, provider=None: [
            {
                "tool": "dcf_recalculator",
                "params": {"wacc": 10.0},
                "reason": "Need updated fair value for the WACC scenario.",
            }
        ],
    )
    monkeypatch.setattr(
        "services.agent_tool_service.AgentToolService.execute_tool",
        lambda self, tool_name, params, session, recent_theses, auth_header=None, user_message="", llm_service=None, notebook_service=None: {
            "tool_name": tool_name,
            "status": "success",
            "data": {
                "comparison": {
                    "before": {"fair_value": 110.0},
                    "after": {"fair_value": 100.0},
                }
            },
            "execution_time_ms": 15,
        },
    )
    monkeypatch.setattr(
        "services.llm_service.LLMService.synthesize_response",
        lambda self, original_message, rewritten_query, tool_results, context, provider=None: iter(
            ["Updated fair value is $100."]
        ),
    )

    app = create_app()
    client = app.test_client()

    first_response = client.post(
        f"/bullbeargpt/api/notebook/sessions/{session.id}/messages",
        json={"message": "What if WACC was 10%?"},
    )
    first_text = first_response.get_data(as_text=True)

    assert first_response.status_code == 200
    assert "event: tool_plan" in first_text
    pending_plan = service.get_latest_pending_tool_plan(session.id)
    assert pending_plan is not None
    assert pending_plan["tool_name"] == "dcf_recalculator"

    second_response = client.post(
        f"/bullbeargpt/api/notebook/sessions/{session.id}/messages",
        json={"message": "yes"},
    )
    second_text = second_response.get_data(as_text=True)

    assert second_response.status_code == 200
    assert "event: tool_result" in second_text
    assert "Updated fair value is $100." in second_text
    assert service.get_latest_pending_tool_plan(session.id) is None

    cells = service.get_cells(session.id)
    final_cell = cells[-1]
    assert final_cell.ai_output["tool_results"][0]["tool_name"] == "dcf_recalculator"
    assert final_cell.ai_output["content"] == "Updated fair value is $100."


def test_message_route_denies_tool_plan_on_no(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    service_module = _reset_notebook_service()
    service = service_module.get_notebook_service()

    session = service.create_session(
        "MSFT",
        company_name="Microsoft",
        user_id="user-1",
        valuation_data={"ticker": "MSFT"},
        valuation_input_json={"initialCostCapital": 8.5},
        valuation_output_json={"companyDTO": {"estimatedValuePerShare": 400.0, "price": 360.0}},
        valuation_id="valuation-msft",
    )

    monkeypatch.setattr(
        "services.llm_service.LLMService.rewrite_query",
        lambda self, message, context, provider=None: message,
    )
    monkeypatch.setattr(
        "services.llm_service.LLMService.select_tools",
        lambda self, message, context, available_tools, provider=None: [
            {
                "tool": "dcf_recalculator",
                "params": {"wacc": 10.0},
                "reason": "Need updated fair value for the WACC scenario.",
            }
        ],
    )

    app = create_app()
    client = app.test_client()

    first_response = client.post(
        f"/bullbeargpt/api/notebook/sessions/{session.id}/messages",
        json={"message": "What if WACC was 10%?"},
    )
    assert first_response.status_code == 200
    _ = first_response.get_data(as_text=True)
    assert service.get_latest_pending_tool_plan(session.id)["tool_name"] == "dcf_recalculator"

    denial_response = client.post(
        f"/bullbeargpt/api/notebook/sessions/{session.id}/messages",
        json={"message": "no"},
    )
    denial_text = denial_response.get_data(as_text=True)

    assert denial_response.status_code == 200
    assert "event: tool_result" not in denial_text
    assert "Not running `dcf_recalculator`." in denial_text
    assert service.get_latest_pending_tool_plan(session.id) is None

    final_cell = service.get_cells(session.id)[-1]
    assert final_cell.ai_output["tool_results"] == []
    assert final_cell.ai_output["content"].startswith("Not running `dcf_recalculator`.")


def test_valuation_loader_returns_full_payload_and_recent_theses(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    service_module = _reset_notebook_service()
    service = service_module.get_notebook_service()

    session = service.create_session(
        "MSFT",
        company_name="Microsoft",
        user_id="user-1",
        valuation_data={"ticker": "MSFT", "companyDTO": {"estimatedValuePerShare": 410.0, "price": 360.0}},
        valuation_input_json={"initialCostCapital": 8.5, "segments": {"segments": [{"sector": "software"}]}},
        valuation_output_json={"companyDTO": {"estimatedValuePerShare": 410.0, "price": 360.0}},
        valuation_id="valuation-msft",
    )
    prior_session = service.create_session("MSFT", company_name="Microsoft", user_id="user-1")
    service.save_thesis(
        session_id=prior_session.id,
        ticker="MSFT",
        company_name="Microsoft",
        title="Prior thesis",
        summary="Older MSFT thesis",
        cells_snapshot=[],
        dcf_snapshot={"companyDTO": {"estimatedValuePerShare": 395.0, "price": 350.0}},
        user_id="user-1",
    )

    tool_service = AgentToolService()
    result = tool_service.execute_tool(
        tool_name="valuation_loader",
        params={"include": "current_valuation"},
        session=session,
        recent_theses=service.list_recent_theses_for_ticker("user-1", "MSFT", limit=2, exclude_session_id=session.id),
    )

    assert result["status"] == "success"
    assert result["data"]["valuation_data"]["ticker"] == "MSFT"
    assert result["data"]["input_json"]["initialCostCapital"] == 8.5
    assert result["data"]["output_json"]["companyDTO"]["estimatedValuePerShare"] == 410.0
    assert result["data"]["recent_theses"][0]["title"] == "Prior thesis"


def test_dcf_recalculator_updates_session_context(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    service_module = _reset_notebook_service()
    service = service_module.get_notebook_service()

    session = service.create_session(
        "MSFT",
        company_name="Microsoft",
        user_id="user-1",
        valuation_data={"ticker": "MSFT"},
        valuation_input_json={"initialCostCapital": 8.5},
        valuation_output_json={"companyDTO": {"estimatedValuePerShare": 400.0, "price": 360.0}},
        valuation_id="valuation-msft",
    )

    monkeypatch.setattr(
        "services.valuation_client.ValuationClient.recalculate_valuation_by_id",
        lambda self, valuation_id, top_level_overrides, sector_overrides=None, persist=True, auth_header=None: {
            "id": valuation_id,
            "ticker": "MSFT",
            "company_name": "Microsoft",
            "valuation_data": {
                "ticker": "MSFT",
                "companyDTO": {"estimatedValuePerShare": 380.0, "price": 360.0},
                "currency": "USD",
            },
            "input_json": {"initialCostCapital": 10.0},
            "output_json": {"companyDTO": {"estimatedValuePerShare": 380.0, "price": 360.0}},
        },
    )

    tool_service = AgentToolService()
    result = tool_service.execute_tool(
        tool_name="dcf_recalculator",
        params={"wacc": 10.0},
        session=session,
        recent_theses=[],
        notebook_service=service,
    )

    assert result["status"] == "success"
    assert result["data"]["comparison"]["before"]["fair_value"] == 400.0
    assert result["data"]["comparison"]["after"]["fair_value"] == 380.0
    assert session.valuation_output_json["companyDTO"]["estimatedValuePerShare"] == 380.0

    reloaded_session = service.get_session(session.id)
    assert reloaded_session is not None
    assert reloaded_session.valuation_output_json["companyDTO"]["estimatedValuePerShare"] == 380.0
    assert reloaded_session.valuation_input_json["initialCostCapital"] == 10.0
