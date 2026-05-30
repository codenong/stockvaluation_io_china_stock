import json
from pathlib import Path

from valuation_agent.scenario_book import validate_scenario_book

FIXTURES = Path(__file__).parent / "fixtures"


def _assumptions(**overrides):
    assumptions = {
        "requested": {"revenue_growth": 0.08},
        "mapped": {"compoundAnnualGrowth2_5": 8.0},
        "unsupported": {},
        "metadata": {"request_policy": {"mode": "autonomous_researched"}},
        "effective": {"revenue_growth": 7.0},
    }
    assumptions.update(overrides)
    return assumptions


def _scenario(**overrides):
    scenario = {
        "scenario_id": "evidence_base",
        "label": "Evidence-constrained base",
        "type": "evidence_constrained_base",
        "status": "completed",
        "visibility": "user_facing",
        "source": "evidence_constrained_workflow",
        "assumption_deltas": [],
        "assumptions": _assumptions(),
        "payload_reference": "payload:evidence_base",
        "service_response_reference": "service:base_response",
        "audit_packet_reference": "valuation_audit_packet:abc123",
        "evidence_packet_reference": "evidence_packet:abc123",
        "provenance_references": ["source_provenance:abc123"],
        "segment_economics_status": {"status": "revenue_only_segments"},
        "accounting_claims_status": {"schemaVersion": "accounting_and_claims.v1"},
        "warnings": [],
        "limitations": [],
    }
    scenario.update(overrides)
    return scenario


def _market_diagnostic(**overrides):
    diagnostic = {
        "diagnostic_id": "market_implied",
        "label": "Market-implied expectations",
        "type": "market_implied_diagnostic",
        "status": "available",
        "visibility": "diagnostic_only",
        "source": "market_implied_diagnostics",
        "model_action": "diagnostic_only",
        "evidence_status": "not_evidence",
        "payload_reference": "diagnostic:market_implied",
        "warnings": [],
    }
    diagnostic.update(overrides)
    return diagnostic


def _book(**overrides):
    book = {
        "ticker": "MSFT",
        "company": "Microsoft Corporation",
        "run_mode": "full_researched",
        "generated_at": "2026-05-30T18:00:00Z",
        "status": "completed",
        "main_scenario_id": "user_refined",
        "guided_refinement": {
            "status": "completed",
            "completion_mode": "answered",
            "user_judgment": {
                "source_type": "user_judgment",
                "answers": [{"question_id": "growth", "selected_choice": "B"}],
                "not_evidence_statement": "User answers define a scenario; they are not independent evidence.",
            },
            "final_recalculate_reference": "payload:user_refined",
        },
        "scenarios": [
            _scenario(),
            _scenario(
                scenario_id="user_refined",
                label="User-refined scenario",
                type="user_refined_scenario",
                source="guided_user_judgment",
                assumptions=_assumptions(
                    metadata={"request_policy": {"mode": "user_refined_scenario"}},
                    effective={"revenue_growth": 8.0},
                ),
            ),
        ],
        "diagnostics": [_market_diagnostic()],
        "internal_references": {
            "mechanical_baseline": {
                "visibility": "internal_only",
                "reference": "mechanical_baseline:abc123",
            },
            "valuation_audit_packet_reference": "valuation_audit_packet:abc123",
            "evidence_packet_reference": "evidence_packet:abc123",
            "recalculate_payload_references": ["payload:evidence_base", "payload:user_refined"],
        },
        "provenance_summary": {
            "source_classes": ["primary_filing"],
            "source_dates": ["2026-05-30"],
            "data_quality_warnings": [],
            "missing_source_families": [],
            "source_policy_status": "primary_filing_used",
        },
        "policy": {
            "educational_use_only": True,
            "not_financial_advice": True,
            "prohibited_recommendation_language": ["buy", "sell", "hold", "target price"],
        },
    }
    book.update(overrides)
    return book


def test_validate_scenario_book_accepts_valid_book_with_user_refined_main_and_market_diagnostic():
    result = validate_scenario_book(_book())

    assert result["ok"] is True
    assert result["status"] == "valid_scenario_book"
    assert result["scenario_book"]["schema_version"] == "scenario_book.v1"
    assert result["summary"] == {
        "book_status": "completed",
        "main_scenario_id": "user_refined",
        "main_scenario_type": "user_refined_scenario",
        "guided_refinement_status": "completed",
        "scenario_count": 2,
        "diagnostic_count": 1,
    }


def test_validate_scenario_book_rejects_mechanical_baseline_as_user_facing_or_main():
    mechanical_scenario = _scenario(
        scenario_id="mechanical",
        label="Mechanical baseline",
        type="mechanical_baseline",
        visibility="user_facing",
        source="mechanical_baseline",
    )

    result = validate_scenario_book(
        _book(
            main_scenario_id="mechanical",
            scenarios=[mechanical_scenario],
        )
    )

    assert result["ok"] is False
    assert "mechanical_baseline cannot be a user-facing scenario." in result["validation_warnings"]
    assert "main_scenario_id cannot point to mechanical_baseline." in result["validation_warnings"]


def test_validate_scenario_book_rejects_market_implied_diagnostic_as_main_evidence_or_model_input():
    result = validate_scenario_book(
        _book(
            main_scenario_id="market_implied",
            diagnostics=[
                _market_diagnostic(
                    visibility="user_facing",
                    evidence_status="governed_evidence",
                    model_action="autonomous_model_change",
                )
            ],
        )
    )

    assert result["ok"] is False
    assert "main_scenario_id cannot point to a diagnostic entry." in result["validation_warnings"]
    assert "market-implied diagnostics must be diagnostic_only." in result["validation_warnings"]
    assert "market-implied diagnostics must be marked not_evidence." in result["validation_warnings"]
    assert "market-implied diagnostics cannot be autonomous model changes." in result["validation_warnings"]


def test_completed_guided_refinement_requires_exactly_one_user_refined_scenario():
    no_user_scenario = validate_scenario_book(_book(scenarios=[_scenario()]))
    duplicate_user_scenarios = validate_scenario_book(
        _book(
            scenarios=[
                _scenario(),
                _scenario(scenario_id="user_refined", type="user_refined_scenario", source="guided_user_judgment"),
                _scenario(scenario_id="user_refined_2", type="user_refined_scenario", source="guided_user_judgment"),
            ]
        )
    )

    assert no_user_scenario["ok"] is False
    assert "completed guided refinement requires exactly one user_refined_scenario." in no_user_scenario["validation_warnings"]
    assert duplicate_user_scenarios["ok"] is False
    assert "completed guided refinement requires exactly one user_refined_scenario." in duplicate_user_scenarios["validation_warnings"]


def test_use_defaults_guided_path_creates_one_user_refined_scenario_from_user_judgment():
    result = validate_scenario_book(
        _book(
            guided_refinement={
                "status": "completed",
                "completion_mode": "use_defaults",
                "user_judgment": {
                    "source_type": "user_judgment",
                    "answers": [{"question_id": "margin_path", "selected_choice": "default"}],
                    "defaults_accepted": True,
                    "not_evidence_statement": "User answers define a scenario; they are not independent evidence.",
                },
                "final_recalculate_reference": "payload:user_refined",
            }
        )
    )

    assert result["ok"] is True
    user_refined = next(
        scenario
        for scenario in result["scenario_book"]["scenarios"]
        if scenario["type"] == "user_refined_scenario"
    )
    assert user_refined["assumptions"]["metadata"]["request_policy"]["mode"] == "user_refined_scenario"
    assert result["summary"]["guided_refinement_status"] == "completed"


def test_quick_bypass_records_bypass_without_fabricating_user_refined_scenario():
    result = validate_scenario_book(
        _book(
            status="completed_with_bypass",
            main_scenario_id="evidence_base",
            guided_refinement={
                "status": "bypassed",
                "bypass_reason": "quick valuation requested",
                "user_judgment": None,
            },
            scenarios=[_scenario()],
        )
    )

    assert result["ok"] is True
    assert result["summary"]["book_status"] == "completed_with_bypass"
    assert [scenario["type"] for scenario in result["scenario_book"]["scenarios"]] == ["evidence_constrained_base"]


def test_quick_bypass_rejects_fabricated_user_refined_scenario():
    result = validate_scenario_book(
        _book(
            status="completed_with_bypass",
            guided_refinement={
                "status": "bypassed",
                "bypass_reason": "quick valuation requested",
                "user_judgment": None,
            },
        )
    )

    assert result["ok"] is False
    assert "bypassed guided refinement cannot include a user_refined_scenario." in result["validation_warnings"]


def test_explicit_scenario_mode_is_distinct_from_user_refined_guided_mode():
    result = validate_scenario_book(
        _book(
            main_scenario_id="explicit_rd",
            guided_refinement={
                "status": "bypassed",
                "bypass_reason": "explicit scenario requested",
                "user_judgment": None,
            },
            scenarios=[
                _scenario(),
                _scenario(
                    scenario_id="explicit_rd",
                    label="Explicit R&D capitalization scenario",
                    type="explicit_scenario",
                    source="explicit_user_request",
                    explicit_user_intent="Model R&D capitalization with sourced multi-year history.",
                    assumptions=_assumptions(
                        requested={"rd_capitalization": {"enabled": True}},
                        mapped={
                            "requestPolicyMode": "explicit_scenario",
                            "isExpensesCapitalize": True,
                            "rdAmortizationMethod": "straight_line",
                            "rdAmortizationPeriodYears": 4,
                        },
                        metadata={"request_policy": {"mode": "explicit_scenario"}},
                        effective={"rd_capitalization": "modeled"},
                    ),
                    accounting_claims_status={
                        "schemaVersion": "accounting_and_claims.v1",
                        "rdCapitalization": {"status": "governed_scenario_supported"},
                    },
                ),
            ],
        )
    )

    assert result["ok"] is True
    assert result["summary"]["main_scenario_type"] == "explicit_scenario"


def test_explicit_scenario_rejects_guided_user_judgment_source():
    result = validate_scenario_book(
        _book(
            main_scenario_id="explicit_bad",
            scenarios=[
                _scenario(),
                _scenario(
                    scenario_id="explicit_bad",
                    type="explicit_scenario",
                    source="guided_user_judgment",
                    assumptions=_assumptions(metadata={"request_policy": {"mode": "user_refined_scenario"}}),
                ),
            ],
        )
    )

    assert result["ok"] is False
    assert "explicit_scenario requires source explicit_user_request." in result["validation_warnings"]
    assert "explicit_scenario requires request_policy.mode explicit_scenario." in result["validation_warnings"]


def test_user_refined_scenario_rejects_explicit_only_and_direct_output_fields_in_mapped_payload():
    result = validate_scenario_book(
        _book(
            scenarios=[
                _scenario(),
                _scenario(
                    scenario_id="user_refined",
                    type="user_refined_scenario",
                    source="guided_user_judgment",
                    assumptions=_assumptions(
                        mapped={
                            "requestPolicyMode": "user_refined_scenario",
                            "initialCostCapital": 8.5,
                            "terminalGrowthRate": 3.0,
                            "overrideAssumptionTaxRate": {"overrideCost": 21.0},
                            "growthPatternOverride": "THREE_STAGE",
                            "targetPrice": 500.0,
                        },
                        unsupported={
                            "wacc": {"status": "explicit_scenario_only_in_user_refined_scenario_mode"},
                            "target_price": {"status": "direct_valuation_output_rejected"},
                        },
                        metadata={"request_policy": {"mode": "user_refined_scenario"}},
                    ),
                ),
            ]
        )
    )

    assert result["ok"] is False
    assert "user_refined_scenario mapped payload contains explicit-scenario-only fields." in result["validation_warnings"]
    assert "scenario mapped payload contains direct valuation output fields." in result["validation_warnings"]


def test_partial_and_blocked_books_are_valid_without_promoting_mechanical_baseline():
    partial = validate_scenario_book(
        _book(
            status="partial",
            main_scenario_id="evidence_base",
            scenarios=[_scenario(status="partial")],
            guided_refinement={"status": "not_started", "bypass_reason": None, "user_judgment": None},
        )
    )
    blocked = validate_scenario_book(
        _book(
            status="blocked",
            main_scenario_id=None,
            scenarios=[],
            guided_refinement={"status": "not_started", "bypass_reason": None, "user_judgment": None},
            internal_references={
                "mechanical_baseline": {
                    "visibility": "internal_only",
                    "reference": "mechanical_baseline:blocked",
                }
            },
        )
    )

    assert partial["ok"] is True
    assert blocked["ok"] is True
    assert blocked["summary"]["main_scenario_id"] is None


def test_multi_segment_scenario_preserves_segment_economics_and_accounting_status():
    result = validate_scenario_book(
        _book(
            ticker="GOOGL",
            company="Alphabet Inc.",
            scenarios=[
                _scenario(
                    scenario_id="evidence_base",
                    segment_economics_status={
                        "status": "partial_economics",
                        "segment_coverage_pct": 98.0,
                        "mapped_industries": ["advertising-agencies", "software-infrastructure"],
                        "limitations": [
                            "YouTube and Other Bets sub-business economics are report-only unless directly sourced."
                        ],
                    },
                    accounting_claims_status={
                        "schemaVersion": "accounting_and_claims.v1",
                        "rdCapitalization": {"status": "source_required"},
                        "sbcDilution": {"status": "blocked_report_only"},
                    },
                ),
                _scenario(
                    scenario_id="user_refined",
                    type="user_refined_scenario",
                    source="guided_user_judgment",
                    assumptions=_assumptions(metadata={"request_policy": {"mode": "user_refined_scenario"}}),
                    segment_economics_status={
                        "status": "partial_economics",
                        "segment_coverage_pct": 98.0,
                        "mapped_industries": ["advertising-agencies", "software-infrastructure"],
                        "limitations": [
                            "Search, YouTube, subscriptions, devices, and Other Bets are not over-modeled."
                        ],
                    },
                    accounting_claims_status={
                        "schemaVersion": "accounting_and_claims.v1",
                        "rdCapitalization": {"status": "source_required"},
                        "sbcDilution": {"status": "blocked_report_only"},
                    },
                ),
            ],
        )
    )

    assert result["ok"] is True
    assert result["scenario_book"]["ticker"] == "GOOGL"
    assert result["scenario_book"]["scenarios"][0]["segment_economics_status"]["status"] == "partial_economics"


def test_phase_6_scenario_book_acceptance_fixture_covers_required_paths():
    cases = json.loads((FIXTURES / "phase_6_scenario_book_cases.json").read_text())["cases"]

    assert {case["case_id"] for case in cases} == {
        "default_guided",
        "use_defaults",
        "quick_bypass",
        "insufficient_evidence",
        "market_implied_diagnostic",
        "explicit_scenario",
        "multi_segment",
    }
    assert all("expected_status" in case for case in cases)
    assert all("mechanical_baseline_visibility" in case for case in cases)
    assert all(case["mechanical_baseline_visibility"] == "internal_only" for case in cases)
    assert any(case["guided_refinement_status"] == "bypassed" for case in cases)
    assert any(case["main_scenario_type"] == "explicit_scenario" for case in cases)
    assert any(case["segment_economics_status"] == "partial_economics" for case in cases)
