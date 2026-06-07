from valuation_agent.guided_question_planner import (
    build_guided_question_plan,
    build_user_judgment_package,
)
from valuation_agent.mcp_tools import MCPToolRegistry, map_recalculate_overrides


def _evidence(driver, **overrides):
    item = {
        "driver": driver,
        "source_title": "FY 2026 investor update",
        "source_url": "https://example.com/investor-update",
        "source_date": "2026-05-15",
        "evidence_summary": f"Driver-specific evidence for {driver}.",
        "direction": "supports higher assumption",
        "confidence": "high",
        "assumption_implication": "Supports a bounded guided default.",
    }
    item.update(overrides)
    return item


def test_guided_question_planner_does_not_invent_filler_questions():
    plan = build_guided_question_plan({"company": "StableCo", "workflow_type": "ticker"})

    assert plan["planned_visible_question_count"] == 0
    assert plan["questions"] == []
    assert "do not invent filler questions" in plan["question_count_rationale"]


def test_guided_question_planner_asks_one_material_question_for_simple_company():
    plan = build_guided_question_plan(
        {
            "company": "StableCo",
            "ticker": "STBL",
            "workflow_type": "ticker",
            "baseline_assumptions": {"operating_margin": 22.0},
            "evidence_items": [
                _evidence(
                    "operating_margin",
                    evidence_summary="StableCo margin expanded after a durable mix shift.",
                    override_candidate={"field": "operating_margin", "value": 24.0},
                )
            ],
        }
    )

    assert plan["planned_visible_question_count"] == 1
    question = plan["questions"][0]
    assert question["driver"] == "operating_margin"
    assert question["company_specific_title"].startswith("StableCo")
    assert question["status"] == "supported"
    assert question["model_action"] == "user scenario override"
    assert question["hidden_model_mapping"]["supported_override_field"] == "operating_margin"
    assert question["hidden_model_mapping"]["candidate_value"] == 24.0


def test_supported_non_default_choices_map_to_real_bounded_values():
    plan = build_guided_question_plan(
        {
            "company": "GrowthCo",
            "ticker": "GROW",
            "workflow_type": "ticker",
            "evidence_items": [
                _evidence(
                    "revenue_growth",
                    evidence_summary="GrowthCo backlog supports a bounded growth default.",
                    override_candidate={"field": "revenue_growth", "value": 10.0},
                )
            ],
        }
    )
    question = plan["questions"][0]
    choices = {choice["label"]: choice for choice in question["bounded_choices"]}

    assert choices["A"]["model_action"] == "user scenario override"
    assert choices["A"]["override_candidate"] == {"field": "revenue_growth", "value": 8.0}
    assert choices["C"]["model_action"] == "user scenario override"
    assert choices["C"]["override_candidate"] == {"field": "revenue_growth", "value": 12.0}

    lower_judgment = build_user_judgment_package(plan, {question["id"]: "A"})
    higher_judgment = build_user_judgment_package(plan, {question["id"]: "C"})

    assert lower_judgment["mapped_assumptions"] == {"revenue_growth": 8.0}
    assert lower_judgment["scenario_label"] == "user-refined scenario"
    assert higher_judgment["mapped_assumptions"] == {"revenue_growth": 12.0}
    assert higher_judgment["scenario_label"] == "user-refined scenario"


def test_supported_choices_respect_mcp_numeric_bounds():
    cases = [
        ("reinvestment_sales_to_capital", "sales_to_capital", 0.05, {"A": 0.05, "B": 0.05, "C": 0.06}),
        ("reinvestment_sales_to_capital", "sales_to_capital", 20.0, {"A": 16.0, "B": 20.0, "C": 20.0}),
        ("margin_path", "margin_convergence_year", 1.0, {"A": 1.0, "B": 1.0, "C": 1.2}),
        ("margin_path", "margin_convergence_year", 10.0, {"A": 8.0, "B": 10.0, "C": 10.0}),
    ]

    for driver, field, value, expected_values in cases:
        plan = build_guided_question_plan(
            {
                "company": "BoundaryCo",
                "workflow_type": "ticker",
                "evidence_items": [
                    _evidence(
                        driver,
                        evidence_summary=f"BoundaryCo evidence supports {field}.",
                        override_candidate={"field": field, "value": value},
                    )
                ],
            }
        )
        question = plan["questions"][0]
        choices = {choice["label"]: choice for choice in question["bounded_choices"]}

        for label, expected_value in expected_values.items():
            assert choices[label]["model_action"] == "user scenario override"
            assert choices[label]["override_candidate"] == {"field": field, "value": expected_value}
            judgment = build_user_judgment_package(plan, {question["id"]: label})
            mapped, unsupported, _metadata = map_recalculate_overrides(
                {
                    "request_policy": {"mode": "user_refined_scenario"},
                    **judgment["mapped_assumptions"],
                }
            )
            assert unsupported == {}
            assert mapped["requestPolicyMode"] == "user_refined_scenario"


def test_guided_question_planner_handles_complex_prospectus_as_report_only_without_recalc():
    plan = build_guided_question_plan(
        {
            "company": "Space Exploration Technologies Corp.",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": False,
            "segments": [
                {
                    "segment_name": "xAI",
                    "revenue_weight": 0.17,
                    "mapping_confidence": "low",
                }
            ],
            "evidence_items": [
                _evidence("revenue_growth", evidence_summary="xAI creates a material revenue runway question."),
                _evidence("operating_margin", evidence_summary="Starlink mature margin could differ from telecom baselines."),
                _evidence("reinvestment_sales_to_capital", evidence_summary="Satellites, rockets, and data centers need material capital."),
                _evidence("accounting_adjustments", evidence_summary="R&D capitalization is material but not cleanly modeled."),
                _evidence("terminal_value_mature_state", evidence_summary="Terminal durability drives much of the value."),
            ],
            "baseline_plausibility": {
                "unsupported_blockers": [
                    {
                        "field": "share_count",
                        "reason": "Post-offering share count requires clean pro-forma cash treatment.",
                    }
                ]
            },
        }
    )

    assert plan["planned_visible_question_count"] > 3
    assert "capital_claims" in {question["driver"] for question in plan["questions"]}
    for question in plan["questions"]:
        assert question["model_action"] in {"report-only user judgment", "unsupported"}
        assert question["hidden_model_mapping"]["supported_override_field"] is None
    assert any("Prospectus guided answers are report-only" in question["mapping_notes"] for question in plan["questions"])


def test_planner_warns_when_real_agent_compact_evidence_lacks_source_metadata():
    plan = build_guided_question_plan(
        {
            "company": "Space Exploration Technologies Corp.",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": False,
            "segments": [
                {"name": "Space", "revenueWeight": 0.2188, "mappingConfidence": "medium"},
                {"name": "Connectivity", "revenueWeight": 0.6098, "mappingConfidence": "medium"},
                {"name": "AI", "revenueWeight": 0.1714, "mappingConfidence": "low"},
            ],
            "evidence_items": [
                {
                    "driver": "cash_share_basis",
                    "fact": "Net proceeds are missing; service inferred only gross proceeds, so post-offering cash/share basis is challenged.",
                    "confidence": "high",
                },
                {
                    "driver": "growth",
                    "fact": "2025 revenue was $18.674B vs $14.015B in 2024.",
                    "confidence": "medium",
                },
                {
                    "driver": "margin",
                    "fact": "2025 operating margin was -13.86%; service baseline converges to 10.53% target margin.",
                    "confidence": "medium",
                },
                {
                    "driver": "reinvestment",
                    "fact": "2025 capex was $20.737B and R&D was $8.643B, indicating high capital intensity.",
                    "confidence": "high",
                },
            ],
        }
    )

    assert plan["planned_visible_question_count"] == 2
    assert [question["driver"] for question in plan["questions"]] == ["business_definition", "segment_mix"]
    assert plan["evidence_input_quality"]["dropped_evidence_item_count"] == 4
    assert {item["reason"] for item in plan["evidence_input_quality"]["dropped_evidence_items"]} == {"missing_source_url"}
    assert plan["planner_warnings"]
    assert "evidence item(s) were ignored" in plan["question_count_rationale"]


def test_planner_accepts_real_agent_compact_evidence_when_dated_and_cited():
    source_url = "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm"
    plan = build_guided_question_plan(
        {
            "company": "Space Exploration Technologies Corp.",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": False,
            "segments": [
                {"name": "Space", "revenueWeight": 0.2188, "mappingConfidence": "medium"},
                {"name": "Connectivity", "revenueWeight": 0.6098, "mappingConfidence": "medium"},
                {"name": "AI", "revenueWeight": 0.1714, "mappingConfidence": "low"},
            ],
            "evidence_items": [
                {
                    "driver": "cash_share_basis",
                    "fact": "Net proceeds are missing; service inferred only gross proceeds, so post-offering cash/share basis is challenged.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "high",
                },
                {
                    "driver": "segments",
                    "fact": "AI is 17.1% of revenue and unmapped; mapped segment coverage is 82.86%.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "high",
                },
                {
                    "driver": "growth",
                    "fact": "2025 revenue was $18.674B vs $14.015B in 2024.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "medium",
                },
                {
                    "driver": "margin",
                    "fact": "2025 operating margin was -13.86%; service baseline converges to 10.53% target margin.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "medium",
                },
                {
                    "driver": "reinvestment",
                    "fact": "2025 capex was $20.737B and R&D was $8.643B, indicating high capital intensity.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "high",
                },
            ],
        }
    )

    drivers = {question["driver"] for question in plan["questions"]}
    assert {
        "business_definition",
        "capital_claims",
        "revenue_growth",
        "operating_margin",
        "reinvestment_sales_to_capital",
    }.issubset(drivers)
    assert plan["planned_visible_question_count"] >= 5
    assert plan["evidence_input_quality"]["dropped_evidence_item_count"] == 0
    for question in plan["questions"]:
        assert question["model_action"] in {"report-only user judgment", "unsupported"}


def test_prospectus_recalc_requires_candidate_values_for_supported_drivers():
    source_url = "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm"
    plan = build_guided_question_plan(
        {
            "company": "Space Exploration Technologies Corp.",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": True,
            "evidence_items": [
                {
                    "driver": "growth",
                    "fact": "2025 revenue was $18.674B vs $14.015B in 2024, so revenue growth materially changes value.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "high",
                    "valueImpactPct": 80,
                }
            ],
        }
    )

    question = plan["questions"][0]
    assert question["driver"] == "revenue_growth"
    assert question["status"] == "candidate-required"
    assert question["model_action"] == "report-only user judgment"
    assert question["hidden_model_mapping"]["supported_override_field"] == "revenue_growth"
    assert plan["scenario_range"]["status"] == "candidate_values_required"
    assert plan["scenario_range"]["calculation_policy"] == "derive_or_ask_for_numeric_candidates_before_service"
    assert plan["scenario_range"]["candidate_requirements"][0]["required_field"] == "revenue_growth"

    judgment = build_user_judgment_package(plan, use_defaults=True)
    assert judgment["scenario_status"] == "candidate_values_required"
    assert judgment["mapped_assumptions"] == {}
    assert judgment["candidate_requirements"][0]["required_field"] == "revenue_growth"

    class FakeClient:
        calls = []

    result = MCPToolRegistry(FakeClient()).call(
        "stockvaluation.apply_guided_answers",
        {"guided_question_plan": plan, "use_defaults": True},
    )["structuredContent"]

    assert result["userJudgment"]["scenario_status"] == "candidate_values_required"
    assert result["prospectusScenarioCandidate"]["supported"] is False
    assert "numeric candidate values" in result["prospectusScenarioCandidate"]["reason"]
    assert result["prospectusScenarioCandidate"]["candidateRequirements"][0]["required_field"] == "revenue_growth"


def test_prospectus_user_judgment_defaults_are_not_labeled_user_refined_without_recalc():
    plan = build_guided_question_plan(
        {
            "company": "IPOCo",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": False,
            "evidence_items": [
                _evidence(
                    "revenue_growth",
                    evidence_summary="IPOCo backlog creates a material revenue question.",
                    override_candidate={"field": "revenue_growth", "value": 18.0},
                )
            ],
        }
    )

    judgment = build_user_judgment_package(plan, use_defaults=True)

    assert judgment["scenario_label"] == "report-only guided defaults"
    assert judgment["scenario_status"] == "report_only_or_unsupported"
    assert judgment["mapped_assumptions"] == {}
    assert judgment["report_only_assumptions"]
    assert plan["scenario_range"]["status"] == "not_supported"
    assert plan["scenario_range"]["calculation_policy"] == "report_only_no_service_inputs"
    assert plan["scenario_range"]["range_cases"] == []


def test_segment_business_definition_question_is_report_only_when_no_segment_payload_exists():
    plan = build_guided_question_plan(
        {
            "company": "SegmentCo",
            "workflow_type": "ticker",
            "segments": [
                {
                    "segment_name": "New Cloud",
                    "revenue_weight": 0.20,
                    "mapping_confidence": "medium",
                }
            ],
        }
    )

    question = plan["questions"][0]
    assert question["driver"] == "business_definition"
    assert question["status"] == "report-only"
    assert question["model_action"] == "report-only user judgment"
    assert question["hidden_model_mapping"]["supported_override_field"] is None

    judgment = build_user_judgment_package(plan, use_defaults=True)
    assert judgment["mapped_assumptions"] == {}
    assert judgment["report_only_assumptions"]


def test_segment_mix_preserves_sector_override_shape_for_mcp_recalculation():
    plan = build_guided_question_plan(
        {
            "company": "SegmentCo",
            "workflow_type": "ticker",
            "segments": [
                {
                    "name": "Cloud",
                    "revenueWeight": 0.55,
                    "mappingConfidence": "high",
                    "sector_override": {
                        "sector": "software-infrastructure",
                        "parameter": "operating_margin",
                        "value": 32.0,
                        "unit": "percent",
                        "adjustment_type": "absolute",
                        "timeframe": "both",
                    },
                },
                {
                    "name": "Ads",
                    "revenueWeight": 0.45,
                    "mappingConfidence": "high",
                    "sector_override": {
                        "sector": "advertising-agencies",
                        "parameter": "revenue_growth",
                        "value": 10.0,
                        "unit": "percent",
                        "adjustment_type": "absolute",
                        "timeframe": "both",
                    },
                },
            ],
        }
    )

    segment_mix = next(question for question in plan["questions"] if question["driver"] == "segment_mix")
    assert segment_mix["model_action"] == "user scenario override"

    judgment = build_user_judgment_package(plan, {segment_mix["id"]: "B"})
    assert judgment["mapped_assumptions"]["sector_overrides"] == [
        {
            "sector": "software-infrastructure",
            "parameter": "operating_margin",
            "value": 32.0,
            "unit": "percent",
            "adjustment_type": "absolute",
            "timeframe": "both",
        },
        {
            "sector": "advertising-agencies",
            "parameter": "revenue_growth",
            "value": 10.0,
            "unit": "percent",
            "adjustment_type": "absolute",
            "timeframe": "both",
        },
    ]

    mapped, unsupported, _metadata = map_recalculate_overrides(
        {
            "request_policy": {"mode": "user_refined_scenario"},
            **judgment["mapped_assumptions"],
        }
    )
    assert unsupported == {}
    assert mapped["sectorOverrides"] == [
        {
            "sectorName": "software-infrastructure",
            "parameterType": "operating_margin",
            "value": 32.0,
            "adjustmentType": "absolute",
            "timeframe": "both",
        },
        {
            "sectorName": "advertising-agencies",
            "parameterType": "revenue_growth",
            "value": 10.0,
            "adjustmentType": "absolute",
            "timeframe": "both",
        },
    ]


def test_segment_mix_unwraps_sector_overrides_candidate_for_mcp_recalculation():
    plan = build_guided_question_plan(
        {
            "company": "SegmentCo",
            "workflow_type": "ticker",
            "segments": [
                {
                    "name": "Cloud",
                    "revenueWeight": 0.50,
                    "mappingConfidence": "high",
                    "override_candidate": {
                        "field": "sector_overrides",
                        "value": [
                            {
                                "sector": "software-infrastructure",
                                "parameter": "revenue_growth",
                                "value": 10.0,
                                "unit": "percent",
                                "adjustment_type": "absolute",
                                "timeframe": "both",
                            }
                        ],
                    },
                },
                {
                    "name": "Ads",
                    "revenueWeight": 0.50,
                    "mappingConfidence": "high",
                    "sector_override": {
                        "sector": "advertising-agencies",
                        "parameter": "operating_margin",
                        "value": 20.0,
                        "unit": "percent",
                        "adjustment_type": "absolute",
                        "timeframe": "both",
                    },
                },
            ],
        }
    )

    segment_mix = next(question for question in plan["questions"] if question["driver"] == "segment_mix")
    judgment = build_user_judgment_package(plan, {segment_mix["id"]: "B"})

    assert judgment["mapped_assumptions"]["sector_overrides"] == [
        {
            "sector": "software-infrastructure",
            "parameter": "revenue_growth",
            "value": 10.0,
            "unit": "percent",
            "adjustment_type": "absolute",
            "timeframe": "both",
        },
        {
            "sector": "advertising-agencies",
            "parameter": "operating_margin",
            "value": 20.0,
            "unit": "percent",
            "adjustment_type": "absolute",
            "timeframe": "both",
        },
    ]

    _mapped, unsupported, _metadata = map_recalculate_overrides(
        {
            "request_policy": {"mode": "user_refined_scenario"},
            **judgment["mapped_assumptions"],
        }
    )
    assert unsupported == {}


def test_blocked_service_baseline_status_marks_materiality_gate_challenged():
    for baseline_use_status in ("blocked", "mechanical_only", "segment_evidence_insufficient"):
        plan = build_guided_question_plan(
            {
                "company": "BlockedCo",
                "workflow_type": "ticker",
                "baseline_plausibility": {"baselineUseStatus": baseline_use_status},
            }
        )

        assert plan["materiality_gate"]["status"] == "blocked_or_challenged"


def test_baseline_use_status_marks_gate_challenged_when_quality_looks_clean():
    plan = build_guided_question_plan(
        {
            "company": "BlockedCo",
            "workflow_type": "ticker",
            "baseline_plausibility": {
                "baselineQuality": "single_industry_fallback",
                "baselineUseStatus": "mechanical_only",
            },
        }
    )

    assert plan["materiality_gate"]["status"] == "blocked_or_challenged"
    assert plan["materiality_gate"]["baseline_quality"] == "single_industry_fallback"
    assert plan["materiality_gate"]["baseline_use_status"] == "mechanical_only"


def test_segment_mix_range_uses_default_when_structured_override_cannot_scale():
    plan = build_guided_question_plan(
        {
            "company": "SegmentCo",
            "workflow_type": "ticker",
            "segments": [
                {
                    "name": "Cloud",
                    "revenueWeight": 0.55,
                    "mappingConfidence": "high",
                    "sector_override": {
                        "sector": "software-infrastructure",
                        "parameter": "operating_margin",
                        "value": 32.0,
                        "unit": "percent",
                        "adjustment_type": "absolute",
                        "timeframe": "both",
                    },
                },
                {
                    "name": "Ads",
                    "revenueWeight": 0.45,
                    "mappingConfidence": "high",
                    "sector_override": {
                        "sector": "advertising-agencies",
                        "parameter": "revenue_growth",
                        "value": 10.0,
                        "unit": "percent",
                        "adjustment_type": "absolute",
                        "timeframe": "both",
                    },
                },
            ],
        }
    )

    for case in plan["scenario_range"]["range_cases"]:
        assert case["answer_policy"]["segment_mix_segment_mix"] == "B"
        assert len(case["mapped_assumptions"]["sector_overrides"]) == 2


def test_sector_overrides_merge_across_guided_questions():
    plan = build_guided_question_plan(
        {
            "company": "SegmentCo",
            "workflow_type": "ticker",
            "segments": [
                {
                    "name": "Cloud",
                    "revenueWeight": 0.55,
                    "mappingConfidence": "high",
                    "sector_override": {
                        "sector": "software-infrastructure",
                        "parameter": "operating_margin",
                        "value": 32.0,
                        "unit": "percent",
                        "adjustment_type": "absolute",
                        "timeframe": "both",
                    },
                },
                {
                    "name": "Ads",
                    "revenueWeight": 0.45,
                    "mappingConfidence": "high",
                    "sector_override": {
                        "sector": "advertising-agencies",
                        "parameter": "revenue_growth",
                        "value": 10.0,
                        "unit": "percent",
                        "adjustment_type": "absolute",
                        "timeframe": "both",
                    },
                },
            ],
            "evidence_items": [
                _evidence(
                    "segment_revenue_growth",
                    evidence_summary="Segment evidence supports a separate cloud growth path.",
                    override_candidate={
                        "field": "sector_overrides",
                        "value": [
                            {
                                "sector": "software-infrastructure",
                                "parameter": "revenue_growth",
                                "value": 14.0,
                                "unit": "percent",
                                "adjustment_type": "absolute",
                                "timeframe": "both",
                            }
                        ],
                    },
                )
            ],
        }
    )

    default_case = next(case for case in plan["scenario_range"]["range_cases"] if case["case_id"] == "guided_default")
    assert len(default_case["mapped_assumptions"]["sector_overrides"]) == 3

    judgment = build_user_judgment_package(plan, use_defaults=True)
    assert len(judgment["mapped_assumptions"]["sector_overrides"]) == 3


def test_segment_mix_evidence_does_not_drop_supported_segment_overrides():
    plan = build_guided_question_plan(
        {
            "company": "SegmentCo",
            "workflow_type": "ticker",
            "segments": [
                {
                    "name": "Cloud",
                    "revenueWeight": 0.55,
                    "mappingConfidence": "high",
                    "sector_override": {
                        "sector": "software-infrastructure",
                        "parameter": "operating_margin",
                        "value": 32.0,
                        "unit": "percent",
                        "adjustment_type": "absolute",
                        "timeframe": "both",
                    },
                },
                {
                    "name": "Ads",
                    "revenueWeight": 0.45,
                    "mappingConfidence": "high",
                    "sector_override": {
                        "sector": "advertising-agencies",
                        "parameter": "revenue_growth",
                        "value": 10.0,
                        "unit": "percent",
                        "adjustment_type": "absolute",
                        "timeframe": "both",
                    },
                },
            ],
            "evidence_items": [
                _evidence(
                    "segment_mix",
                    evidence_summary="Segment mix is material to growth, margin, and reinvestment.",
                    override_candidate=None,
                    valueImpactPct=50,
                )
            ],
        }
    )

    segment_mix = next(question for question in plan["questions"] if question["driver"] == "segment_mix")
    assert segment_mix["model_action"] == "user scenario override"
    assert segment_mix["hidden_model_mapping"]["supported_override_field"] == "sector_overrides"
    assert plan["scenario_range"]["status"] == "recommended"

    default_case = next(case for case in plan["scenario_range"]["range_cases"] if case["case_id"] == "guided_default")
    assert len(default_case["mapped_assumptions"]["sector_overrides"]) == 2


def test_market_implied_diagnostics_are_hidden_by_default_and_visible_in_deep_mode():
    default_plan = build_guided_question_plan(
        {
            "company": "PriceGap Inc.",
            "workflow_type": "ticker",
            "market_implied_diagnostics": {"implied_growth": 18.0},
        }
    )
    deep_plan = build_guided_question_plan(
        {
            "company": "PriceGap Inc.",
            "workflow_type": "ticker",
            "deep_mode": True,
            "market_implied_diagnostics": {"implied_growth": 18.0},
        }
    )

    assert default_plan["planned_visible_question_count"] == 0
    assert deep_plan["planned_visible_question_count"] == 1
    question = deep_plan["questions"][0]
    assert question["driver"] == "market_implied_diagnostics"
    assert question["model_action"] == "report-only user judgment"
    assert "not evidence" in question["company_specific_rationale"]


def test_market_implied_diagnostics_stay_hidden_by_default_with_high_impact():
    default_plan = build_guided_question_plan(
        {
            "company": "PriceGap Inc.",
            "workflow_type": "ticker",
            "evidence_items": [
                _evidence(
                    "market_implied_diagnostics",
                    evidence_summary="Market price implies a large growth gap.",
                    valueImpactPct=50,
                )
            ],
        }
    )
    deep_plan = build_guided_question_plan(
        {
            "company": "PriceGap Inc.",
            "workflow_type": "ticker",
            "deep_mode": True,
            "evidence_items": [
                _evidence(
                    "market_implied_diagnostics",
                    evidence_summary="Market price implies a large growth gap.",
                    valueImpactPct=50,
                )
            ],
        }
    )

    assert default_plan["planned_visible_question_count"] == 0
    assert deep_plan["planned_visible_question_count"] == 1
    assert deep_plan["questions"][0]["driver"] == "market_implied_diagnostics"


def test_weak_or_undated_evidence_does_not_create_default_questions():
    plan = build_guided_question_plan(
        {
            "company": "WeakNewsCo",
            "workflow_type": "ticker",
            "evidence_items": [
                _evidence("revenue_growth", source_date="", evidence_summary="Undated news says growth may improve."),
                _evidence("operating_margin", confidence="low", evidence_summary="Weak evidence says margin may improve."),
            ],
        }
    )

    assert plan["planned_visible_question_count"] == 0
    assert plan["questions"] == []


def test_prospectus_news_stays_report_only_even_when_recalc_support_exists():
    plan = build_guided_question_plan(
        {
            "company": "IPOCo",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": True,
            "evidence_items": [
                _evidence(
                    "revenue_growth",
                    evidence_type="company_news",
                    evidence_summary="A dated news item frames revenue uncertainty.",
                    override_candidate={"field": "revenue_growth", "value": 20.0},
                )
            ],
        }
    )

    question = plan["questions"][0]
    assert question["status"] == "report-only"
    assert question["model_action"] == "report-only user judgment"
    assert question["hidden_model_mapping"]["supported_override_field"] is None


def test_visible_question_count_is_capped_at_15():
    plan = build_guided_question_plan(
        {
            "company": "ComplexCo",
            "workflow_type": "ticker",
            "baseline_plausibility": {
                "unsupported_blockers": [
                    {"field": f"custom_driver_{index}", "reason": "Material unsupported issue."}
                    for index in range(20)
                ]
            },
        }
    )

    assert plan["candidate_question_count"] == 20
    assert plan["planned_visible_question_count"] == 15
    assert len(plan["questions"]) == 15


def test_user_judgment_package_records_defaults_without_treating_them_as_evidence():
    plan = build_guided_question_plan(
        {
            "company": "GrowthCo",
            "workflow_type": "ticker",
            "deep_mode": True,
            "evidence_items": [
                _evidence(
                    "revenue_growth",
                    evidence_summary="GrowthCo backlog supports a bounded growth default.",
                    override_candidate={"field": "revenue_growth", "value": 12.5},
                ),
                _evidence(
                    "terminal_value_mature_state",
                    evidence_summary="Terminal durability is important but report-only.",
                ),
            ],
        }
    )

    judgment = build_user_judgment_package(plan, use_defaults=True)

    assert len(judgment["answers"]) == plan["planned_visible_question_count"]
    assert judgment["mapped_assumptions"] == {"revenue_growth": 12.5}
    assert judgment["report_only_assumptions"]
    assert judgment["not_evidence_statement"] == "User answers define a scenario; they are not independent evidence."


def test_mcp_tool_exposes_read_only_guided_question_planner_without_service_call():
    class FakeClient:
        calls = []

    result = MCPToolRegistry(FakeClient()).call(
        "stockvaluation.plan_guided_questions",
        {
            "company": "StableCo",
            "ticker": "STBL",
            "workflow_type": "ticker",
            "evidence_items": [_evidence("revenue_growth")],
        },
    )

    assert result["isError"] is False
    assert result["structuredContent"]["tool"] == "stockvaluation.plan_guided_questions"
    assert result["structuredContent"]["guidedQuestionPlan"]["planned_visible_question_count"] == 1
    assert FakeClient.calls == []

    tool_names = {tool["name"] for tool in MCPToolRegistry(FakeClient()).list_tools()}
    assert "stockvaluation.plan_guided_questions" in tool_names


def test_mcp_tool_applies_guided_defaults_to_prospectus_scenario_candidate():
    class FakeClient:
        calls = []

    plan = build_guided_question_plan(
        {
            "company": "Space Exploration Technologies Corp.",
            "ticker": "SPCX",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": True,
            "evidence_items": [
                _evidence(
                    "revenue_growth",
                    source_url="https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
                    source_date="2026-06-03",
                    evidence_summary="SpaceX filing evidence supports a bounded revenue runway.",
                    override_candidate={"field": "revenue_growth", "value": 25.0},
                ),
                _evidence(
                    "operating_margin",
                    source_url="https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
                    source_date="2026-06-03",
                    evidence_summary="Segment margins support a bounded mature margin path.",
                    override_candidate={"field": "operating_margin", "value": 35.0},
                ),
                _evidence(
                    "reinvestment_sales_to_capital",
                    source_url="https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
                    source_date="2026-06-03",
                    evidence_summary="SpaceX filing capex supports high reinvestment needs.",
                    override_candidate={"field": "sales_to_capital", "value": 1.4},
                ),
            ],
        }
    )

    result = MCPToolRegistry(FakeClient()).call(
        "stockvaluation.apply_guided_answers",
        {"guided_question_plan": plan, "use_defaults": True},
    )

    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["tool"] == "stockvaluation.apply_guided_answers"
    assert structured["userJudgment"]["scenario_status"] == "recalculation_ready"
    assert structured["userJudgment"]["mapped_assumptions"] == {
        "revenue_growth": 25.0,
        "operating_margin": 35.0,
        "sales_to_capital": 1.4,
    }
    assert structured["tickerOverridesCandidate"]["supported"] is True
    assert structured["tickerOverridesCandidate"]["overrides"]["request_policy"]["mode"] == "user_refined_scenario"
    assert structured["prospectusScenarioCandidate"] == {
        "supported": True,
        "scenario": {
            "scenario_name": "guided_user_refined_scenario",
            "compound_annual_growth_2_5": 25.0,
            "target_operating_margin": 35.0,
            "sales_to_capital_years_1_to_5": 1.4,
            "sales_to_capital_years_6_to_10": 1.4,
        },
        "unsupportedMappedAssumptions": {},
        "reason": None,
    }
    assert FakeClient.calls == []

    tool_names = {tool["name"] for tool in MCPToolRegistry(FakeClient()).list_tools()}
    assert "stockvaluation.apply_guided_answers" in tool_names


def test_guided_defaults_map_prospectus_net_proceeds_to_scenario_candidate():
    class FakeClient:
        calls = []

    plan = build_guided_question_plan(
        {
            "company": "Space Exploration Technologies Corp.",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": True,
            "evidence_items": [
                _evidence(
                    "net_proceeds",
                    source_url="https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
                    source_date="2026-06-03",
                    evidence_summary="The filing discloses full-option net proceeds as a bounded per-share basis choice.",
                    override_candidate={"field": "net_proceeds", "value": 85_700_000_000.0},
                ),
            ],
        }
    )

    result = MCPToolRegistry(FakeClient()).call(
        "stockvaluation.apply_guided_answers",
        {"guided_question_plan": plan, "use_defaults": True},
    )

    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["userJudgment"]["mapped_assumptions"] == {"net_proceeds": 85_700_000_000.0}
    assert structured["prospectusScenarioCandidate"]["supported"] is True
    assert structured["prospectusScenarioCandidate"]["scenario"]["net_proceeds"] == 85_700_000_000.0


def test_guided_answers_reject_object_candidate_for_numeric_prospectus_field():
    class FakeClient:
        calls = []

    plan = {
        "workflow_type": "prospectus",
        "questions": [
            {
                "id": "margin_path_operating_margin",
                "driver": "operating_margin",
                "model_action": "user scenario override",
                "default_answer": {"choice_label": "B"},
                "bounded_choices": [
                    {
                        "label": "B",
                        "model_action": "user scenario override",
                        "override_candidate": {
                            "field": "operating_margin",
                            "value": {"bounded_default_percent": 35.0},
                        },
                    }
                ],
            }
        ],
    }

    result = MCPToolRegistry(FakeClient()).call(
        "stockvaluation.apply_guided_answers",
        {"guided_question_plan": plan, "use_defaults": True},
    )

    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["userJudgment"]["mapped_assumptions"] == {}
    assert structured["prospectusScenarioCandidate"]["supported"] is False
    assert structured["prospectusScenarioCandidate"]["scenario"] == {}


def test_materiality_gate_marks_spacex_style_prospectus_as_questions_required():
    source_url = "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm"
    plan = build_guided_question_plan(
        {
            "company": "Space Exploration Technologies Corp.",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": True,
            "baseline_plausibility": {
                "baseline_quality": "challenged",
                "unsupported_blockers": [
                    {
                        "field": "pro_forma_cash",
                        "reason": "Post-offering share count requires clean pro-forma cash treatment.",
                    }
                ],
            },
            "segments": [
                {"name": "Space", "revenueWeight": 0.2188, "mappingConfidence": "medium"},
                {"name": "Connectivity", "revenueWeight": 0.6098, "mappingConfidence": "medium"},
                {"name": "AI", "revenueWeight": 0.1714, "mappingConfidence": "low"},
            ],
            "evidence_items": [
                {
                    "driver": "growth",
                    "fact": "2036 revenue is the largest open story variable.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "high",
                    "valueImpactPct": 80,
                    "override_candidate": {"field": "revenue_growth", "value": 25.0},
                },
                {
                    "driver": "margin",
                    "fact": "Mature segment margins can differ sharply from the industry baseline.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "high",
                    "valueImpactPct": 60,
                    "override_candidate": {"field": "operating_margin", "value": 35.0},
                },
                {
                    "driver": "reinvestment",
                    "fact": "Satellites, rockets, and data centers make capital intensity material.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "high",
                    "valueImpactPct": 35,
                    "override_candidate": {"field": "sales_to_capital", "value": 1.4},
                },
                {
                    "driver": "accounting_adjustments",
                    "fact": "R&D capitalization can materially change starting operating income.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "high",
                    "valueImpactPct": 30,
                },
                {
                    "driver": "terminal_value_mature_state",
                    "fact": "Terminal growth and terminal ROIC drive long-duration valuation.",
                    "sourceUrl": source_url,
                    "sourceDate": "2026-06-03",
                    "confidence": "medium",
                    "valueImpactPct": 25,
                },
            ],
        }
    )

    drivers = {question["driver"] for question in plan["questions"]}
    assert {
        "business_definition",
        "segment_mix",
        "revenue_growth",
        "operating_margin",
        "reinvestment_sales_to_capital",
        "accounting_adjustments",
        "terminal_value_mature_state",
        "capital_claims",
    }.issubset(drivers)
    assert plan["materiality_gate"]["status"] == "blocked_or_challenged"
    assert plan["materiality_gate"]["question_policy"] == "ask_before_final_report"
    assert plan["scenario_range"]["status"] == "recommended"
    assert plan["scenario_range"]["calculation_policy"] == "deterministic_service_required"
    assert [case["case_id"] for case in plan["scenario_range"]["range_cases"]] == [
        "guided_low",
        "guided_default",
        "guided_high",
    ]
    assert any(driver["value_impact_pct"] == 80.0 for driver in plan["materiality_gate"]["fragile_drivers"])


def test_msft_like_ticker_gets_generic_segment_and_driver_questions():
    plan = build_guided_question_plan(
        {
            "company": "Microsoft Corporation",
            "ticker": "MSFT",
            "workflow_type": "ticker",
            "segments": [
                {"name": "Productivity and Business Processes", "revenueWeight": 0.33, "mappingConfidence": "high"},
                {"name": "Intelligent Cloud", "revenueWeight": 0.42, "mappingConfidence": "high"},
                {"name": "More Personal Computing", "revenueWeight": 0.25, "mappingConfidence": "medium"},
            ],
            "evidence_items": [
                _evidence(
                    "revenue_growth",
                    evidence_summary="Cloud demand creates a company-specific growth durability question.",
                    override_candidate={"field": "revenue_growth", "value": 11.0},
                    valueImpactPct=25,
                ),
                _evidence(
                    "operating_margin",
                    evidence_summary="Cloud and software mix can move mature margin above a blended baseline.",
                    override_candidate={"field": "operating_margin", "value": 42.0},
                    valueImpactPct=30,
                ),
                _evidence(
                    "reinvestment",
                    evidence_summary="AI infrastructure investment can affect how much capital is needed to grow.",
                    override_candidate={"field": "sales_to_capital", "value": 2.1},
                    valueImpactPct=20,
                ),
            ],
        }
    )

    drivers = [question["driver"] for question in plan["questions"]]
    assert "segment_mix" in drivers
    assert "revenue_growth" in drivers
    assert "operating_margin" in drivers
    assert plan["materiality_gate"]["status"] == "material_questions_required"
    assert plan["scenario_range"]["status"] == "recommended"
    default_case = next(case for case in plan["scenario_range"]["range_cases"] if case["case_id"] == "guided_default")
    assert default_case["mapped_assumptions"] == {
        "operating_margin": 42.0,
        "sales_to_capital": 2.1,
        "revenue_growth": 11.0,
    }
    assert all("Space" not in question["company_specific_title"] for question in plan["questions"])


def test_custom_choice_is_recorded_as_report_only_until_validated():
    plan = build_guided_question_plan(
        {
            "company": "GrowthCo",
            "workflow_type": "ticker",
            "evidence_items": [
                _evidence(
                    "revenue_growth",
                    evidence_summary="GrowthCo backlog supports a bounded growth default.",
                    override_candidate={"field": "revenue_growth", "value": 10.0},
                )
            ],
        }
    )
    question = plan["questions"][0]
    choices = {choice["label"]: choice for choice in question["bounded_choices"]}

    assert choices["D"]["model_action"] == "report-only user judgment"
    judgment = build_user_judgment_package(plan, {question["id"]: "D"})
    assert judgment["mapped_assumptions"] == {}
    assert judgment["report_only_assumptions"]


def test_custom_choice_preserves_unsupported_blocker_status():
    plan = build_guided_question_plan(
        {
            "company": "IPOCo",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": False,
            "baseline_plausibility": {
                "unsupported_blockers": [
                    {
                        "field": "share_count",
                        "reason": "Post-offering share count is not clean.",
                    }
                ]
            },
        }
    )
    question = plan["questions"][0]
    choices = {choice["label"]: choice for choice in question["bounded_choices"]}

    assert question["driver"] == "capital_claims"
    assert question["model_action"] == "unsupported"
    assert choices["D"]["model_action"] == "unsupported"

    judgment = build_user_judgment_package(plan, {question["id"]: "D"})
    assert judgment["report_only_assumptions"] == {}
    assert judgment["unsupported_assumptions"]
