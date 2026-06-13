"""M3: deterministic driver anchors, scenario_validation, and range output."""

import copy
import json
from pathlib import Path

from valuation_agent.driver_anchors import anchors_from_prospectus_packet
from valuation_agent.guided_question_planner import build_guided_question_plan
from valuation_agent.mcp_tools import MCPToolRegistry
from valuation_agent.workflow_run_state import GATE_EVIDENCE_REVIEW, WorkflowRunStore

from test_mcp_contracts import _prospectus_valuation_payload

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "spacex_prospectus_extraction.json"

EVIDENCE_ITEMS = [
    {
        "driver": "revenue_growth",
        "evidence_summary": "Filing shows multi-year revenue growth.",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
        "source_date": "2026-06-03",
        "confidence": "high",
    },
    {
        "driver": "operating_margin",
        "evidence_summary": "Filing shows one profitable year in the margin history.",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
        "source_date": "2026-06-03",
        "confidence": "medium",
    },
    {
        "driver": "reinvestment_sales_to_capital",
        "evidence_summary": "Filing shows heavy capital expenditures against revenue growth.",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
        "source_date": "2026-06-03",
        "confidence": "medium",
    },
]


def _fixture_payload():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fixture_packet():
    return _fixture_payload()["prospectus"]["packet"]


class FixtureProspectusClient:
    """Service stub: extraction returns the recorded SpaceX packet; valuation
    is a deterministic function of the submitted scenario."""

    def __init__(self):
        self._packet = _fixture_packet()
        self.scenario_calls = []

    def health(self):
        return {"status": "UP"}

    def extract_prospectus(self, filing_url, expected_company=None, expected_symbol=None):
        return {"packet": copy.deepcopy(self._packet), "sourceQualityGate": _fixture_payload()["sourceQualityGate"]}

    def value_prospectus(self, packet, scenario=None):
        scenario = scenario or {}
        self.scenario_calls.append(copy.deepcopy(scenario))
        value = round(
            1.0
            + 0.1 * float(scenario.get("compound_annual_growth_2_5") or 0.0)
            + 0.2 * float(scenario.get("target_operating_margin") or 0.0)
            + 0.5 * float(scenario.get("sales_to_capital_years_1_to_5") or 0.0),
            4,
        )
        payload = copy.deepcopy(_prospectus_valuation_payload())
        payload["valuation"]["companyDTO"]["estimatedValuePerShare"] = value
        return payload


def _service_anchor(field, low, base, high):
    return {
        "schema_version": "driver_anchors.v1",
        "driver": field,
        "field": field,
        "unit": "ratio" if field == "sales_to_capital" else "percent",
        "source": "damodaran_segment_quantiles",
        "anchors": {
            "low": {"value": low, "provenance": f"service {field} low"},
            "base": {"value": base, "provenance": f"service {field} base"},
            "high": {"value": high, "provenance": f"service {field} high"},
        },
    }


class ServiceAnchoredProspectusClient(FixtureProspectusClient):
    def extract_prospectus(self, filing_url, expected_company=None, expected_symbol=None):
        payload = super().extract_prospectus(filing_url, expected_company, expected_symbol)
        payload["driverAnchors"] = {
            "revenue_growth": _service_anchor("revenue_growth", 4.0, 8.0, 12.0),
            "target_operating_margin": _service_anchor("target_operating_margin", 1.0, 9.0, 20.0),
            "sales_to_capital": _service_anchor("sales_to_capital", 0.5, 1.0, 1.9),
        }
        return payload


class RefreshingAnchoredProspectusClient(ServiceAnchoredProspectusClient):
    def value_prospectus(self, packet, scenario=None):
        payload = super().value_prospectus(packet, scenario)
        payload["driverAnchors"] = {
            "target_operating_margin": _service_anchor("target_operating_margin", 2.0, 14.0, 24.0),
            "sales_to_capital": _service_anchor("sales_to_capital", 0.6, 1.2, 2.4),
        }
        return payload


def _registry(tmp_path, client=None):
    client = client or FixtureProspectusClient()
    return MCPToolRegistry(client, run_store=WorkflowRunStore(root=tmp_path / "runs")), client


def _extract(registry):
    payload = registry.call(
        "stockvaluation.extract_prospectus",
        {"filing_url": "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm"},
    )["structuredContent"]
    assert payload["ok"] is True
    return payload["run_id"], payload["prospectus"]["reviewReference"]


def _plan(registry, run_id):
    return registry.call(
        "stockvaluation.plan_guided_questions",
        {
            "run_id": run_id,
            "company": "Space Exploration Technologies",
            "workflow_type": "prospectus",
            "evidence_items": EVIDENCE_ITEMS,
            "gate_records": [{"gate": GATE_EVIDENCE_REVIEW, "outcome": "approved"}],
        },
    )["structuredContent"]["guidedQuestionPlan"]


def test_anchor_sets_from_recorded_fixture_are_byte_identical():
    first = anchors_from_prospectus_packet(_fixture_packet())
    second = anchors_from_prospectus_packet(_fixture_packet())

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert set(first) == {"revenue_growth", "target_operating_margin", "sales_to_capital", "net_proceeds"}
    for field, anchor_set in first.items():
        anchors = anchor_set["anchors"]
        assert set(anchors) == {"low", "base", "high"}
        for entry in anchors.values():
            assert isinstance(entry["value"], (int, float))
            assert entry["provenance"]
    assert "filing_revenue_history" in first["revenue_growth"]["anchors"]["base"]["provenance"]
    assert "filing_margin_history" in first["target_operating_margin"]["anchors"]["base"]["provenance"]
    assert "filing_reinvestment_history" in first["sales_to_capital"]["anchors"]["base"]["provenance"]
    assert "offering_terms" in first["net_proceeds"]["anchors"]["base"]["provenance"]
    proceeds = first["net_proceeds"]["anchors"]
    assert proceeds["low"]["value"] == proceeds["base"]["value"] == proceeds["high"]["value"]


def test_material_numeric_questions_carry_anchor_choices_with_provenance(tmp_path):
    registry, _ = _registry(tmp_path)
    run_id, _ = _extract(registry)
    expected = anchors_from_prospectus_packet(_fixture_packet())

    plan = _plan(registry, run_id)

    anchored = {
        question["anchor_set"]["field"]: question
        for question in plan["questions"]
        if question.get("anchor_set")
    }
    assert {"revenue_growth", "target_operating_margin", "sales_to_capital"} <= set(anchored)
    for field, question in anchored.items():
        assert question["anchor_set"] == expected[field]
        assert question["model_action"] == "user scenario override"
        choices = {choice["label"]: choice for choice in question["bounded_choices"]}
        for label, anchor_label in (("A", "low"), ("B", "base"), ("C", "high")):
            assert choices[label]["override_candidate"]["value"] == expected[field]["anchors"][anchor_label]["value"]
            assert choices[label]["anchor_provenance"] == expected[field]["anchors"][anchor_label]["provenance"]
        assert choices["D"]["anchor_label"] == "user_input"
        assert question["hidden_model_mapping"]["candidate_source"] == "anchor:base"
    assert plan["scenario_range"]["status"] == "recommended"


def test_extract_prospectus_prefers_service_driver_anchors_and_keeps_offering_anchor(tmp_path):
    registry, _ = _registry(tmp_path, ServiceAnchoredProspectusClient())
    run_id, _ = _extract(registry)

    run = registry.run_store.get_run(run_id)

    assert run["anchors"]["target_operating_margin"]["source"] == "damodaran_segment_quantiles"
    assert run["anchors"]["target_operating_margin"]["anchors"]["base"]["value"] == 9.0
    assert run["anchors"]["sales_to_capital"]["anchors"]["high"]["value"] == 1.9
    assert run["anchors"]["net_proceeds"]["anchors"]["base"]["provenance"].startswith("offering_terms")


def test_value_prospectus_refreshes_run_anchors_from_reviewed_packet(tmp_path):
    registry, _ = _registry(tmp_path, RefreshingAnchoredProspectusClient())
    run_id, review_reference = _extract(registry)

    result = registry.call(
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
        },
    )

    assert result["isError"] is False
    run = registry.run_store.get_run(run_id)
    assert run["anchors"]["target_operating_margin"]["anchors"]["base"]["value"] == 14.0
    assert run["anchors"]["sales_to_capital"]["anchors"]["high"]["value"] == 2.4
    assert run["anchors"]["net_proceeds"]["anchors"]["base"]["provenance"].startswith("offering_terms")


def test_planner_keeps_candidate_required_and_asks_user_when_no_anchor_exists():
    plan = build_guided_question_plan(
        {
            "company": "Space Exploration Technologies",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": True,
            "evidence_items": [EVIDENCE_ITEMS[2]],
        }
    )

    question = plan["questions"][0]
    assert question["status"] == "candidate-required"
    assert question["requires_user_value"] is True
    assert "ask the user" in question["user_value_instruction"].lower()
    assert plan["scenario_range"]["status"] == "candidate_values_required"


def test_scenario_validation_refuses_unanchored_value_and_allows_user_input(tmp_path):
    registry, _ = _registry(tmp_path)
    run_id, review_reference = _extract(registry)
    _plan(registry, run_id)

    refused = registry.call(
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
            "scenario": {"target_operating_margin": 12.0},
        },
    )
    assert refused["isError"] is True
    payload = refused["structuredContent"]
    assert payload["ok"] is False
    assert payload["error"]["code"] == "UNANCHORED_SCENARIO_VALUE"
    assert payload["failureCategory"] == "unanchored_scenario_value"
    assert payload["driver"] == "target_operating_margin"

    allowed = registry.call(
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
            "scenario": {"target_operating_margin": 12.0},
            "value_sources": {"target_operating_margin": "user_input"},
        },
    )
    assert allowed["structuredContent"]["error"]["code"] != "UNANCHORED_SCENARIO_VALUE" if not allowed["structuredContent"]["ok"] else True


def test_guided_custom_scalar_candidate_can_drive_final_prospectus_value_without_manual_value_sources(tmp_path):
    registry, _ = _registry(tmp_path)
    run_id, review_reference = _extract(registry)
    plan = _plan(registry, run_id)
    answers = {}
    for question in plan["questions"]:
        if not question.get("anchor_set"):
            continue
        field = question["anchor_set"]["field"]
        answers[question["id"]] = {"choice": "D", "value": 12.0} if field == "target_operating_margin" else "B"

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "answers": answers},
    )["structuredContent"]

    candidate = applied["prospectusScenarioCandidate"]
    assert candidate["value_sources"]["target_operating_margin"] == "user_input"
    record = applied["guidedAnswerRecord"]["target_operating_margin"]
    assert record["source"] == "user_input"
    assert "anchor_explanation" in record

    valued = registry.call(
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
            "prospectusScenarioCandidate": candidate,
        },
    )["structuredContent"]

    assert valued["ok"] is True
    assert valued.get("error", {}).get("code") != "UNANCHORED_SCENARIO_VALUE"
    assert valued["scenarioValueSources"]["target_operating_margin"] == "user_input"


def _run_all_default_flow(tmp_path, name):
    registry, client = _registry(tmp_path / name)
    run_id, review_reference = _extract(registry)
    plan = _plan(registry, run_id)
    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "guided_question_plan": plan, "use_defaults": True},
    )["structuredContent"]
    candidate = applied["prospectusScenarioCandidate"]
    assert candidate["supported"] is True
    valued = registry.call(
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
            "scenario": candidate["scenario"],
        },
    )["structuredContent"]
    return applied, candidate["scenario"], valued, client


def test_two_all_default_runs_produce_identical_scenario_payloads_and_value(tmp_path):
    applied_a, scenario_a, valued_a, client_a = _run_all_default_flow(tmp_path, "run_a")
    applied_b, scenario_b, valued_b, client_b = _run_all_default_flow(tmp_path, "run_b")

    assert json.dumps(scenario_a, sort_keys=True) == json.dumps(scenario_b, sort_keys=True)
    assert client_a.scenario_calls[-1] == client_b.scenario_calls[-1]
    assert valued_a["ok"] is True and valued_b["ok"] is True
    assert "valuationRange" not in valued_a
    value_a = valued_a["dcf"]["estimatedValuePerShare"]
    value_b = valued_b["dcf"]["estimatedValuePerShare"]
    assert value_a == value_b

    record = applied_a["guidedAnswerRecord"]
    assert {"revenue_growth", "target_operating_margin", "sales_to_capital"} <= set(record)
    for entry in record.values():
        assert entry["source"] == "anchor:base"


def test_range_output_names_unresolved_driver_with_low_and_high_values(tmp_path):
    registry, client = _registry(tmp_path)
    run_id, review_reference = _extract(registry)
    plan = _plan(registry, run_id)

    answers = {
        question["id"]: "B"
        for question in plan["questions"]
        if question.get("anchor_set")
        and question["hidden_model_mapping"]["supported_override_field"] != "sales_to_capital"
    }
    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "guided_question_plan": plan, "answers": answers},
    )["structuredContent"]
    scenario = applied["prospectusScenarioCandidate"]["scenario"]
    assert "sales_to_capital_years_1_to_5" not in scenario

    valued = registry.call(
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
            "scenario": scenario,
        },
    )["structuredContent"]

    assert valued["ok"] is True
    value_range = valued["valuationRange"]
    assert value_range["status"] == "unresolved_material_drivers"
    assert value_range["unresolved_drivers"] == ["sales_to_capital"]
    assert value_range["spread_drivers"] == ["sales_to_capital"]
    assert value_range["low"]["anchor_labels"] == {"sales_to_capital": "low"}
    assert value_range["high"]["anchor_labels"] == {"sales_to_capital": "high"}
    low_value = value_range["low"]["value_per_share"]
    high_value = value_range["high"]["value_per_share"]
    assert low_value < high_value
    assert value_range["value_spread"] == {"min": low_value, "max": high_value}
    assert "prospectus" not in valued
    assert "valuation" not in valued


def test_apply_guided_answers_uses_stored_plan_without_echo(tmp_path):
    registry, _ = _registry(tmp_path)
    run_id, _ = _extract(registry)
    _plan(registry, run_id)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "use_defaults": True},
    )["structuredContent"]

    assert applied["ok"] is True
    assert applied["planSource"] == "run_state"
    candidate = applied["prospectusScenarioCandidate"]
    assert candidate["supported"] is True
    assert candidate["scenario"]["compound_annual_growth_2_5"] == 34.08
    assert {"revenue_growth", "target_operating_margin", "sales_to_capital"} <= set(applied["guidedAnswerRecord"])


def test_degraded_plan_echo_cannot_corrupt_anchor_mapping(tmp_path):
    """Replay of the 2026-06-11 live-tier session A failure: a truncated plan
    echo that lost model_action must not hollow out the scenario, because the
    server's stored plan is canonical."""
    registry, _ = _registry(tmp_path)
    run_id, review_reference = _extract(registry)
    plan = _plan(registry, run_id)

    degraded = json.loads(json.dumps(plan))
    for question in degraded["questions"]:
        question.pop("model_action", None)
        for choice in question.get("bounded_choices", []):
            choice.pop("model_action", None)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "guided_question_plan": degraded, "use_defaults": True},
    )["structuredContent"]

    assert applied["planSource"] == "run_state"
    candidate = applied["prospectusScenarioCandidate"]
    assert candidate["supported"] is True
    assert candidate["scenario"]["target_operating_margin"] == 3.33

    valued = registry.call(
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
            "scenario": candidate["scenario"],
        },
    )["structuredContent"]
    assert valued["ok"] is True
    assert "valuationRange" not in valued


def test_guided_answer_record_excludes_unmapped_answers(tmp_path):
    registry, _ = _registry(tmp_path)
    run_id, _ = _extract(registry)
    # No tracked plan call: the run has no stored plan, so the degraded echo
    # is all the server sees and nothing maps.
    plan = build_guided_question_plan(
        {
            "company": "Space Exploration Technologies",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": True,
            "evidence_items": EVIDENCE_ITEMS,
            "driver_anchors": anchors_from_prospectus_packet(_fixture_packet()),
        }
    )
    degraded = json.loads(json.dumps(plan))
    for question in degraded["questions"]:
        question.pop("model_action", None)
        for choice in question.get("bounded_choices", []):
            choice.pop("model_action", None)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "guided_question_plan": degraded, "use_defaults": True},
    )["structuredContent"]

    assert applied["planSource"] == "request"
    assert applied["prospectusScenarioCandidate"]["supported"] is False
    assert applied["guidedAnswerRecord"] == {}
    assert registry.run_store.get_run(run_id)["guided_answers"] == {}


def test_scenario_less_call_after_plan_returns_range_for_unresolved_drivers(tmp_path):
    registry, _ = _registry(tmp_path)
    run_id, review_reference = _extract(registry)
    _plan(registry, run_id)

    valued = registry.call(
        "stockvaluation.value_prospectus",
        {"run_id": run_id, "review_reference": review_reference, "review_status": "reviewed"},
    )["structuredContent"]

    assert valued["ok"] is True
    value_range = valued["valuationRange"]
    assert value_range["status"] == "unresolved_material_drivers"
    assert value_range["unresolved_drivers"] == ["revenue_growth", "sales_to_capital", "target_operating_margin"]
    assert "dcf" not in valued


def test_apply_guided_answers_handles_plan_without_questions(tmp_path):
    registry, _ = _registry(tmp_path)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"guided_question_plan": {"plan_id": "placeholder"}, "use_defaults": True},
    )["structuredContent"]

    assert applied["ok"] is True
    assert applied["userJudgment"]["answers"] == []
    assert applied["prospectusScenarioCandidate"]["supported"] is False


def test_anchor_state_records_anchors_in_run_state(tmp_path):
    registry, _ = _registry(tmp_path)
    run_id, _ = _extract(registry)

    run = registry.run_store.get_run(run_id)
    assert run["anchors"] == anchors_from_prospectus_packet(_fixture_packet())

    _plan(registry, run_id)
    run = registry.run_store.get_run(run_id)
    assert set(run["material_anchor_fields"]) == {"revenue_growth", "target_operating_margin", "sales_to_capital"}
    assert any(event.get("type") == "guided_plan_created" for event in run["events"])


class SegmentDetailedProspectusClient(FixtureProspectusClient):
    def extract_prospectus(self, filing_url, expected_company=None, expected_symbol=None):
        payload = super().extract_prospectus(filing_url, expected_company, expected_symbol)
        margin_anchor = _service_anchor("target_operating_margin", -0.32, 8.95, 18.48)
        margin_anchor["source_note"] = "filing-based segment mix plus Damodaran industry quantiles"
        margin_anchor["segment_breakdown"] = [
            {
                "segment": "Space",
                "sector_key": "aerospace-defense",
                "industry_group": "Aerospace/Defense",
                "mapping_confidence": "reviewed",
                "weight": 0.264,
                "low": -4.44,
                "base": 6.68,
                "high": 13.39,
            },
            {
                "segment": "Connectivity",
                "sector_key": "telecom-services",
                "industry_group": "Telecom. Services",
                "mapping_confidence": "reviewed",
                "weight": 0.736,
                "low": 1.16,
                "base": 9.76,
                "high": 20.31,
            },
        ]
        payload["driverAnchors"] = {"target_operating_margin": margin_anchor}
        return payload


def test_segment_level_custom_answers_route_into_prospectus_scenario_segments(tmp_path):
    registry, _ = _registry(tmp_path, SegmentDetailedProspectusClient())
    run_id, _ = _extract(registry)
    plan = _plan(registry, run_id)

    segment_questions = [item for item in plan["questions"] if item.get("segment_scope")]
    assert len(segment_questions) == 1
    question = segment_questions[0]
    assert question["segment_scope"] == {
        "segment": "Space",
        "field": "target_operating_margin",
        "sector_key": "aerospace-defense",
        "mapped_industry": "Aerospace/Defense",
        "revenue_weight_pct": 26.4,
    }
    assert "filing-based segment mix plus Damodaran industry quantiles" in question["anchor_explanation"]["summary"]

    # Answer only the segment-level question: the driver must resolve through
    # the segment answer, without a company-level numeric answer.
    answers = {
        question["id"]: {
            "choice": "D",
            "value": [{"segment": "Space", "field": "target_operating_margin", "value": 12.0}],
        }
    }
    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "answers": answers},
    )["structuredContent"]

    assert applied["ok"] is True
    candidate = applied["prospectusScenarioCandidate"]
    assert candidate["supported"] is True
    segment_rows = {row["name"]: row for row in candidate["scenario"]["segments"]}
    assert set(segment_rows) == {"Space", "Connectivity"}
    assert segment_rows["Space"]["target_operating_margin"] == 12.0
    assert segment_rows["Space"]["mapped_industry"] == "Aerospace/Defense"
    assert segment_rows["Connectivity"]["target_operating_margin"] == 9.76
    assert segment_rows["Connectivity"]["mapped_industry"] == "Telecom. Services"

    record = applied["guidedAnswerRecord"]["target_operating_margin"]
    assert record["source"] == "segments:mixed"
    assert record["value"]["segments"][0]["target_operating_margin"] == 12.0


def test_segment_level_partial_answer_preserves_other_reviewed_segments_with_defaults(tmp_path):
    registry, _ = _registry(tmp_path, SegmentDetailedProspectusClient())
    run_id, _ = _extract(registry)
    plan = _plan(registry, run_id)
    question = next(item for item in plan["questions"] if item.get("segment_scope"))

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "answers": {
                question["id"]: {
                    "choice": "D",
                    "value": [{"segment": "Space", "field": "target_operating_margin", "value": 12.0}],
                }
            },
        },
    )["structuredContent"]

    candidate = applied["prospectusScenarioCandidate"]
    assert candidate["supported"] is True
    segment_rows = {row["name"]: row for row in candidate["scenario"]["segments"]}
    assert set(segment_rows) == {"Space", "Connectivity"}
    assert segment_rows["Connectivity"]["target_operating_margin"] == 9.76
    assert applied["guidedAnswerRecord"]["target_operating_margin"]["fallback_segments"] == ["Connectivity"]


def test_segment_level_defaults_use_segment_base_anchors_alongside_company_default(tmp_path):
    registry, _ = _registry(tmp_path, SegmentDetailedProspectusClient())
    run_id, review_reference = _extract(registry)
    _plan(registry, run_id)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "use_defaults": True},
    )["structuredContent"]

    assert applied["ok"] is True
    segment_rows = {
        row["name"]: row
        for row in applied["prospectusScenarioCandidate"]["scenario"]["segments"]
    }
    assert segment_rows["Space"]["target_operating_margin"] == 6.68
    # The company-level margin default also answered with the weighted base
    # anchor, so the driver record keeps numeric anchor provenance.
    record = applied["guidedAnswerRecord"]["target_operating_margin"]
    assert record["source"] == "anchor:base"
    assert record["value"] == 8.95


def test_segment_level_base_anchor_answer_records_segment_anchor_source(tmp_path):
    registry, _ = _registry(tmp_path, SegmentDetailedProspectusClient())
    run_id, _ = _extract(registry)
    plan = _plan(registry, run_id)
    question = next(item for item in plan["questions"] if item.get("segment_scope"))

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "answers": {question["id"]: "B"}},
    )["structuredContent"]

    record = applied["guidedAnswerRecord"]["target_operating_margin"]
    assert record["source"] == "segments:anchor:base"
    assert record["value"]["segments"][0]["target_operating_margin"] == 6.68
