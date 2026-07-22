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


HIGH_SUPPORT = [
    {
        "claim": "High-confidence source backs this driver.",
        "confidence": "high",
        "source_url": "https://example.com/source",
    }
]

FOUR_LEVER_DRIVERS = [
    "revenue_growth",
    "operating_margin",
    "reinvestment_sales_to_capital",
    "risk_wacc",
]
FOUR_LEVER_WEAK_SUPPORT_DRIVERS = [
    "revenue_growth",
    "sales_to_capital",
    "target_operating_margin",
    "wacc",
]


def _coherence_choice(label, field, value, anchor_label, **extra):
    choice = {
        "label": label,
        "story": f"{field} {anchor_label}",
        "override_candidate": {"field": field, "value": value},
        "anchor_label": anchor_label,
        "scenario_key": anchor_label,
        "model_action": "user scenario override",
        "confidence": "medium",
    }
    choice.update(extra)
    return choice


def _coherence_question(qid, driver, field, *, evidence_used=None, supporting_evidence_refs=None, **extra):
    values = {
        "revenue_growth": {"low": 6.0, "base": 8.0, "high": 12.0},
        "target_operating_margin": {"low": 35.0, "base": 45.0, "high": 54.0},
        "sales_to_capital": {"low": 1.6, "base": 2.4, "high": 2.88},
        "wacc": {"low": 7.7, "base": 8.5, "high": 9.3},
        "terminal_revenue": {"low": 900.0, "base": 1_000.0, "high": 1_100.0},
    }
    question = {
        "id": qid,
        "driver": driver,
        "model_action": "user scenario override",
        "default_answer": {"choice_label": "B"},
        "hidden_model_mapping": {"supported_override_field": field},
        "evidence_used": evidence_used or [],
        "supporting_evidence_refs": supporting_evidence_refs or [],
        "bounded_choices": [
            _coherence_choice("A", field, values[field]["low"], "low", **extra),
            _coherence_choice("B", field, values[field]["base"], "base", **extra),
            _coherence_choice("C", field, values[field]["high"], "high", **extra),
        ],
    }
    return question


def _coherence_plan(*questions):
    return {"plan_id": "coherence_contract", "questions": list(questions)}


def _stock_plan(evidence_used=None, supporting_evidence_refs=None):
    return _coherence_plan(
        _coherence_question(
            "growth",
            "revenue_growth",
            "revenue_growth",
            evidence_used=evidence_used,
            supporting_evidence_refs=supporting_evidence_refs,
        ),
        _coherence_question(
            "margin",
            "operating_margin",
            "target_operating_margin",
            evidence_used=evidence_used,
            supporting_evidence_refs=supporting_evidence_refs,
        ),
        _coherence_question(
            "reinvestment",
            "reinvestment_sales_to_capital",
            "sales_to_capital",
            evidence_used=evidence_used,
            supporting_evidence_refs=supporting_evidence_refs,
        ),
        _coherence_question(
            "risk",
            "risk_wacc",
            "wacc",
            evidence_used=evidence_used,
            supporting_evidence_refs=supporting_evidence_refs,
        ),
        _coherence_question(
            "extra",
            "terminal_revenue",
            "terminal_revenue",
            evidence_used=evidence_used,
            supporting_evidence_refs=supporting_evidence_refs,
        ),
    )


def _semantic_fork(driver):
    return {
        "schema_version": "framing_fork.v1",
        "fork_id": f"{driver}_coherence",
        "primary_driver": driver,
        "causal_question": f"Which bounded story best fits {driver.replace('_', ' ')}?",
        "confidence": "high",
        "material": True,
        "supporting_evidence_refs": [f"{driver}-support"],
        "opposing_evidence_refs": [],
        "evidence_gaps": [],
        "options": [
            {"label": "A", "story": "The conservative story best matches the evidence.", "falsifier": "Durable conditions improve."},
            {"label": "B", "story": "The base story remains balanced.", "falsifier": "Conditions break from the base case."},
            {"label": "C", "story": "The favorable story best matches the evidence.", "falsifier": "Supportive conditions fade."},
        ],
        "analysis_lean": "C",
    }


def _semantic_evidence_items(confidence="high"):
    return [
        {
            "evidence_id": f"{driver}-support",
            "driver": driver,
            "source_title": "Semantic support packet",
            "source_url": f"https://example.com/{driver}",
            "source_date": "2026-07-01",
            "evidence_summary": f"Company-specific evidence supports the favorable {driver} story.",
            "confidence": confidence,
        }
        for driver in FOUR_LEVER_DRIVERS
    ]


def _semantic_four_lever_plan(registry, run_id, *, confidence="high"):
    return registry.call(
        "stockvaluation.plan_guided_questions",
        {
            "run_id": run_id,
            "ticker": "MSFT",
            "workflow_type": "ticker",
            "evidence_items": _semantic_evidence_items(confidence),
            "framing_forks": [_semantic_fork(driver) for driver in FOUR_LEVER_DRIVERS],
            "max_visible_questions": 4,
        },
    )["structuredContent"]["guidedQuestionPlan"]


def _favorable_semantic_answers(plan):
    answers = {}
    for question in plan["questions"]:
        answers[question["id"]] = "A" if question["driver"] == "risk_wacc" else "C"
    return answers


def _start_ticker_run(registry):
    return registry.call("stockvaluation.researched_baseline", {"ticker": "MSFT"})["structuredContent"]["run_id"]


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


def test_guided_flow_recalculate_refuses_unverified_user_input_even_after_answers_applied(tmp_path):
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
    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "UNVERIFIED_USER_INPUT"
    assert result["structuredContent"]["failureCategory"] == "unverified_user_input"


def test_clean_coherence_clears_guided_gate(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": _stock_plan(evidence_used=HIGH_SUPPORT),
            "answers": {"growth": "B", "margin": "B", "reinvestment": "B", "risk": "B"},
        },
    )["structuredContent"]

    assert applied["coherenceReview"]["status"] == "clean"
    assert applied["coherenceReview"]["issues"] == []
    assert applied["workflow_state"]["gates"][GATE_GUIDED_REFINEMENT]["status"] == "cleared"


def test_high_confidence_semantic_support_refs_clear_four_lever_coherence(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)
    plan = _semantic_four_lever_plan(registry, run_id, confidence="high")

    assert [question["framingQuality"] for question in plan["questions"]] == ["semantic"] * 4
    assert {
        question["driver"]: question["supporting_evidence_refs"]
        for question in plan["questions"]
    } == {driver: [f"{driver}-support"] for driver in FOUR_LEVER_DRIVERS}
    assert all(
        evidence["confidence"] == "high"
        for question in plan["questions"]
        for evidence in question["evidence_used"]
    )

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "answers": _favorable_semantic_answers(plan),
            "gate_records": [{"gate": GATE_EVIDENCE_REVIEW, "outcome": "approved"}],
        },
    )["structuredContent"]

    assert applied["coherenceReview"]["status"] == "clean"
    assert applied["coherenceReview"]["issues"] == []
    assert applied["workflow_state"]["gates"][GATE_GUIDED_REFINEMENT]["status"] == "cleared"
    assert all(
        evidence["confidence"] == "high"
        for answer in applied["userJudgment"]["answers"]
        for evidence in answer["evidence_used"]
    )


def test_low_confidence_semantic_support_refs_do_not_clear_four_lever_coherence(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)
    plan = _semantic_four_lever_plan(registry, run_id, confidence="low")

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "answers": _favorable_semantic_answers(plan),
            "gate_records": [{"gate": GATE_EVIDENCE_REVIEW, "outcome": "approved"}],
        },
    )["structuredContent"]

    issue = applied["coherenceReview"]["issues"][0]
    assert applied["coherenceReview"]["status"] == "challenge_required"
    assert issue["type"] == "optimistic_stack"
    assert issue["weak_support_drivers"] == FOUR_LEVER_WEAK_SUPPORT_DRIVERS


def test_optimistic_stack_challenge_leaves_guided_gate_uncleared(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": _stock_plan(),
            "answers": {"growth": "C", "margin": "C", "reinvestment": "C", "risk": "A"},
            "gate_records": [{"gate": GATE_EVIDENCE_REVIEW, "outcome": "approved"}],
        },
    )["structuredContent"]

    assert applied["coherenceReview"]["status"] == "challenge_required"
    assert applied["coherenceReview"]["issues"][0]["type"] == "optimistic_stack"
    assert applied["coherenceReview"]["issues"][0]["weak_support_drivers"] == FOUR_LEVER_WEAK_SUPPORT_DRIVERS
    assert applied["challenge_count"] == 1
    assert GATE_GUIDED_REFINEMENT in applied["workflow_state"]["gates_pending"]

    refused = registry.call(
        "stockvaluation.recalculate",
        {
            "run_id": run_id,
            "ticker": "MSFT",
            "overrides": applied["tickerOverridesCandidate"]["overrides"],
        },
    )["structuredContent"]
    assert refused["error"]["code"] == "GATE_NOT_CLEARED"
    assert refused["gate"] == GATE_GUIDED_REFINEMENT


def test_unresolved_string_support_refs_do_not_clear_four_lever_coherence(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": _stock_plan(supporting_evidence_refs=["unresolved-support"]),
            "answers": {"growth": "C", "margin": "C", "reinvestment": "C", "risk": "A"},
            "gate_records": [{"gate": GATE_EVIDENCE_REVIEW, "outcome": "approved"}],
        },
    )["structuredContent"]

    issue = applied["coherenceReview"]["issues"][0]
    assert applied["coherenceReview"]["status"] == "challenge_required"
    assert issue["type"] == "optimistic_stack"
    assert issue["weak_support_drivers"] == FOUR_LEVER_WEAK_SUPPORT_DRIVERS


def test_optimistic_stack_recalculate_cannot_strip_guided_metadata_to_bypass_gate(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": _stock_plan(),
            "answers": {"growth": "C", "margin": "C", "reinvestment": "C", "risk": "A"},
            "gate_records": [{"gate": GATE_EVIDENCE_REVIEW, "outcome": "approved"}],
        },
    )["structuredContent"]
    assert applied["coherenceReview"]["status"] == "challenge_required"
    assert applied["workflow_state"]["gates_pending"] == [GATE_GUIDED_REFINEMENT]

    stripped_overrides = {
        key: value
        for key, value in applied["tickerOverridesCandidate"]["overrides"].items()
        if key != "user_judgment"
    }

    refused = registry.call(
        "stockvaluation.recalculate",
        {"run_id": run_id, "ticker": "MSFT", "overrides": stripped_overrides},
    )["structuredContent"]

    assert refused["error"]["code"] == "GATE_NOT_CLEARED"
    assert refused["gate"] == GATE_GUIDED_REFINEMENT


def test_changed_answer_resolution_clears_after_one_challenge(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)
    plan = _stock_plan()
    registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": plan,
            "answers": {"growth": "C", "margin": "C", "reinvestment": "C", "risk": "A"},
        },
    )

    resolved = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": plan,
            "answers": {"growth": "B", "margin": "C", "reinvestment": "C", "risk": "A"},
        },
    )["structuredContent"]

    assert resolved["coherenceReview"]["status"] == "resolved_by_changed_answers"
    assert resolved["challenge_count"] == 1
    assert resolved["workflow_state"]["gates_pending"] == [GATE_EVIDENCE_REVIEW]


def test_caveat_acceptance_cannot_skip_first_coherence_challenge(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": _stock_plan(),
            "answers": {"growth": "C", "margin": "C", "reinvestment": "C", "risk": "A"},
            "accept_coherence_caveat": True,
            "coherence_caveat_reason": "User accepts the optimistic-stack caveat.",
        },
    )["structuredContent"]

    assert applied["coherenceReview"]["status"] == "challenge_required"
    assert applied["challenge_count"] == 1
    assert applied["workflow_state"]["gates"][GATE_GUIDED_REFINEMENT]["status"] == "pending"


def test_explicit_caveat_acceptance_clears_after_one_challenge(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)
    plan = _stock_plan()
    answers = {"growth": "C", "margin": "C", "reinvestment": "C", "risk": "A"}
    registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "guided_question_plan": plan, "answers": answers},
    )

    caveated = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": plan,
            "answers": answers,
            "accept_coherence_caveat": True,
            "coherence_caveat_reason": "User accepts the optimistic-stack caveat.",
        },
    )["structuredContent"]

    assert caveated["coherenceReview"]["status"] == "caveat_accepted"
    assert caveated["challenge_count"] == 1
    assert caveated["workflow_state"]["gates"][GATE_GUIDED_REFINEMENT]["outcome"] == "caveated"


def test_linked_theme_contradiction_requires_identical_scenario_keys(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)
    plan = _coherence_plan(
        _coherence_question("growth", "revenue_growth", "revenue_growth", theme_id="same_market_story"),
        _coherence_question("margin", "operating_margin", "target_operating_margin", theme_id="same_market_story"),
    )

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "guided_question_plan": plan, "answers": {"growth": "C", "margin": "A"}},
    )["structuredContent"]

    assert applied["coherenceReview"]["issues"][0]["type"] == "linked_theme_contradiction"
    assert applied["coherenceReview"]["issues"][0]["scenario_keys"] == ["high", "low"]


def test_risk_double_count_priority_and_non_overlap_waiver(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)
    plan = _coherence_plan(
        _coherence_question("growth", "revenue_growth", "revenue_growth", factor_id="ai_cycle", theme_id="same_story"),
        _coherence_question("risk", "risk_wacc", "wacc", factor_id="ai_cycle", theme_id="same_story"),
    )

    challenged = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": run_id, "guided_question_plan": plan, "answers": {"growth": "C", "risk": "A"}},
    )["structuredContent"]
    assert challenged["coherenceReview"]["issues"][0]["type"] == "risk_double_count"

    clean_run = _start_ticker_run(registry)
    waived_plan = _coherence_plan(
        _coherence_question(
            "growth",
            "revenue_growth",
            "revenue_growth",
            factor_id="ai_cycle",
            non_overlap_reason="growth captures demand; WACC captures discount-rate uncertainty",
        ),
        _coherence_question(
            "risk",
            "risk_wacc",
            "wacc",
            factor_id="ai_cycle",
            non_overlap_reason="growth captures demand; WACC captures discount-rate uncertainty",
        ),
    )
    waived = registry.call(
        "stockvaluation.apply_guided_answers",
        {"run_id": clean_run, "guided_question_plan": waived_plan, "answers": {"growth": "C", "risk": "A"}},
    )["structuredContent"]
    assert waived["coherenceReview"]["issues"] == []


def test_growth_reinvestment_mismatch_priority_before_optimistic_stack(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)

    applied = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": _stock_plan(),
            "answers": {"growth": "C", "reinvestment": "A"},
        },
    )["structuredContent"]

    assert applied["coherenceReview"]["issues"][0]["type"] == "growth_reinvestment_mismatch"


def test_inconsistent_replacement_awaits_caveat_and_hard_caps_one_challenge(tmp_path):
    registry = _registry(tmp_path)
    run_id = _start_ticker_run(registry)
    plan = _stock_plan()

    first = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": plan,
            "answers": {"growth": "C", "margin": "C", "reinvestment": "C", "risk": "A", "extra": "B"},
        },
    )["structuredContent"]
    assert first["coherenceReview"]["status"] == "challenge_required"
    assert first["challenge_count"] == 1

    replacement = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": plan,
            "answers": {"growth": "C", "margin": "C", "reinvestment": "C", "risk": "A", "extra": "C"},
        },
    )["structuredContent"]

    assert replacement["coherenceReview"]["status"] == "awaiting_caveat_acceptance"
    assert replacement["challenge_count"] == 1
    run = registry.run_store.get_run(run_id)
    assert run["coherence_challenge_count"] == 1
    assert run["coherence_review"]["issues"] == replacement["coherenceReview"]["issues"]
    assert run["coherence_requires_caveat_decision"] is True
    assert any(event["type"] == "coherence_changes_still_inconsistent" for event in run["events"])
    assert run["gates"][GATE_GUIDED_REFINEMENT]["status"] == "pending"

    rejected = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": plan,
            "answers": {"growth": "C", "margin": "C", "reinvestment": "C", "risk": "A", "extra": "A"},
        },
    )["structuredContent"]
    assert rejected["error"]["code"] == "COHERENCE_CAVEAT_DECISION_REQUIRED"

    caveated = registry.call(
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "guided_question_plan": plan,
            "answers": {"growth": "C", "margin": "C", "reinvestment": "C", "risk": "A", "extra": "C"},
            "accept_coherence_caveat": True,
        },
    )["structuredContent"]
    assert caveated["coherenceReview"]["status"] == "caveat_accepted"
    assert caveated["challenge_count"] == 1
    assert caveated["workflow_state"]["gates"][GATE_GUIDED_REFINEMENT]["status"] == "cleared"


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
                "target_operating_margin": 45.0,
                "user_judgment": USER_JUDGMENT,
                "evidence_packet": _valid_evidence_packet(confidence="low"),
            },
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
