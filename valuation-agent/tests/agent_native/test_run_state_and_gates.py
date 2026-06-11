"""M2: workflow run state persistence and server-side gate enforcement."""

from valuation_agent.mcp_tools import MCPToolRegistry
from valuation_agent.workflow_run_state import (
    GATE_EVIDENCE_REVIEW,
    GATE_GUIDED_REFINEMENT,
    RUN_STATE_TTL_SECONDS,
    WorkflowRunStore,
)

from test_mcp_contracts import FakeClient, _valid_evidence_packet

SCENARIO = {"targetOperatingMargin": 12.0, "salesToCapital": 1.4}

USER_JUDGMENT = {
    "source_type": "user_judgment",
    "scenario_label": "user-refined scenario",
    "answers": [{"driver": "operating_margin_next_year", "choice": "slower margin ramp"}],
}


def _registry(tmp_path, client=None):
    return MCPToolRegistry(client or FakeClient(), run_store=WorkflowRunStore(root=tmp_path / "runs"))


def _extract(registry):
    result = registry.call(
        "stockvaluation.extract_prospectus",
        {"filing_url": "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spacex.htm"},
    )
    payload = result["structuredContent"]
    return payload["run_id"], payload["prospectus"]["reviewReference"]


def test_run_state_store_persists_gates_across_instances(tmp_path):
    store_a = WorkflowRunStore(root=tmp_path / "runs")
    run = store_a.create_run(workflow_type="prospectus", subject="https://example.test/filing")
    store_a.record_gate(run["run_id"], GATE_EVIDENCE_REVIEW, "approved")

    store_b = WorkflowRunStore(root=tmp_path / "runs")
    reloaded = store_b.get_run(run["run_id"])
    assert reloaded is not None
    assert reloaded["gates"][GATE_EVIDENCE_REVIEW]["status"] == "cleared"
    assert reloaded["gates"][GATE_GUIDED_REFINEMENT]["status"] == "pending"
    assert [event["type"] for event in reloaded["events"]] == ["gate"]


def test_run_state_entries_expire_after_24_hours(tmp_path):
    clock = {"now": 1_000_000.0}
    store = WorkflowRunStore(root=tmp_path / "runs", now=lambda: clock["now"])
    run = store.create_run(workflow_type="ticker", subject="MSFT")

    clock["now"] += RUN_STATE_TTL_SECONDS - 60
    assert store.get_run(run["run_id"]) is not None

    clock["now"] += 120
    assert store.get_run(run["run_id"]) is None


def test_baseline_and_extraction_tools_issue_run_ids_with_pending_gates(tmp_path):
    registry = _registry(tmp_path)

    for call_args in (
        ("stockvaluation.researched_baseline", {"ticker": "MSFT"}),
        ("stockvaluation.value_ticker", {"ticker": "MSFT"}),
        ("stockvaluation.extract_prospectus", {"filing_url": "https://www.sec.gov/Archives/edgar/data/1/2/a.htm"}),
    ):
        payload = registry.call(*call_args)["structuredContent"]
        assert payload["ok"] is True
        assert payload["run_id"].startswith("run-")
        state = payload["workflow_state"]
        assert state["gate_enforcement"] == "tracked"
        assert state["gates_passed"] == []
        assert set(state["gates_pending"]) == {GATE_EVIDENCE_REVIEW, GATE_GUIDED_REFINEMENT}


def test_replay_2026_06_10_failure_scenario_valuation_refused_before_evidence_gate(tmp_path):
    registry = _registry(tmp_path)
    run_id, review_reference = _extract(registry)

    result = registry.call(
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
            "scenario": SCENARIO,
        },
    )

    assert result["isError"] is True
    payload = result["structuredContent"]
    assert payload["ok"] is False
    assert payload["error"]["code"] == "GATE_NOT_CLEARED"
    assert payload["failureCategory"] == "gate_not_cleared"
    assert payload["gate"] == GATE_EVIDENCE_REVIEW
    assert GATE_EVIDENCE_REVIEW in payload["workflow_state"]["gates_pending"]


def test_recorded_evidence_review_unlocks_scenario_valuation(tmp_path):
    registry = _registry(tmp_path)
    run_id, review_reference = _extract(registry)

    result = registry.call(
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
            "scenario": SCENARIO,
            "gate_records": [{"gate": GATE_EVIDENCE_REVIEW, "outcome": "approved"}],
        },
    )

    assert result["isError"] is False
    payload = result["structuredContent"]
    assert payload["ok"] is True
    state = payload["workflow_state"]
    assert GATE_EVIDENCE_REVIEW in state["gates_passed"]
    assert state["gates"][GATE_EVIDENCE_REVIEW]["outcome"] == "approved"


def test_baseline_prospectus_valuation_without_scenario_is_not_gated(tmp_path):
    registry = _registry(tmp_path)
    run_id, review_reference = _extract(registry)

    result = registry.call(
        "stockvaluation.value_prospectus",
        {"run_id": run_id, "review_reference": review_reference, "review_status": "reviewed"},
    )

    assert result["isError"] is False
    assert result["structuredContent"]["workflow_state"]["gates_pending"] == [
        GATE_EVIDENCE_REVIEW,
        GATE_GUIDED_REFINEMENT,
    ]


def test_guided_flow_recalculate_refused_until_answers_applied(tmp_path):
    registry = _registry(tmp_path)
    run_id = registry.call("stockvaluation.researched_baseline", {"ticker": "MSFT"})["structuredContent"]["run_id"]

    overrides = {
        "request_policy": {"mode": "user_refined_scenario"},
        "operating_margin_next_year": 39.0,
        "user_judgment": USER_JUDGMENT,
        "evidence_packet": _valid_evidence_packet(confidence="low"),
    }
    value_sources = {"operating_margin_next_year": "user_input"}
    refused = registry.call(
        "stockvaluation.recalculate",
        {
            "run_id": run_id,
            "ticker": "MSFT",
            "overrides": overrides,
            "value_sources": value_sources,
            "gate_records": [{"gate": GATE_EVIDENCE_REVIEW, "outcome": "approved"}],
        },
    )
    assert refused["isError"] is True
    assert refused["structuredContent"]["error"]["code"] == "GATE_NOT_CLEARED"
    assert refused["structuredContent"]["gate"] == GATE_GUIDED_REFINEMENT

    plan = registry.call(
        "stockvaluation.plan_guided_questions",
        {"run_id": run_id, "ticker": "MSFT", "workflow_type": "ticker"},
    )["structuredContent"]["guidedQuestionPlan"]
    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "guided_question_plan": plan, "use_defaults": True},
    )
    assert applied["structuredContent"]["workflow_state"]["gates"][GATE_GUIDED_REFINEMENT]["outcome"] == "applied"

    result = registry.call(
        "stockvaluation.recalculate",
        {"run_id": run_id, "ticker": "MSFT", "overrides": overrides, "value_sources": value_sources},
    )
    assert result["isError"] is False
    state = result["structuredContent"]["workflow_state"]
    assert state["gates_passed"] == [GATE_EVIDENCE_REVIEW, GATE_GUIDED_REFINEMENT]


def test_explicit_bypass_unlocks_gates_and_appears_in_workflow_state(tmp_path):
    registry = _registry(tmp_path)
    run_id = registry.call("stockvaluation.researched_baseline", {"ticker": "MSFT"})["structuredContent"]["run_id"]

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "run_id": run_id,
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "user_refined_scenario"},
                "operating_margin_next_year": 39.0,
                "user_judgment": USER_JUDGMENT,
                "evidence_packet": _valid_evidence_packet(confidence="low"),
            },
            "value_sources": {"operating_margin_next_year": "user_input"},
            "gate_records": [
                {"gate": GATE_EVIDENCE_REVIEW, "outcome": "bypassed", "reason": "quick"},
                {"gate": GATE_GUIDED_REFINEMENT, "outcome": "bypassed", "reason": "no_questions"},
            ],
        },
    )

    assert result["isError"] is False
    state = result["structuredContent"]["workflow_state"]
    assert state["gates"][GATE_EVIDENCE_REVIEW] == {
        "status": "bypassed",
        "outcome": "bypassed",
        "reason": "quick",
        "recorded_at": state["gates"][GATE_EVIDENCE_REVIEW]["recorded_at"],
    }
    assert state["gates"][GATE_GUIDED_REFINEMENT]["reason"] == "no_questions"
    assert state["gates_pending"] == []


def test_bypass_without_explicit_reason_is_refused(tmp_path):
    registry = _registry(tmp_path)
    run_id, review_reference = _extract(registry)

    result = registry.call(
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
            "scenario": SCENARIO,
            "gate_records": [{"gate": GATE_EVIDENCE_REVIEW, "outcome": "bypassed"}],
        },
    )

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "INVALID_GATE_RECORD"


def test_unknown_run_id_returns_structured_error(tmp_path):
    registry = _registry(tmp_path)

    result = registry.call(
        "stockvaluation.recalculate",
        {"run_id": "run-doesnotexist", "ticker": "MSFT", "overrides": {"wacc": 9.0}},
    )

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "UNKNOWN_RUN_ID"


def test_untracked_calls_behave_as_today_with_untracked_marker(tmp_path):
    registry = _registry(tmp_path)
    _, review_reference = _extract(registry)

    valued = registry.call(
        "stockvaluation.value_prospectus",
        {"review_reference": review_reference, "review_status": "reviewed", "scenario": SCENARIO},
    )
    assert valued["isError"] is False
    payload = valued["structuredContent"]
    assert payload["gate_enforcement"] == "untracked"
    assert "workflow_state" not in payload

    recalculated = registry.call(
        "stockvaluation.recalculate",
        {"ticker": "MSFT", "overrides": {"wacc": 9.0, "rationale": "sensitivity check"}},
    )
    assert recalculated["isError"] is False
    assert recalculated["structuredContent"]["gate_enforcement"] == "untracked"


def test_gate_enforcement_survives_across_separate_registry_processes(tmp_path):
    registry_a = _registry(tmp_path)
    run_id, _ = _extract(registry_a)

    registry_b = _registry(tmp_path)
    refused = registry_b.call(
        "stockvaluation.recalculate",
        {"run_id": run_id, "ticker": "MSFT", "overrides": {"wacc": 9.0}},
    )
    assert refused["structuredContent"]["error"]["code"] == "GATE_NOT_CLEARED"
    assert refused["structuredContent"]["gate"] == GATE_EVIDENCE_REVIEW

    registry_a.run_store.record_gate(run_id, GATE_EVIDENCE_REVIEW, "approved")
    allowed = registry_b.call(
        "stockvaluation.recalculate",
        {"run_id": run_id, "ticker": "MSFT", "overrides": {"wacc": 9.0}},
    )
    assert allowed["isError"] is False
