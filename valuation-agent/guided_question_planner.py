"""Materiality-driven guided valuation question planning."""

from __future__ import annotations

import math
from typing import Any

from .security import sanitize_for_agent

MAX_VISIBLE_QUESTIONS = 15
MATERIAL_VALUE_IMPACT_THRESHOLD_PCT = 20.0
PLANNING_RULE = "story_to_driver_materiality_cap_15_no_minimum"

SUPPORTED_USER_SCENARIO_FIELDS = {
    "revenue_growth",
    "operating_margin_next_year",
    "operating_margin",
    "target_operating_margin",
    "target_pre_tax_operating_margin",
    "margin_convergence_year",
    "convergence_year_margin",
    "sales_to_capital",
    "sales_to_capital_years_1_to_5",
    "sales_to_capital_years_6_to_10",
    "segments",
    "sector_overrides",
}

FIELD_BOUNDS = {
    "margin_convergence_year": (1.0, 10.0),
    "convergence_year_margin": (1.0, 10.0),
    "sales_to_capital": (0.05, 20.0),
    "sales_to_capital_years_1_to_5": (0.05, 20.0),
    "sales_to_capital_years_6_to_10": (0.05, 20.0),
}

DRIVER_TO_OVERRIDE_FIELD = {
    "revenue_growth": "revenue_growth",
    "segment_revenue_growth": "sector_overrides",
    "operating_margin": "operating_margin",
    "segment_operating_margin": "sector_overrides",
    "margin_path": "operating_margin_next_year",
    "reinvestment_sales_to_capital": "sales_to_capital",
    "segment_sales_to_capital": "sector_overrides",
    "business_definition": "segments",
    "segment_mix": "sector_overrides",
}

DRIVER_ALIASES = {
    "business_mix": "business_definition",
    "cash_share_basis": "capital_claims",
    "capital_basis": "capital_claims",
    "growth": "revenue_growth",
    "margin": "operating_margin",
    "profitability": "operating_margin",
    "reinvestment": "reinvestment_sales_to_capital",
    "capital_intensity": "reinvestment_sales_to_capital",
    "segments": "business_definition",
    "segment_mix": "segment_mix",
    "share_basis": "capital_claims",
}

QUESTION_FAMILIES = {
    "business_definition": {
        "driver": "business_definition",
        "title": "Business definition",
        "business_tension": "The valuation has to decide which businesses are real model segments and which are report-only options.",
    },
    "segment_mix": {
        "driver": "segment_mix",
        "title": "Segment mix",
        "business_tension": "The valuation has to decide whether different segments deserve different growth, margin, and reinvestment assumptions.",
    },
    "revenue_runway": {
        "driver": "revenue_growth",
        "title": "Revenue runway",
        "business_tension": "The valuation has to decide how much growth can last beyond the near-term evidence.",
    },
    "margin_path": {
        "driver": "operating_margin",
        "title": "Margin path",
        "business_tension": "The valuation has to decide whether current margins are temporary or a good guide to mature profitability.",
    },
    "reinvestment": {
        "driver": "reinvestment_sales_to_capital",
        "title": "Reinvestment needs",
        "business_tension": "The valuation has to decide how much capital is needed to support growth.",
    },
    "terminal_maturity": {
        "driver": "terminal_value_mature_state",
        "title": "Terminal maturity",
        "business_tension": "The valuation has to decide what the company looks like when it becomes mature.",
    },
    "risk": {
        "driver": "risk_wacc",
        "title": "Risk and discount rate",
        "business_tension": "The valuation has to decide whether company risk is higher or lower than the baseline.",
    },
    "accounting_cleanup": {
        "driver": "accounting_adjustments",
        "title": "Accounting cleanup",
        "business_tension": "The valuation has to decide whether accounting numbers need report-only or governed cleanup.",
    },
    "capital_claims": {
        "driver": "capital_claims",
        "title": "Capital claims and per-share basis",
        "business_tension": "The valuation has to decide whether cash, debt, claims, and shares are on a clean basis.",
    },
    "market_implied": {
        "driver": "market_implied_diagnostics",
        "title": "Market-implied sanity check",
        "business_tension": "The valuation can compare the model story to what the current price would require, but that is not evidence.",
    },
}

DRIVER_TO_FAMILY = {
    "revenue_growth": "revenue_runway",
    "segment_revenue_growth": "revenue_runway",
    "operating_margin": "margin_path",
    "segment_operating_margin": "margin_path",
    "margin_path": "margin_path",
    "reinvestment_sales_to_capital": "reinvestment",
    "segment_sales_to_capital": "reinvestment",
    "terminal_value_mature_state": "terminal_maturity",
    "risk_wacc": "risk",
    "accounting_adjustments": "accounting_cleanup",
    "capital_claims": "capital_claims",
    "business_definition": "business_definition",
    "segment_mix": "segment_mix",
    "market_implied_diagnostics": "market_implied",
}

REPORT_ONLY_DRIVERS = {
    "risk_wacc",
    "terminal_value_mature_state",
    "accounting_adjustments",
    "market_implied_diagnostics",
}

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def build_guided_question_plan(raw: dict[str, Any]) -> dict[str, Any]:
    """Build a hidden and visible guided-question plan from compact valuation context."""
    context = sanitize_for_agent(raw if isinstance(raw, dict) else {})
    company = _string(context.get("company") or context.get("company_name") or "the company")
    ticker = _string_or_none(context.get("ticker"))
    workflow_type = _workflow_type(context.get("workflow_type") or context.get("workflowType"))
    deep_mode = bool(context.get("deep_mode") or context.get("deepMode"))
    max_visible = _bounded_question_cap(context.get("max_visible_questions") or context.get("maxVisibleQuestions"))
    prospectus_recalc_supported = bool(
        context.get("prospectus_recalculate_supported") or context.get("prospectusRecalculateSupported")
    )

    candidates: list[dict[str, Any]] = []
    candidates.extend(_questions_from_segments(context, company, workflow_type, prospectus_recalc_supported))
    candidates.extend(_questions_from_evidence(context, company, workflow_type, prospectus_recalc_supported))
    candidates.extend(_questions_from_baseline_plausibility(context, company, workflow_type, prospectus_recalc_supported))
    candidates.extend(_questions_from_market_diagnostics(context, company, workflow_type, prospectus_recalc_supported))
    evidence_input_quality = _evidence_input_quality(context)

    deduped = _dedupe_questions(candidates)
    ranked = sorted(deduped, key=lambda item: (PRIORITY_ORDER.get(item["priority"], 99), -item["materiality_score"], item["id"]))
    visible = _visible_questions(ranked, deep_mode, max_visible)
    materiality_gate = _materiality_gate(context, ranked, visible, workflow_type)
    return {
        "plan_id": f"{_slug(ticker or company)}_guided_refinement",
        "company": company,
        "ticker": ticker,
        "workflow_type": workflow_type,
        "prospectus_recalculate_supported": prospectus_recalc_supported,
        "source_type": "guided_question_plan",
        "planning_rule": PLANNING_RULE,
        "question_grammar": list(QUESTION_FAMILIES.keys()),
        "candidate_question_count": len(ranked),
        "planned_visible_question_count": len(visible),
        "question_count_rationale": _question_count_rationale(visible, ranked, deep_mode, evidence_input_quality),
        "materiality_gate": materiality_gate,
        "scenario_range": _scenario_range_recommendation(materiality_gate, visible),
        "question_order": [item["id"] for item in visible],
        "questions": visible,
        "hidden_candidate_questions": ranked,
        "evidence_input_quality": evidence_input_quality,
        "planner_warnings": evidence_input_quality["planner_warnings"],
        "not_evidence_statement": "User answers define a scenario; they are not independent evidence.",
    }


def build_user_judgment_package(
    plan: dict[str, Any],
    answers: dict[str, Any] | list[dict[str, Any]] | None = None,
    *,
    use_defaults: bool = False,
) -> dict[str, Any]:
    """Convert guided answers or accepted defaults into user judgment metadata."""
    question_list = plan.get("questions") if isinstance(plan, dict) else []
    questions = [item for item in question_list if isinstance(item, dict)]
    answer_map = _answer_map(answers)
    recorded_answers: list[dict[str, Any]] = []
    requested_assumptions: dict[str, Any] = {}
    mapped_assumptions: dict[str, Any] = {}
    report_only_assumptions: dict[str, Any] = {}
    unsupported_assumptions: dict[str, Any] = {}

    for question in questions:
        question_id = _string(question.get("id"))
        selected_choice = answer_map.get(question_id)
        if selected_choice is None and use_defaults:
            selected_choice = "default"
        if selected_choice is None:
            continue

        choice = _selected_choice(question, selected_choice)
        model_action = _string(choice.get("model_action") or question.get("model_action"))
        requested_override = _dict(choice.get("override_candidate"))
        field = _string_or_none(requested_override.get("field"))
        value = requested_override.get("value")
        answer_record = {
            "question_id": question_id,
            "selected_choice": selected_choice,
            "recommended_choice": _dict(question.get("default_answer")).get("choice_label"),
            "used_recommended_choice": selected_choice in {"default", _dict(question.get("default_answer")).get("choice_label")},
            "user_note": None,
            "mapped_driver": question.get("driver"),
            "model_action": model_action,
            "requested_override": requested_override,
            "unsupported_or_report_only_reason": None,
            "confidence": choice.get("confidence") or question.get("confidence"),
        }
        if model_action == "user scenario override" and field and value is not None:
            _merge_mapped_assumption(requested_assumptions, field, value)
            _merge_mapped_assumption(mapped_assumptions, field, value)
        elif model_action == "report-only user judgment":
            answer_record["unsupported_or_report_only_reason"] = "report_only_user_judgment"
            report_only_assumptions[question_id] = {
                "driver": question.get("driver"),
                "selected_choice": selected_choice,
                "reason": "report_only_user_judgment",
            }
        else:
            answer_record["unsupported_or_report_only_reason"] = "unsupported_or_unmapped"
            unsupported_assumptions[question_id] = {
                "driver": question.get("driver"),
                "selected_choice": selected_choice,
                "reason": "unsupported_or_unmapped",
            }
        recorded_answers.append(answer_record)

    scenario_label = _scenario_label(plan, mapped_assumptions, use_defaults)
    return {
        "source_type": "user_judgment",
        "scenario_label": scenario_label,
        "scenario_status": "recalculation_ready" if mapped_assumptions else "report_only_or_unsupported",
        "answers": recorded_answers,
        "requested_assumptions": requested_assumptions,
        "mapped_assumptions": mapped_assumptions,
        "report_only_assumptions": report_only_assumptions,
        "unsupported_assumptions": unsupported_assumptions,
        "not_evidence_statement": "User answers define a scenario; they are not independent evidence.",
    }


def _questions_from_segments(
    context: dict[str, Any],
    company: str,
    workflow_type: str,
    prospectus_recalc_supported: bool,
) -> list[dict[str, Any]]:
    segments = _list(context.get("segments") or _dict(context.get("baseline")).get("segments"))
    questions: list[dict[str, Any]] = []
    material_segments = [
        item for item in segments if _number(item.get("revenue_weight") or item.get("revenueWeight") or item.get("revenue_share") or item.get("revenueShare"), 0) >= 0.1
    ]
    low_confidence_material = [
        item for item in segments if _number(item.get("revenue_weight") or item.get("revenueWeight") or item.get("revenue_share") or item.get("revenueShare"), 0) >= 0.05
        and _string(item.get("mapping_confidence") or item.get("mappingConfidence")).lower() in {"low", "unmapped", "unknown"}
    ]
    if material_segments or low_confidence_material:
        names = ", ".join(
            _string(item.get("segment_name") or item.get("segmentName") or item.get("name") or "unnamed segment")
            for item in (low_confidence_material or material_segments)[:3]
        )
        questions.append(
            _question(
                company=company,
                workflow_type=workflow_type,
                prospectus_recalc_supported=prospectus_recalc_supported,
                family="business_definition",
                driver="business_definition",
                priority="P1",
                materiality_score=88,
                rationale=f"{company} has material segment evidence that may not fit one industry baseline.",
                evidence_summary=f"Material segment(s): {names}.",
                evidence_used=[],
                baseline_assumption="Current baseline may rely on industry or mapped segment assumptions.",
                default_story="Treat material disclosed businesses separately where the service can model them.",
                override_field="segments",
                candidate_value=None,
                confidence="medium",
                priority_reason="Material segments can change growth, margin, and reinvestment assumptions.",
            )
        )
    if len(material_segments) >= 2:
        names = ", ".join(
            _string(item.get("segment_name") or item.get("segmentName") or item.get("name") or "unnamed segment")
            for item in material_segments[:4]
        )
        questions.append(
            _question(
                company=company,
                workflow_type=workflow_type,
                prospectus_recalc_supported=prospectus_recalc_supported,
                family="segment_mix",
                driver="segment_mix",
                priority="P1",
                materiality_score=84,
                rationale=f"{company} has multiple material segments whose economics may not match a single company-wide baseline.",
                evidence_summary=f"Material segments: {names}.",
                evidence_used=[],
                baseline_assumption="The current valuation may blend segments into one company-wide growth, margin, or reinvestment path.",
                default_story="Model material segments separately when their economics differ and the service contract supports the mapping.",
                override_field="sector_overrides",
                candidate_value=_segment_mix_candidate(material_segments),
                confidence="medium",
                priority_reason="Segment mix can change revenue runway, mature margins, and reinvestment needs.",
            )
        )
    return questions


def _questions_from_evidence(
    context: dict[str, Any],
    company: str,
    workflow_type: str,
    prospectus_recalc_supported: bool,
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for item in _evidence_items(context):
        driver = _evidence_driver(item)
        if not _usable_driver_evidence(item):
            continue
        family = DRIVER_TO_FAMILY.get(driver)
        if family is None:
            continue
        value_impact_pct = _evidence_value_impact_pct(item)
        material_report_only = (
            driver in REPORT_ONLY_DRIVERS
            and driver != "market_implied_diagnostics"
            and value_impact_pct is not None
            and abs(value_impact_pct) >= MATERIAL_VALUE_IMPACT_THRESHOLD_PCT
        )
        priority = "P1" if driver not in REPORT_ONLY_DRIVERS or material_report_only else "P2"
        materiality_score = 82 if priority == "P1" else 68
        if value_impact_pct is not None and abs(value_impact_pct) >= MATERIAL_VALUE_IMPACT_THRESHOLD_PCT:
            materiality_score += min(10, int(abs(value_impact_pct) / 10))
        if _string(item.get("confidence")).lower() == "high":
            materiality_score += 4
        if "material" in _string(item.get("evidence_summary") or item.get("claim")).lower():
            materiality_score += 5
        override = _dict(item.get("override_candidate") or item.get("suggested_override"))
        external_news_in_prospectus = workflow_type == "prospectus" and _is_news_evidence(item)
        override_field = None if external_news_in_prospectus else (
            _string_or_none(override.get("field")) or DRIVER_TO_OVERRIDE_FIELD.get(driver)
        )
        candidate_value = override.get("value")
        if driver == "segment_mix" and candidate_value is None:
            candidate_value = _segment_mix_candidate(_list(context.get("segments") or _dict(context.get("baseline")).get("segments")))
        questions.append(
            _question(
                company=company,
                workflow_type=workflow_type,
                prospectus_recalc_supported=prospectus_recalc_supported,
                family=family,
                driver=driver,
                priority=priority,
                materiality_score=materiality_score,
                rationale=f"{company} has driver-specific evidence for {driver.replace('_', ' ')}.",
                evidence_summary=_string(
                    _evidence_text(item)
                    or "Driver-specific evidence was provided."
                ),
                evidence_used=[_evidence_reference(item)],
                baseline_assumption=_baseline_assumption_for_driver(context, driver),
                default_story=_default_story_for_driver(company, driver),
                override_field=override_field,
                candidate_value=candidate_value,
                confidence=_confidence(item),
                priority_reason="Driver-specific evidence creates a material valuation judgment.",
                value_impact_pct=value_impact_pct,
            )
        )
    return questions


def _questions_from_baseline_plausibility(
    context: dict[str, Any],
    company: str,
    workflow_type: str,
    prospectus_recalc_supported: bool,
) -> list[dict[str, Any]]:
    plausibility = _dict(context.get("baseline_plausibility") or context.get("baselinePlausibility"))
    questions: list[dict[str, Any]] = []
    for blocker in _list(plausibility.get("unsupported_blockers") or plausibility.get("unsupportedBlockers")):
        field = _string(blocker.get("field"))
        if field in {"cash", "debt", "share_count", "shares", "pro_forma_cash", "capital_claims"}:
            questions.append(
                _question(
                    company=company,
                    workflow_type=workflow_type,
                    prospectus_recalc_supported=prospectus_recalc_supported,
                    family="capital_claims",
                    driver="capital_claims",
                    priority="P0",
                    materiality_score=96,
                    rationale=f"{company} has an unresolved capital-claims or per-share basis issue.",
                    evidence_summary=_string(blocker.get("reason") or "Capital claims or share count are not clean."),
                    evidence_used=[],
                    baseline_assumption="The current valuation basis may not be clean enough for a user-facing value.",
                    default_story="Resolve the service-side basis before treating the valuation as clean.",
                    override_field=None,
                    candidate_value=None,
                    confidence="high",
                    priority_reason="A basis issue can make the per-share value misleading.",
                )
            )
        elif field:
            family = DRIVER_TO_FAMILY.get(field, "accounting_cleanup")
            questions.append(
                _question(
                    company=company,
                    workflow_type=workflow_type,
                    prospectus_recalc_supported=prospectus_recalc_supported,
                    family=family,
                    driver=field,
                    priority="P1",
                    materiality_score=76,
                    rationale=f"{company} has an unsupported but material {field.replace('_', ' ')} issue.",
                    evidence_summary=_string(blocker.get("reason") or "Unsupported blocker was flagged."),
                    evidence_used=[],
                    baseline_assumption="The current model may leave this driver unchanged or report-only.",
                    default_story="Keep the issue visible instead of treating the baseline as clean.",
                    override_field=DRIVER_TO_OVERRIDE_FIELD.get(field),
                    candidate_value=None,
                    confidence="medium",
                    priority_reason="Unsupported material drivers should not be buried.",
                )
            )
    optimistic = _dict(plausibility.get("optimistic_assumption_stack") or plausibility.get("optimisticAssumptionStack"))
    for flag in _list(optimistic.get("flags")):
        driver = _string(flag.get("driver"))
        family = DRIVER_TO_FAMILY.get(driver)
        if family is None:
            continue
        questions.append(
            _question(
                company=company,
                workflow_type=workflow_type,
                prospectus_recalc_supported=prospectus_recalc_supported,
                family=family,
                driver=driver,
                priority="P1",
                materiality_score=80,
                rationale=f"{company}'s baseline has a challenged {driver.replace('_', ' ')} assumption.",
                evidence_summary=_string(flag.get("reason") or "Baseline plausibility flagged this driver."),
                evidence_used=[],
                baseline_assumption=_string(flag.get("baseline_value") or "Challenged baseline assumption."),
                default_story="Use a bounded scenario rather than accepting the challenged baseline silently.",
                override_field=DRIVER_TO_OVERRIDE_FIELD.get(driver),
                candidate_value=None,
                confidence="medium",
                priority_reason="Baseline plausibility flagged this as a material assumption risk.",
            )
        )
    return questions


def _questions_from_market_diagnostics(
    context: dict[str, Any],
    company: str,
    workflow_type: str,
    prospectus_recalc_supported: bool,
) -> list[dict[str, Any]]:
    diagnostics = context.get("market_implied_diagnostics") or context.get("marketImpliedDiagnostics")
    if not diagnostics:
        return []
    return [
        _question(
            company=company,
            workflow_type=workflow_type,
            prospectus_recalc_supported=prospectus_recalc_supported,
            family="market_implied",
            driver="market_implied_diagnostics",
            priority="P2",
            materiality_score=58,
            rationale=f"{company}'s market price can be compared with the model story, but it is not evidence.",
            evidence_summary="Market-implied diagnostics are available for a sanity check.",
            evidence_used=[],
            baseline_assumption="Market price is separate from intrinsic valuation assumptions.",
            default_story="Use market-implied diagnostics only to explain the gap, not to set assumptions.",
            override_field=None,
            candidate_value=None,
            confidence="medium",
            priority_reason="Useful for explanation, but not evidence and not a model override.",
        )
    ]


def _question(
    *,
    company: str,
    workflow_type: str,
    prospectus_recalc_supported: bool,
    family: str,
    driver: str,
    priority: str,
    materiality_score: int,
    rationale: str,
    evidence_summary: str,
    evidence_used: list[dict[str, Any]],
    baseline_assumption: str,
    default_story: str,
    override_field: str | None,
    candidate_value: Any,
    confidence: str,
    priority_reason: str,
    value_impact_pct: float | None = None,
) -> dict[str, Any]:
    family_info = QUESTION_FAMILIES[family]
    status, model_action, effective_override_field = _model_action(
        workflow_type,
        prospectus_recalc_supported,
        driver,
        override_field,
        candidate_value,
    )
    choices = _bounded_choices(default_story, effective_override_field, candidate_value, model_action, confidence)
    question_id = _slug(f"{family}_{driver}")
    return {
        "id": question_id,
        "family": family,
        "driver": driver,
        "priority": priority,
        "materiality_score": materiality_score,
        "value_impact_pct": value_impact_pct,
        "status": status,
        "company_specific_title": f"{company} - {family_info['title']}",
        "company_specific_rationale": rationale,
        "business_tension": family_info["business_tension"],
        "baseline_assumption": baseline_assumption,
        "evidence_basis": evidence_summary,
        "evidence_used": evidence_used,
        "default_answer": {
            "choice_label": "B",
            "why_default_selected": default_story,
            "evidence_used": evidence_summary,
            "business_impact": _business_impact(driver),
            "model_impact": _model_impact(model_action, effective_override_field),
            "confidence": confidence,
        },
        "recommended_answer": {
            "choice_label": "B",
            "rationale": default_story,
            "confidence": confidence,
            "model_action": model_action,
        },
        "bounded_choices": choices,
        "hidden_model_mapping": {
            "supported_override_field": effective_override_field,
            "candidate_value": candidate_value,
            "send_to_mcp_by_default": model_action == "user scenario override" and candidate_value is not None,
        },
        "model_action": model_action,
        "mapping_notes": _mapping_notes(model_action, effective_override_field, workflow_type),
        "unsupported_if_any": None if status == "supported" else _mapping_notes(model_action, effective_override_field, workflow_type),
        "priority_reason": priority_reason,
        "confidence": confidence,
    }


def _model_action(
    workflow_type: str,
    prospectus_recalc_supported: bool,
    driver: str,
    override_field: str | None,
    candidate_value: Any,
) -> tuple[str, str, str | None]:
    if workflow_type == "prospectus" and not prospectus_recalc_supported:
        if driver == "capital_claims":
            return "unsupported", "unsupported", None
        return "report-only", "report-only user judgment", None
    if workflow_type == "prospectus" and override_field is None:
        return "report-only", "report-only user judgment", None
    if driver in REPORT_ONLY_DRIVERS or driver in {"market_implied_diagnostics", "capital_claims"}:
        return "report-only", "report-only user judgment", None
    if override_field in SUPPORTED_USER_SCENARIO_FIELDS and _candidate_allowed_by_contract(override_field, candidate_value):
        return "supported", "user scenario override", override_field
    if override_field in SUPPORTED_USER_SCENARIO_FIELDS:
        return "report-only", "report-only user judgment", None
    return "unsupported", "unsupported", None


def _bounded_choices(default_story: str, field: str | None, value: Any, model_action: str, confidence: str) -> list[dict[str, Any]]:
    lower_value = _scaled_candidate(field, value, 0.8)
    higher_value = _scaled_candidate(field, value, 1.2)
    lower_action = _choice_model_action(model_action, field, lower_value)
    default_action = _choice_model_action(model_action, field, value)
    higher_action = _choice_model_action(model_action, field, higher_value)
    return [
        {
            "label": "A",
            "story": "Stay close to the current baseline.",
            "assumption_effect": "Lower or no company-specific departure.",
            "override_candidate": {"field": field if lower_action == "user scenario override" else None, "value": lower_value},
            "model_action": lower_action,
            "confidence": "medium",
            "report_label": "Baseline-leaning case",
        },
        {
            "label": "B",
            "story": default_story,
            "assumption_effect": "Use the recommended bounded company-specific judgment.",
            "override_candidate": {"field": field if default_action == "user scenario override" else None, "value": value},
            "model_action": default_action,
            "confidence": confidence,
            "report_label": "Recommended guided default",
        },
        {
            "label": "C",
            "story": "Use a more aggressive company-specific departure.",
            "assumption_effect": "Higher departure from the baseline; needs stronger evidence.",
            "override_candidate": {"field": field if higher_action == "user scenario override" else None, "value": higher_value},
            "model_action": higher_action,
            "confidence": "low",
            "report_label": "Higher-conviction case",
        },
        {
            "label": "D",
            "story": "Use a custom scenario note.",
            "assumption_effect": "Requires a user-supplied assumption before it can become a model override.",
            "override_candidate": {"field": None, "value": None},
            "model_action": "unsupported" if model_action == "unsupported" else "report-only user judgment",
            "confidence": "low",
            "report_label": "Custom user judgment",
        },
    ]


def _scaled_candidate(field: str | None, value: Any, factor: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return _contract_bounded_candidate(field, number * factor)


def _choice_model_action(model_action: str, field: str | None, value: Any) -> str:
    if model_action == "user scenario override" and field and _candidate_allowed_by_contract(field, value):
        return "user scenario override"
    if model_action == "user scenario override":
        return "report-only user judgment"
    return model_action


def _contract_bounded_candidate(field: str | None, value: float) -> float | None:
    if not math.isfinite(value):
        return None
    if field in FIELD_BOUNDS:
        minimum, maximum = FIELD_BOUNDS[field]
        value = max(minimum, min(maximum, value))
    return round(value, 2)


def _candidate_allowed_by_contract(field: str | None, value: Any) -> bool:
    if field is None or value is None:
        return False
    if field not in FIELD_BOUNDS:
        return True
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(number):
        return False
    minimum, maximum = FIELD_BOUNDS[field]
    return minimum <= number <= maximum


def _materiality_gate(
    context: dict[str, Any],
    ranked: list[dict[str, Any]],
    visible: list[dict[str, Any]],
    workflow_type: str,
) -> dict[str, Any]:
    plausibility = _dict(context.get("baseline_plausibility") or context.get("baselinePlausibility"))
    baseline_quality = _string(
        plausibility.get("baseline_quality")
        or plausibility.get("baselineQuality")
        or "unknown"
    )
    baseline_use_status = _string(
        plausibility.get("baseline_use_status")
        or plausibility.get("baselineUseStatus")
        or "unknown"
    )
    p0_questions = [item for item in ranked if item.get("priority") == "P0"]
    fragile_drivers = [
        _materiality_driver(item)
        for item in ranked
        if item.get("priority") in {"P0", "P1"}
    ][:MAX_VISIBLE_QUESTIONS]

    challenged_or_blocked_statuses = {
        "blocked",
        "challenged",
        "challenged_baseline",
        "mechanical_only",
        "not_calculated",
        "segment_evidence_insufficient",
        "segment_mapping_blocked",
        "unsupported_mechanical_only",
    }
    baseline_statuses = {baseline_quality, baseline_use_status}
    if p0_questions or bool(baseline_statuses & challenged_or_blocked_statuses):
        status = "blocked_or_challenged"
    elif visible:
        status = "material_questions_required"
    else:
        status = "no_material_questions"

    return {
        "status": status,
        "workflow_type": workflow_type,
        "baseline_quality": baseline_quality,
        "baseline_use_status": baseline_use_status,
        "threshold_value_impact_pct": MATERIAL_VALUE_IMPACT_THRESHOLD_PCT,
        "candidate_question_count": len(ranked),
        "visible_question_count": len(visible),
        "question_policy": "ask_before_final_report" if visible else "no_questions_required",
        "fragile_drivers": fragile_drivers,
        "blocking_driver_count": len(p0_questions),
        "supported_driver_count": sum(1 for item in visible if item.get("model_action") == "user scenario override"),
        "report_only_driver_count": sum(1 for item in visible if item.get("model_action") == "report-only user judgment"),
        "unsupported_driver_count": sum(1 for item in visible if item.get("model_action") == "unsupported"),
    }


def _scenario_range_recommendation(materiality_gate: dict[str, Any], visible: list[dict[str, Any]]) -> dict[str, Any]:
    if not visible:
        return {
            "status": "not_needed",
            "calculation_policy": "do_not_hand_compute",
            "reason": "No material guided questions were selected.",
            "drivers": [],
        }
    supported = [item for item in visible if item.get("model_action") == "user scenario override"]
    report_only = [item for item in visible if item.get("model_action") != "user scenario override"]
    if not supported:
        return {
            "status": "not_supported",
            "calculation_policy": "report_only_no_service_inputs",
            "reason": "Material guided questions exist, but none map to governed recalculation inputs.",
            "drivers": [item.get("driver") for item in visible],
            "range_cases": [],
            "supported_driver_count": 0,
            "report_only_or_unsupported_driver_count": len(report_only),
            "baseline_gate_status": materiality_gate.get("status"),
        }
    return {
        "status": "recommended",
        "calculation_policy": "deterministic_service_required",
        "reason": "Material guided questions exist; show a range only when service output or service-validated scenarios are available.",
        "drivers": [item.get("driver") for item in visible],
        "range_cases": [
            _scenario_range_case("guided_low", "Guided low case", "A", visible),
            _scenario_range_case("guided_default", "Guided default case", "B", visible),
            _scenario_range_case("guided_high", "Guided high case", "C", visible),
        ],
        "supported_driver_count": len(supported),
        "report_only_or_unsupported_driver_count": len(report_only),
        "baseline_gate_status": materiality_gate.get("status"),
    }


def _scenario_range_case(
    case_id: str,
    label: str,
    supported_choice_label: str,
    visible: list[dict[str, Any]],
) -> dict[str, Any]:
    mapped_assumptions: dict[str, Any] = {}
    answer_policy: dict[str, str] = {}
    for question in visible:
        question_id = _string(question.get("id"))
        if question.get("model_action") != "user scenario override":
            answer_policy[question_id] = "default"
            continue
        choice = _choice_by_label(question, supported_choice_label) or _choice_by_label(question, "B")
        if _string(choice.get("model_action")) != "user scenario override":
            choice = _choice_by_label(question, "B")
        override = _dict(choice.get("override_candidate") if choice else None)
        field = _string_or_none(override.get("field"))
        value = override.get("value")
        answer_policy[question_id] = _string(choice.get("label")) or supported_choice_label
        if field and value is not None and choice.get("model_action") == "user scenario override":
            _merge_mapped_assumption(mapped_assumptions, field, value)
    return {
        "case_id": case_id,
        "label": label,
        "answer_policy": answer_policy,
        "mapped_assumptions": mapped_assumptions,
        "calculation_policy": "send_mapped_assumptions_to_deterministic_service",
    }


def _materiality_driver(question: dict[str, Any]) -> dict[str, Any]:
    priority = _string(question.get("priority"))
    if priority == "P0":
        level = "blocker"
    elif priority == "P1":
        level = "material"
    elif priority == "P2":
        level = "watchlist"
    else:
        level = "hidden"
    return {
        "driver": question.get("driver"),
        "family": question.get("family"),
        "priority": priority,
        "materiality_level": level,
        "materiality_score": question.get("materiality_score"),
        "value_impact_pct": question.get("value_impact_pct"),
        "model_action": question.get("model_action"),
        "reason": question.get("priority_reason") or question.get("company_specific_rationale"),
        "report_label": question.get("company_specific_title"),
    }


def _segment_mix_candidate(segments: list[Any]) -> list[dict[str, Any]] | None:
    candidate: list[dict[str, Any]] = []
    for item in segments:
        if not isinstance(item, dict):
            continue
        override = _dict(item.get("override_candidate") or item.get("suggested_override") or item.get("sector_override"))
        if not override:
            continue
        if _string(override.get("field")) == "sector_overrides" and isinstance(override.get("value"), list):
            candidate.extend(dict(value) for value in override["value"] if isinstance(value, dict))
            continue
        candidate.append(dict(override))
    return candidate or None


def _merge_mapped_assumption(target: dict[str, Any], field: str, value: Any) -> None:
    if field == "sector_overrides" and isinstance(value, list):
        existing = target.get(field)
        if isinstance(existing, list):
            target[field] = [*existing, *value]
        else:
            target[field] = list(value)
        return
    target[field] = value


def _visible_questions(questions: list[dict[str, Any]], deep_mode: bool, max_visible: int) -> list[dict[str, Any]]:
    allowed_priorities = {"P0", "P1", "P2"} if deep_mode else {"P0", "P1"}
    return [item for item in questions if item.get("priority") in allowed_priorities][:max_visible]


def _dedupe_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for question in questions:
        key = _string(question.get("id"))
        current = best.get(key)
        if current is None or (
            PRIORITY_ORDER.get(question.get("priority"), 99),
            -int(question.get("materiality_score", 0)),
        ) < (
            PRIORITY_ORDER.get(current.get("priority"), 99),
            -int(current.get("materiality_score", 0)),
        ):
            best[key] = question
    return list(best.values())


def _question_count_rationale(
    visible: list[dict[str, Any]],
    ranked: list[dict[str, Any]],
    deep_mode: bool,
    evidence_input_quality: dict[str, Any],
) -> str:
    warning_note = ""
    dropped = int(evidence_input_quality.get("dropped_evidence_item_count", 0))
    if dropped:
        warning_note = f" {dropped} evidence item(s) were ignored because they lacked required source metadata, driver-specific text, confidence, or a supported driver."
    if not visible:
        return f"No material company-specific guided questions passed the display filter; do not invent filler questions.{warning_note}"
    hidden_count = max(0, len(ranked) - len(visible))
    mode_note = "Deep mode included P2 questions." if deep_mode else "Default mode included P0/P1 questions only."
    return f"Showing {len(visible)} material question(s). {mode_note} {hidden_count} lower-priority question(s) remain hidden or report-only.{warning_note}"


def _evidence_items(context: dict[str, Any]) -> list[dict[str, Any]]:
    packet = _dict(context.get("evidence_packet") or context.get("evidencePacket"))
    direct_items = _list(context.get("evidence_items") or context.get("evidenceItems"))
    packet_items = _list(packet.get("evidence_items") or packet.get("evidenceItems"))
    return [item for item in [*direct_items, *packet_items] if isinstance(item, dict)]


def _evidence_reference(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim": _evidence_text(item),
        "source_title": _source_title(item),
        "source_url": _source_url(item),
        "source_date": _source_date(item) or "unknown",
        "evidence_type": _string(item.get("evidence_type") or item.get("evidenceType") or item.get("source_type") or item.get("sourceType")),
        "driver": _evidence_driver(item),
        "confidence": _confidence(item),
    }


def _baseline_assumption_for_driver(context: dict[str, Any], driver: str) -> str:
    assumptions = _dict(context.get("baseline_assumptions") or context.get("baselineAssumptions") or context.get("assumptions"))
    value = assumptions.get(driver) or assumptions.get(DRIVER_TO_OVERRIDE_FIELD.get(driver, ""))
    if value is None:
        return "Baseline assumption is available in the valuation output or is not yet extracted into the planner context."
    return f"Current baseline for {driver.replace('_', ' ')}: {value}."


def _default_story_for_driver(company: str, driver: str) -> str:
    if driver in {"revenue_growth", "segment_revenue_growth"}:
        return f"Use a company-specific growth runway for {company}, but do not assume indefinite above-industry growth."
    if driver in {"operating_margin", "segment_operating_margin", "margin_path"}:
        return f"Use a bounded mature-margin path for {company}, with current profitability and operating leverage both visible."
    if driver in {"reinvestment_sales_to_capital", "segment_sales_to_capital"}:
        return f"Use a capital-intensity assumption that makes growth pay for the required reinvestment."
    if driver == "terminal_value_mature_state":
        return "Keep terminal assumptions mature and conservative unless evidence supports durable excess returns."
    if driver == "risk_wacc":
        return "Keep risk changes report-only unless a governed scenario explicitly supports them."
    if driver == "accounting_adjustments":
        return "Keep material accounting cleanup visible and report-only unless a governed service path supports it."
    return "Use the evidence-backed bounded default and keep unsupported math clearly labeled."


def _business_impact(driver: str) -> str:
    if "revenue" in driver:
        return "Changes the size of the future business."
    if "margin" in driver:
        return "Changes how much revenue converts into operating profit."
    if "capital" in driver:
        return "Changes how much reinvestment is needed to grow."
    if "terminal" in driver:
        return "Changes the mature-state story after the explicit forecast."
    if "risk" in driver:
        return "Changes how risky the cash flows are described."
    if "accounting" in driver:
        return "Changes how accounting limitations are explained."
    return "Clarifies the business story behind the valuation."


def _model_impact(model_action: str, field: str | None) -> str:
    if model_action == "user scenario override" and field:
        return f"Maps to `{field}` if the selected choice has a numeric or structured candidate value."
    if model_action == "report-only user judgment":
        return "Stays in user judgment and the report; it is not sent to recalculation."
    return "Does not change the model unless future governed support is added."


def _mapping_notes(model_action: str, field: str | None, workflow_type: str) -> str:
    if model_action == "user scenario override" and field:
        return f"Supported guided scenario field: {field}."
    if workflow_type == "prospectus":
        return "Prospectus guided answers are report-only unless a deterministic prospectus recalc path exists."
    if model_action == "report-only user judgment":
        return "This driver is report-only and must not be sent to recalculation."
    return "No governed guided-refinement mapping exists for this driver."


def _answer_map(answers: dict[str, Any] | list[dict[str, Any]] | None) -> dict[str, str]:
    if answers is None:
        return {}
    if isinstance(answers, dict):
        if "answers" in answers:
            return _answer_map(answers.get("answers"))
        return {_string(key): _string(value) for key, value in answers.items()}
    mapped: dict[str, str] = {}
    if isinstance(answers, list):
        for item in answers:
            if not isinstance(item, dict):
                continue
            question_id = _string(item.get("question_id") or item.get("id"))
            selected = _string(item.get("selected_choice") or item.get("choice") or item.get("answer"))
            if question_id and selected:
                mapped[question_id] = selected
    return mapped


def _selected_choice(question: dict[str, Any], selected: str) -> dict[str, Any]:
    default_label = _string(_dict(question.get("default_answer")).get("choice_label") or "B")
    label = default_label if selected == "default" else selected
    return _choice_by_label(question, label) or _choice_by_label(question, default_label) or {}


def _choice_by_label(question: dict[str, Any], label: str) -> dict[str, Any]:
    for choice in _list(question.get("bounded_choices")):
        if _string(choice.get("label")) == label:
            return choice
    return {}


def _scenario_label(plan: dict[str, Any], mapped_assumptions: dict[str, Any], use_defaults: bool) -> str:
    workflow_type = _string(plan.get("workflow_type")).lower()
    prospectus_recalc_supported = bool(plan.get("prospectus_recalculate_supported"))
    if workflow_type == "prospectus" and not prospectus_recalc_supported:
        return "report-only guided defaults" if use_defaults else "report-only guided judgment"
    if mapped_assumptions:
        return "user-refined scenario"
    return "report-only guided defaults" if use_defaults else "report-only guided judgment"


def _usable_driver_evidence(item: dict[str, Any]) -> bool:
    return _evidence_drop_reason(item) is None


def _evidence_input_quality(context: dict[str, Any]) -> dict[str, Any]:
    items = _evidence_items(context)
    dropped_items: list[dict[str, Any]] = []
    usable_count = 0
    for index, item in enumerate(items):
        reason = _evidence_drop_reason(item)
        if reason is None:
            usable_count += 1
            continue
        dropped_items.append(
            {
                "index": index,
                "driver": _string(item.get("driver")),
                "normalized_driver": _evidence_driver(item),
                "reason": reason,
                "text": _short_text(_evidence_text(item)),
            }
        )
    warnings = []
    if dropped_items:
        warnings.append(
            f"{len(dropped_items)} evidence item(s) were ignored by the guided-question planner. "
            "Retry with driver, evidence_summary or fact, source_url, source_date, and non-low confidence before asking the user."
        )
    return {
        "received_evidence_item_count": len(items),
        "usable_evidence_item_count": usable_count,
        "dropped_evidence_item_count": len(dropped_items),
        "dropped_evidence_items": dropped_items[:10],
        "planner_warnings": warnings,
    }


def _evidence_drop_reason(item: dict[str, Any]) -> str | None:
    driver = _evidence_driver(item)
    if not driver:
        return "missing_driver"
    if _generic_source_presence(item):
        return "generic_source_presence"
    if not _source_url(item):
        return "missing_source_url"
    if not _source_date(item):
        return "missing_source_date"
    if not _evidence_text(item):
        return "missing_driver_specific_text"
    if _confidence(item) == "low":
        return "low_confidence"
    if driver not in DRIVER_TO_FAMILY:
        return "unsupported_driver"
    return None


def _evidence_driver(item: dict[str, Any]) -> str:
    raw = _string(item.get("driver") or item.get("valuation_driver") or item.get("valuationDriver")).lower()
    return DRIVER_ALIASES.get(raw, raw)


def _evidence_text(item: dict[str, Any]) -> str:
    return _string(
        item.get("evidence_summary")
        or item.get("evidenceSummary")
        or item.get("claim")
        or item.get("fact")
        or item.get("summary")
        or item.get("assumption_implication")
        or item.get("assumptionImplication")
    )


def _evidence_value_impact_pct(item: dict[str, Any]) -> float | None:
    for key in (
        "value_impact_pct",
        "valueImpactPct",
        "estimated_value_impact_pct",
        "estimatedValueImpactPct",
        "impact_pct",
        "impactPct",
    ):
        value = item.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return None


def _source_date(item: dict[str, Any]) -> str | None:
    provenance = _dict(item.get("source_provenance") or item.get("sourceProvenance"))
    value = _string(item.get("source_date") or item.get("sourceDate") or provenance.get("source_date") or provenance.get("sourceDate"))
    if not value or value.lower() in {"unknown", "n/a", "na"}:
        return None
    return value


def _source_url(item: dict[str, Any]) -> str:
    provenance = _dict(item.get("source_provenance") or item.get("sourceProvenance"))
    return _string(item.get("source_url") or item.get("sourceUrl") or provenance.get("source_url") or provenance.get("sourceUrl"))


def _source_title(item: dict[str, Any]) -> str:
    provenance = _dict(item.get("source_provenance") or item.get("sourceProvenance"))
    return _string(
        item.get("source_title")
        or item.get("sourceTitle")
        or item.get("source_name")
        or item.get("sourceName")
        or provenance.get("provider")
    )


def _is_news_evidence(item: dict[str, Any]) -> bool:
    evidence_type = _string(item.get("evidence_type") or item.get("evidenceType") or item.get("source_type") or item.get("sourceType")).lower()
    source_family = _string(item.get("source_family") or item.get("sourceFamily") or item.get("family")).lower()
    return evidence_type in {"company_news", "material_news", "latest_news", "news"} or source_family in {
        "material_news",
        "latest_news_research",
    }


def _generic_source_presence(item: dict[str, Any]) -> bool:
    text = _evidence_text(item).lower()
    return any(phrase in text for phrase in ("10-k found", "earnings release found", "sec filing source captured"))


def _short_text(raw: str, limit: int = 180) -> str:
    value = _string(raw)
    return value if len(value) <= limit else f"{value[: limit - 3]}..."


def _confidence(item: dict[str, Any]) -> str:
    value = _string(item.get("confidence")).lower()
    return value if value in {"low", "medium", "high"} else "medium"


def _workflow_type(raw: Any) -> str:
    value = _string(raw).lower()
    return value if value in {"ticker", "prospectus"} else "ticker"


def _bounded_question_cap(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = MAX_VISIBLE_QUESTIONS
    return max(0, min(MAX_VISIBLE_QUESTIONS, value))


def _dict(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _list(raw: Any) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _number(raw: Any, default: float) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _string(raw: Any) -> str:
    return str(raw or "").strip()


def _string_or_none(raw: Any) -> str | None:
    value = _string(raw)
    return value or None


def _slug(raw: str) -> str:
    value = "".join(char.lower() if char.isalnum() else "_" for char in raw)
    value = "_".join(part for part in value.split("_") if part)
    return value or "guided_question"
