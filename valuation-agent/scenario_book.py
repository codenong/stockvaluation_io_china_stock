"""Scenario Book validation for agent-native valuation runs."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from typing import Any

from .security import sanitize_for_agent

SCHEMA_VERSION = "scenario_book.v1"

BOOK_STATUSES = {
    "completed",
    "completed_with_bypass",
    "insufficient_evidence",
    "blocked",
    "partial",
}

USER_FACING_SCENARIO_TYPES = {
    "evidence_constrained_base",
    "user_refined_scenario",
    "explicit_scenario",
}

REQUIRED_BOOK_FIELDS = (
    "ticker",
    "company",
    "run_mode",
    "status",
    "main_scenario_id",
    "guided_refinement",
    "scenarios",
    "diagnostics",
    "internal_references",
    "provenance_summary",
    "policy",
)

REQUIRED_SCENARIO_FIELDS = (
    "scenario_id",
    "label",
    "type",
    "status",
    "visibility",
    "source",
    "assumption_deltas",
    "assumptions",
    "payload_reference",
    "service_response_reference",
    "audit_packet_reference",
    "evidence_packet_reference",
    "provenance_references",
    "segment_economics_status",
    "accounting_claims_status",
)

ASSUMPTION_BUCKETS = (
    "requested",
    "mapped",
    "unsupported",
    "metadata",
    "effective",
)

MECHANICAL_VALUE_FIELDS = {
    "dcf",
    "valuation",
    "estimatedValuePerShare",
    "estimated_value_per_share",
    "marketPrice",
    "market_price",
    "valueOfEquity",
    "value_of_equity",
    "intrinsicValue",
    "intrinsic_value",
}

USER_REFINED_EXPLICIT_ONLY_MAPPED_FIELDS = {
    "initialCostCapital",
    "terminalGrowthRate",
    "overrideAssumptionTaxRate",
    "growthPatternOverride",
    "isExpensesCapitalize",
    "rdAmortizationMethod",
    "rdAmortizationPeriodYears",
}

DIRECT_OUTPUT_MAPPED_FIELDS = {
    "targetPrice",
    "priceTarget",
    "fairValue",
    "fairValuePerShare",
    "equityValue",
    "terminalValue",
    "intrinsicValue",
    "marketPrice",
    "upside",
    "downside",
    "cash",
    "debt",
    "shareCount",
    "numberOfShares",
}


def validate_scenario_book(book: Any) -> dict[str, Any]:
    """Validate and sanitize a Scenario Book artifact."""
    if not isinstance(book, dict):
        return _result(False, "invalid_scenario_book", {}, ["ScenarioBook must be a JSON object."])

    warnings: list[str] = []
    warnings.extend(_required_book_warnings(book))

    scenarios = _list(book.get("scenarios"))
    diagnostics = _list(book.get("diagnostics"))
    scenario_by_id = {
        str(item.get("scenario_id") or "").strip(): item
        for item in scenarios
        if isinstance(item, dict)
    }
    diagnostic_by_id = {
        str(item.get("diagnostic_id") or item.get("scenario_id") or "").strip(): item
        for item in diagnostics
        if isinstance(item, dict)
    }

    for scenario in scenarios:
        warnings.extend(_scenario_warnings(scenario))
    for diagnostic in diagnostics:
        warnings.extend(_diagnostic_warnings(diagnostic))
    warnings.extend(_guided_refinement_warnings(book, scenarios))
    warnings.extend(_main_scenario_warnings(book, scenario_by_id, diagnostic_by_id))
    warnings.extend(_mechanical_baseline_reference_warnings(book))
    warnings.extend(_policy_warnings(book))

    sanitized_book = sanitize_for_agent(book)
    sanitized_book["schema_version"] = SCHEMA_VERSION
    ok = not warnings
    return _result(
        ok,
        "valid_scenario_book" if ok else "invalid_scenario_book",
        sanitized_book,
        warnings,
    )


def scenario_book_metadata(validation: dict[str, Any]) -> dict[str, Any]:
    book = _dict(validation.get("scenario_book"))
    reference = scenario_book_reference(book)
    book_with_reference = dict(book)
    book_with_reference["scenario_book_reference"] = reference
    summary = dict(_dict(validation.get("summary")))
    summary["scenario_book_reference"] = reference
    return {
        "reference": reference,
        "summary": summary,
        "book": book_with_reference,
    }


def scenario_book_reference(book: dict[str, Any]) -> str:
    encoded = json.dumps(book, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"scenario_book:{digest}"


def _required_book_warnings(book: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for field in REQUIRED_BOOK_FIELDS:
        if field not in book:
            warnings.append(f"{field} is required.")
            continue
        value = book.get(field)
        if field in {"ticker", "company", "run_mode", "status"} and not str(value or "").strip():
            warnings.append(f"{field} is required.")
        elif field in {"scenarios", "diagnostics"} and not isinstance(value, list):
            warnings.append(f"{field} must be a list.")
        elif field in {"guided_refinement", "internal_references", "provenance_summary", "policy"} and not isinstance(value, dict):
            warnings.append(f"{field} must be a JSON object.")

    status = str(book.get("status") or "").strip()
    if status and status not in BOOK_STATUSES:
        warnings.append("status is unsupported.")
    return warnings


def _scenario_warnings(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["each scenario must be a JSON object."]
    warnings: list[str] = []
    for field in REQUIRED_SCENARIO_FIELDS:
        if field not in value:
            warnings.append(f"scenario.{field} is required.")
    scenario_type = str(value.get("type") or "").strip()
    visibility = str(value.get("visibility") or "").strip()
    if scenario_type == "mechanical_baseline" and visibility != "internal_only":
        warnings.append("mechanical_baseline cannot be a user-facing scenario.")
    if scenario_type in USER_FACING_SCENARIO_TYPES and visibility != "user_facing":
        warnings.append(f"{scenario_type} must be user_facing.")
    if scenario_type not in USER_FACING_SCENARIO_TYPES and scenario_type != "mechanical_baseline":
        warnings.append(f"{scenario_type or 'scenario'} is not a supported user-facing scenario type.")
    assumptions = value.get("assumptions")
    if not isinstance(assumptions, dict):
        warnings.append("scenario.assumptions must be a JSON object.")
    else:
        for bucket in ASSUMPTION_BUCKETS:
            if bucket not in assumptions:
                warnings.append(f"scenario.assumptions.{bucket} is required.")
        warnings.extend(_scenario_assumption_warnings(scenario_type, value, assumptions))
    for field in (
        "assumption_deltas",
        "provenance_references",
    ):
        if field in value and not isinstance(value.get(field), list):
            warnings.append(f"scenario.{field} must be a list.")
    return warnings


def _scenario_assumption_warnings(
    scenario_type: str,
    scenario: dict[str, Any],
    assumptions: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    source = str(scenario.get("source") or "").strip()
    request_mode = _scenario_request_policy_mode(assumptions)
    mapped = _dict(assumptions.get("mapped"))
    if scenario_type == "user_refined_scenario":
        if source != "guided_user_judgment":
            warnings.append("user_refined_scenario requires source guided_user_judgment.")
        if request_mode != "user_refined_scenario":
            warnings.append("user_refined_scenario requires request_policy.mode user_refined_scenario.")
        if any(field in mapped for field in USER_REFINED_EXPLICIT_ONLY_MAPPED_FIELDS):
            warnings.append("user_refined_scenario mapped payload contains explicit-scenario-only fields.")
    if scenario_type == "explicit_scenario":
        if source != "explicit_user_request":
            warnings.append("explicit_scenario requires source explicit_user_request.")
        if not str(scenario.get("explicit_user_intent") or "").strip():
            warnings.append("explicit_scenario requires explicit_user_intent.")
        if request_mode != "explicit_scenario":
            warnings.append("explicit_scenario requires request_policy.mode explicit_scenario.")
    if any(field in mapped for field in DIRECT_OUTPUT_MAPPED_FIELDS):
        warnings.append("scenario mapped payload contains direct valuation output fields.")
    return warnings


def _scenario_request_policy_mode(assumptions: dict[str, Any]) -> str | None:
    metadata = _dict(assumptions.get("metadata"))
    request_policy = _dict(metadata.get("request_policy"))
    mode = str(request_policy.get("mode") or "").strip()
    if mode:
        return mode
    mapped = _dict(assumptions.get("mapped"))
    mapped_mode = str(mapped.get("requestPolicyMode") or "").strip()
    return mapped_mode or None


def _diagnostic_warnings(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["each diagnostic must be a JSON object."]
    diagnostic_type = str(value.get("type") or "").strip()
    if diagnostic_type not in {"market_implied_diagnostic", "priced_in_diagnostic", "sensitivity_diagnostic"}:
        return []
    warnings: list[str] = []
    if str(value.get("visibility") or "").strip() != "diagnostic_only":
        warnings.append("market-implied diagnostics must be diagnostic_only.")
    if str(value.get("evidence_status") or "").strip() not in {"not_evidence", "diagnostic_only"}:
        warnings.append("market-implied diagnostics must be marked not_evidence.")
    if str(value.get("model_action") or "").strip() not in {"diagnostic_only", "report_only"}:
        warnings.append("market-implied diagnostics cannot be autonomous model changes.")
    return warnings


def _main_scenario_warnings(
    book: dict[str, Any],
    scenario_by_id: dict[str, Any],
    diagnostic_by_id: dict[str, Any],
) -> list[str]:
    main_scenario_id = str(book.get("main_scenario_id") or "").strip()
    if not main_scenario_id:
        return []
    if main_scenario_id in diagnostic_by_id:
        return ["main_scenario_id cannot point to a diagnostic entry."]
    scenario = scenario_by_id.get(main_scenario_id)
    if scenario is None:
        return ["main_scenario_id must point to a user-facing scenario."]
    scenario_type = str(scenario.get("type") or "").strip()
    visibility = str(scenario.get("visibility") or "").strip()
    warnings: list[str] = []
    if scenario_type == "mechanical_baseline":
        warnings.append("main_scenario_id cannot point to mechanical_baseline.")
    if scenario_type not in USER_FACING_SCENARIO_TYPES or visibility != "user_facing":
        warnings.append("main_scenario_id must point to a user-facing scenario.")
    return warnings


def _guided_refinement_warnings(book: dict[str, Any], scenarios: list[Any]) -> list[str]:
    guided = book.get("guided_refinement")
    if not isinstance(guided, dict):
        return []
    status = str(guided.get("status") or "").strip()
    user_refined_count = sum(
        1
        for scenario in scenarios
        if isinstance(scenario, dict) and scenario.get("type") == "user_refined_scenario"
    )
    warnings: list[str] = []
    if status == "completed":
        if user_refined_count != 1:
            warnings.append("completed guided refinement requires exactly one user_refined_scenario.")
        if not isinstance(guided.get("user_judgment"), dict):
            warnings.append("completed guided refinement requires a user_judgment package.")
        if not str(guided.get("final_recalculate_reference") or "").strip():
            warnings.append("completed guided refinement requires one final recalculate reference.")
    if status == "bypassed":
        if user_refined_count:
            warnings.append("bypassed guided refinement cannot include a user_refined_scenario.")
        if not str(guided.get("bypass_reason") or "").strip():
            warnings.append("bypassed guided refinement requires a bypass_reason.")
        if guided.get("user_judgment") is not None:
            warnings.append("bypassed guided refinement cannot include a user_judgment package.")
    return warnings


def _mechanical_baseline_reference_warnings(book: dict[str, Any]) -> list[str]:
    internal_references = book.get("internal_references")
    if not isinstance(internal_references, dict):
        return []
    mechanical = internal_references.get("mechanical_baseline")
    if mechanical is None:
        return []
    if not isinstance(mechanical, dict):
        return ["internal_references.mechanical_baseline must be a JSON object."]
    warnings: list[str] = []
    if mechanical.get("visibility") != "internal_only":
        warnings.append("internal_references.mechanical_baseline.visibility must be internal_only.")
    if any(field in mechanical for field in MECHANICAL_VALUE_FIELDS):
        warnings.append("internal_references.mechanical_baseline must contain references only, not valuation values.")
    return warnings


def _policy_warnings(book: dict[str, Any]) -> list[str]:
    policy = book.get("policy")
    if not isinstance(policy, dict):
        return []
    warnings: list[str] = []
    if policy.get("educational_use_only") is not True:
        warnings.append("policy.educational_use_only must be true.")
    if policy.get("not_financial_advice") is not True:
        warnings.append("policy.not_financial_advice must be true.")
    return warnings


def _result(ok: bool, status: str, scenario_book: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    scenarios = _list(scenario_book.get("scenarios"))
    diagnostics = _list(scenario_book.get("diagnostics"))
    main_id = str(scenario_book.get("main_scenario_id") or "").strip()
    main = next(
        (item for item in scenarios if isinstance(item, dict) and item.get("scenario_id") == main_id),
        {},
    )
    guided_refinement = _dict(scenario_book.get("guided_refinement"))
    return {
        "ok": ok,
        "status": status,
        "scenario_book": scenario_book,
        "validation_warnings": warnings,
        "summary": {
            "book_status": scenario_book.get("status"),
            "main_scenario_id": scenario_book.get("main_scenario_id"),
            "main_scenario_type": _dict(main).get("type"),
            "guided_refinement_status": guided_refinement.get("status"),
            "scenario_count": len(scenarios),
            "diagnostic_count": len(diagnostics),
        },
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []
