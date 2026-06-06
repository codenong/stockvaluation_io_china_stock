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

    assert plan["planned_visible_question_count"] == 1
    assert [question["driver"] for question in plan["questions"]] == ["business_definition"]
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
