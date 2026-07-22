"""M6 deterministic conformance tier: scripted replays over the recorded
SpaceX fixture asserting every M2/M3 contract, plus conformance-record
emission and diffing."""

import json
import os
from pathlib import Path
import stat
import subprocess

import pytest

from valuation_agent.conformance import build_conformance_record, diff_conformance_records
from valuation_agent.mcp_tools import MCPToolRegistry
from valuation_agent.workflow_run_state import WorkflowRunStore

from test_anchor_scenario_validation_and_range import FixtureProspectusClient
from test_mcp_contracts import _valuation_payload

CASES = json.loads((Path(__file__).parent / "fixtures" / "conformance_replay_cases.json").read_text(encoding="utf-8"))
ROOT_DIR = Path(__file__).resolve().parents[3]


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


class TickerConformanceClient:
    def value_ticker(self, ticker, overrides=None):
        return _valuation_payload()


def _ticker_evidence_items():
    return [
        {
            "evidence_id": "demand",
            "driver": "revenue_growth",
            "source_title": "Customer cohort memo",
            "source_url": "https://example.com/demand",
            "source_date": "2026-05-01",
            "evidence_summary": "Renewal demand is recurring.",
            "confidence": "high",
        },
        {
            "evidence_id": "margin",
            "driver": "operating_margin",
            "source_title": "Margin bridge",
            "source_url": "https://example.com/margin",
            "source_date": "2026-05-02",
            "evidence_summary": "Margins are normalizing.",
            "confidence": "high",
        },
        {
            "evidence_id": "capital",
            "driver": "reinvestment_sales_to_capital",
            "source_title": "Capital plan",
            "source_url": "https://example.com/capital",
            "source_date": "2026-05-03",
            "evidence_summary": "Growth needs heavier reinvestment.",
            "confidence": "high",
        },
        {
            "evidence_id": "risk",
            "driver": "risk_wacc",
            "source_title": "Risk review",
            "source_url": "https://example.com/risk",
            "source_date": "2026-05-04",
            "evidence_summary": "Execution risk is elevated.",
            "confidence": "high",
        },
    ]


def _ticker_framing_forks():
    def fork(fork_id, driver, question, refs, options):
        return {
            "schema_version": "framing_fork.v1",
            "fork_id": fork_id,
            "primary_driver": driver,
            "causal_question": question,
            "confidence": "high",
            "material": True,
            "supporting_evidence_refs": refs,
            "opposing_evidence_refs": [],
            "evidence_gaps": ["No direct falsifier data is disclosed."],
            "options": [
                {"label": label, "story": story, "falsifier": falsifier}
                for label, story, falsifier in options
            ],
            "analysis_lean": "B",
        }

    return [
        fork(
            "growth_durability",
            "revenue_growth",
            "Is demand recurring or pulled forward?",
            ["demand"],
            [
                ("A", "Recurring demand expands.", "Renewals weaken."),
                ("B", "Demand normalizes.", "Backlog stalls."),
                ("C", "Demand was pulled forward.", "New workloads fail to replace churn."),
            ],
        ),
        fork(
            "margin_path",
            "operating_margin",
            "Are margins normalizing or structurally capped?",
            ["margin"],
            [
                ("A", "Margins stay capped.", "Cost discipline appears."),
                ("B", "Margins normalize.", "Fixed costs rise again."),
                ("C", "Margins expand faster.", "Pricing pressure returns."),
            ],
        ),
        fork(
            "reinvestment_intensity",
            "reinvestment_sales_to_capital",
            "Does growth need heavier reinvestment?",
            ["capital"],
            [
                ("A", "Capital efficiency improves.", "Capacity additions lag revenue."),
                ("B", "Reinvestment stays near base.", "Working capital absorbs growth."),
                ("C", "Growth needs heavier reinvestment.", "Asset turns improve."),
            ],
        ),
        fork(
            "risk_discount",
            "risk_wacc",
            "Is base risk enough for execution uncertainty?",
            ["risk"],
            [
                ("A", "Base risk is enough.", "Launch failures increase."),
                ("B", "Risk needs a modest premium.", "Execution volatility falls."),
                ("C", "Risk needs a large premium.", "Delivery metrics stabilize."),
            ],
        ),
    ]


def _replay_semantic_ticker(tmp_path, name="semantic"):
    registry = MCPToolRegistry(
        TickerConformanceClient(),
        run_store=WorkflowRunStore(root=tmp_path / name / "runs"),
    )
    baseline = registry.call("stockvaluation.value_ticker", {"ticker": "MSFT"})["structuredContent"]
    run_id = baseline["run_id"]
    plan_payload = registry.call(
        "stockvaluation.plan_guided_questions",
        {
            "run_id": run_id,
            "gate_records": [{"gate": "evidence_review", "outcome": "approved"}],
            "company": "Microsoft Corporation",
            "ticker": "MSFT",
            "workflow_type": "ticker",
            "evidence_items": _ticker_evidence_items(),
            "framing_forks": _ticker_framing_forks(),
        },
    )["structuredContent"]
    plan = plan_payload["guidedQuestionPlan"]
    apply_payload = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "answers": {
                "semantic_growth_durability": "A",
                "semantic_margin_path": "B",
                "semantic_reinvestment_intensity": "C",
                "semantic_risk_discount": {"choice": "D", "value": 9.2},
            },
        },
    )["structuredContent"]
    recalc_payload = registry.call(
        "stockvaluation.recalculate",
        {
            "run_id": run_id,
            "ticker": "MSFT",
            "overrides": apply_payload["tickerOverridesCandidate"]["overrides"],
        },
    )["structuredContent"]
    return registry.run_store.get_run(run_id), plan, apply_payload, recalc_payload


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


def test_semantic_ticker_replay_conformance_records_revealed_thesis_and_exact_diff(tmp_path):
    run_a, plan_a, apply_a, payload_a = _replay_semantic_ticker(tmp_path, "first")
    run_b, _plan_b, _apply_b, payload_b = _replay_semantic_ticker(tmp_path, "second")

    record_a = build_conformance_record(run_a, value_per_share=payload_a["dcf"]["estimatedValuePerShare"])
    record_b = build_conformance_record(run_b, value_per_share=payload_b["dcf"]["estimatedValuePerShare"])

    assert [fork["primary_driver"] for fork in record_a["accepted_framing_forks"]] == [
        "revenue_growth",
        "operating_margin",
        "reinvestment_sales_to_capital",
        "risk_wacc",
    ]
    assert set(record_a["drivers"]) == {"revenue_growth", "target_operating_margin", "sales_to_capital", "wacc"}
    assert record_a["coherence_status"] == "clean"
    assert record_a["coherence_challenge_count"] == 0
    assert record_a["revealed_thesis"] == apply_a["revealedThesis"]
    assert record_a["final_scenario_record"] == {"case_type": "point", "value": payload_a["dcf"]["estimatedValuePerShare"]}
    assert plan_a["question_order"][:4] == [decision["question_id"] for decision in record_a["revealed_thesis"]["decisions"]]
    assert diff_conformance_records(record_a, record_b) == {"identical": True, "differences": []}

    mutated = json.loads(json.dumps(record_a))
    mutated["revealed_thesis"]["decisions"][0]["selected_interpretation"] = "Changed interpretation."
    diff = diff_conformance_records(record_a, mutated)

    assert diff == {
        "identical": False,
        "differences": [
            {
                "path": "revealed_thesis.decisions[0].interpretation",
                "first": record_a["revealed_thesis"]["decisions"][0]["selected_interpretation"],
                "second": "Changed interpretation.",
            }
        ],
    }


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


@pytest.mark.parametrize(
    "runtime_factory",
    [
        lambda tmp_path: "python3.11",
        lambda tmp_path: str(tmp_path / "missing-python"),
        lambda tmp_path: str(tmp_path / "not-executable-python"),
        lambda tmp_path: str(tmp_path / "python-3.10"),
    ],
    ids=["relative", "missing", "non_executable", "non_311"],
)
def test_local_smoke_rejects_invalid_python_runtime_before_service_access(tmp_path, runtime_factory):
    non_executable = tmp_path / "not-executable-python"
    non_executable.write_text("#!/bin/sh\necho 3.11.0\n", encoding="utf-8")
    fake_non_311 = tmp_path / "python-3.10"
    fake_non_311.write_text("#!/bin/sh\necho 3.10.13\n", encoding="utf-8")
    fake_non_311.chmod(fake_non_311.stat().st_mode | stat.S_IXUSR)

    env = {
        **os.environ,
        "STOCKVALUATION_PYTHON_BIN": runtime_factory(tmp_path),
    }
    result = subprocess.run(
        [str(ROOT_DIR / "scripts" / "local_smoke.sh"), "--agent-native", "--ticker", "MSFT"],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "INVALID_PYTHON_RUNTIME" in result.stderr
    assert "yfinance health" not in result.stdout
    assert "valuation-service" not in result.stdout
