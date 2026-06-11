"""M6 deterministic conformance tier: scripted replays over the recorded
SpaceX fixture asserting every M2/M3 contract, plus conformance-record
emission and diffing."""

import json
from pathlib import Path

import pytest

from valuation_agent.conformance import build_conformance_record, diff_conformance_records
from valuation_agent.mcp_tools import MCPToolRegistry
from valuation_agent.workflow_run_state import WorkflowRunStore

from test_anchor_scenario_validation_and_range import FixtureProspectusClient

CASES = json.loads((Path(__file__).parent / "fixtures" / "conformance_replay_cases.json").read_text(encoding="utf-8"))


class ReplayContext:
    """Substitutes recorded placeholders with values captured from prior steps."""

    def __init__(self):
        self.values = {
            "$filing_url": CASES["filing_url"],
            "$evidence_items": CASES["evidence_items"],
        }

    def resolve(self, value):
        if isinstance(value, str) and value.startswith("$"):
            return self.values[value]
        if isinstance(value, dict):
            return {key: self.resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.resolve(item) for item in value]
        return value

    def capture(self, payload):
        if payload.get("run_id"):
            self.values["$run_id"] = payload["run_id"]
        prospectus = payload.get("prospectus") or {}
        if prospectus.get("reviewReference"):
            self.values["$review_reference"] = prospectus["reviewReference"]
        plan = payload.get("guidedQuestionPlan")
        if plan:
            self.values["$plan"] = plan
            self.values["$answers_except_sales_to_capital"] = {
                question["id"]: "B"
                for question in plan.get("questions", [])
                if question.get("anchor_set")
                and question["anchor_set"]["field"] != "sales_to_capital"
            }
        candidate = payload.get("prospectusScenarioCandidate") or {}
        if candidate.get("scenario"):
            self.values["$scenario_candidate"] = candidate["scenario"]


def _replay_case(case, tmp_path, name="replay"):
    registry = MCPToolRegistry(
        FixtureProspectusClient(),
        run_store=WorkflowRunStore(root=tmp_path / name / "runs"),
    )
    context = ReplayContext()
    last_payload = None
    for step in case["steps"]:
        result = registry.call(step["tool"], context.resolve(step["args"]))
        payload = result["structuredContent"]
        context.capture(payload)
        expect = step["expect"]
        assert payload["ok"] is expect["ok"], (case["case_id"], step["tool"], payload.get("error"))
        if "error_code" in expect:
            assert payload["error"]["code"] == expect["error_code"], (case["case_id"], payload["error"])
        if "gate" in expect:
            assert payload["gate"] == expect["gate"]
        if "driver" in expect:
            assert payload["driver"] == expect["driver"]
        if expect.get("point_estimate"):
            assert "valuationRange" not in payload
            assert payload["dcf"]["estimatedValuePerShare"] is not None
        if expect.get("range"):
            assert payload["valuationRange"]["status"] == "unresolved_material_drivers"
        if "unresolved_drivers" in expect:
            assert payload["valuationRange"]["unresolved_drivers"] == expect["unresolved_drivers"]
        last_payload = payload
    run = registry.run_store.get_run(context.values.get("$run_id"))
    return registry, run, last_payload


def _case(case_id):
    return next(case for case in CASES["cases"] if case["case_id"] == case_id)


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda case: case["case_id"])
def test_conformance_replay_cases_assert_gate_and_anchor_contracts(case, tmp_path):
    _replay_case(case, tmp_path)


def test_conformance_record_from_all_default_replay_summarizes_run(tmp_path):
    _, run, payload = _replay_case(_case("all_default_run"), tmp_path)

    record = build_conformance_record(run, value_per_share=payload["dcf"]["estimatedValuePerShare"])

    assert record["schema_version"] == "conformance_record.v1"
    assert record["workflow_type"] == "prospectus"
    assert [gate["gate"] for gate in record["gates_in_order"]] == ["evidence_review", "guided_refinement"]
    assert [gate["outcome"] for gate in record["gates_in_order"]] == ["approved", "applied"]
    assert record["question_count"] == 3
    assert record["material_anchor_fields"] == ["revenue_growth", "sales_to_capital", "target_operating_margin"]
    assert set(record["drivers"]) == {"revenue_growth", "sales_to_capital", "target_operating_margin"}
    assert all(entry["source"] == "anchor:base" for entry in record["drivers"].values())
    assert record["final_case_type"] == "point"
    assert isinstance(record["value"], float)


def test_two_all_default_replays_produce_identical_conformance_records(tmp_path):
    case = _case("all_default_run")
    _, run_a, payload_a = _replay_case(case, tmp_path, "first")
    _, run_b, payload_b = _replay_case(case, tmp_path, "second")

    record_a = build_conformance_record(run_a, value_per_share=payload_a["dcf"]["estimatedValuePerShare"])
    record_b = build_conformance_record(run_b, value_per_share=payload_b["dcf"]["estimatedValuePerShare"])

    diff = diff_conformance_records(record_a, record_b)
    assert diff == {"identical": True, "differences": []}
    assert record_a["value"] == record_b["value"]


def test_conformance_record_for_range_run_names_unresolved_driver(tmp_path):
    _, run, payload = _replay_case(_case("range_when_driver_unresolved"), tmp_path)

    record = build_conformance_record(run, value_range=payload["valuationRange"])

    assert record["final_case_type"] == "range"
    assert record["value"]["unresolved_drivers"] == ["sales_to_capital"]
    assert record["value"]["low"] < record["value"]["high"]


def test_conformance_diff_reports_exact_divergence(tmp_path):
    _, run, payload = _replay_case(_case("all_default_run"), tmp_path)
    record_a = build_conformance_record(run, value_per_share=payload["dcf"]["estimatedValuePerShare"])
    record_b = json.loads(json.dumps(record_a))
    record_b["value"] = record_a["value"] + 1.0
    record_b["drivers"]["revenue_growth"]["source"] = "user_input"

    diff = diff_conformance_records(record_a, record_b)

    assert diff["identical"] is False
    paths = {difference["path"] for difference in diff["differences"]}
    assert paths == {"value", "drivers.revenue_growth.source"}
