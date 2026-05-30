"""Accounting and capital-claims validation for agent-native recalculation."""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlsplit

from .security import sanitize_for_agent
from .source_provenance import RETRIEVAL_STATUSES, SOURCE_CLASSES

ACCOUNTING_SCHEMA_VERSION = "accounting_and_claims.v1"
GOVERNED_ACCOUNTING_MODE = "explicit_scenario"
RD_ALIASES = {"rd_capitalization", "r_and_d_capitalization"}
LEASE_ALIASES = {"leases", "operating_leases"}
REPORT_ONLY_TOPICS = {
    *LEASE_ALIASES,
    "sbc_dilution",
    "options",
    "warrants",
    "options_warrants",
    "nols",
    "nol_tax",
    "cash",
    "debt",
    "share_count",
    "accounting_adjustments",
}


def validate_accounting_override(
    topic: str,
    value: Any,
    request_policy_mode: str | None,
) -> dict[str, Any]:
    """Validate one accounting override before it can reach valuation-service."""
    normalized_topic = str(topic or "").strip()
    if normalized_topic in RD_ALIASES:
        return _validate_rd_capitalization(value, request_policy_mode)
    return _result(
        ok=False,
        status="blocked_report_only",
        unsupported=[
            {
                "topic": normalized_topic,
                "status": "blocked_report_only",
                "reason": f"{normalized_topic} is report-only in Phase 5; R&D capitalization is the only governed accounting scenario path.",
            }
        ],
    )


def accounting_metadata(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": ACCOUNTING_SCHEMA_VERSION,
        "ok": validation.get("ok"),
        "status": validation.get("status"),
        "accepted_mcp_inputs": validation.get("accepted_mcp_inputs", {}),
        "governed_scenarios": validation.get("governed_scenarios", []),
        "report_only_diagnostics": validation.get("report_only_diagnostics", []),
        "rejected_claims": validation.get("rejected_claims", []),
        "unsupported": validation.get("unsupported", []),
        "validation_warnings": validation.get("validation_warnings", []),
        "limitations": validation.get("limitations", []),
    }


def merge_accounting_metadata(existing: dict[str, Any] | None, validation: dict[str, Any]) -> dict[str, Any]:
    merged = existing.copy() if isinstance(existing, dict) else {
        "schema_version": ACCOUNTING_SCHEMA_VERSION,
        "ok": True,
        "status": "valid_accounting_and_claims",
        "accepted_mcp_inputs": {},
        "governed_scenarios": [],
        "report_only_diagnostics": [],
        "rejected_claims": [],
        "unsupported": [],
        "validation_warnings": [],
        "limitations": [],
    }
    metadata = accounting_metadata(validation)
    merged["ok"] = bool(merged.get("ok", True)) and bool(metadata.get("ok"))
    merged["status"] = "valid_accounting_and_claims" if merged["ok"] else "invalid_accounting_and_claims"
    merged["accepted_mcp_inputs"] = {
        **_dict(merged.get("accepted_mcp_inputs")),
        **_dict(metadata.get("accepted_mcp_inputs")),
    }
    for key in ("governed_scenarios", "report_only_diagnostics", "rejected_claims", "unsupported", "validation_warnings", "limitations"):
        merged[key] = [
            *list(merged.get(key, [])),
            *list(metadata.get(key, [])),
        ]
    return sanitize_for_agent(merged)


def _validate_rd_capitalization(value: Any, request_policy_mode: str | None) -> dict[str, Any]:
    if request_policy_mode != GOVERNED_ACCOUNTING_MODE:
        return _result(
            ok=False,
            status="blocked_report_only",
            unsupported=[
                {
                    "topic": "rd_capitalization",
                    "status": "blocked_report_only",
                    "reason": "R&D capitalization can affect recalculation only in explicit_scenario mode.",
                }
            ],
        )
    if not isinstance(value, dict):
        return _invalid_rd("rd_capitalization must be a JSON object.")
    warnings: list[str] = []
    if value.get("enabled") is not True and value.get("capitalize") is not True:
        warnings.append("rd_capitalization.enabled must be true for governed scenario support.")
    history = _valid_rd_history(value.get("rd_history"))
    if history is None:
        warnings.append("rd_capitalization.rd_history must include at least three dated positive R&D records with direct source URLs.")
    amortization_policy = _valid_amortization_policy(value.get("amortization_policy"))
    if amortization_policy is None:
        warnings.append("rd_capitalization.amortization_policy must include method and amortization_period_years.")
    provenance = _valid_source_provenance(value.get("source_provenance"))
    if provenance is None:
        warnings.append("rd_capitalization.source_provenance must include source_class, provider, source_date, and retrieved status.")
    if warnings:
        return _result(
            ok=False,
            status="invalid_accounting_and_claims",
            rejected_claims=[
                {
                    "topic": "rd_capitalization",
                    "status": "source_required",
                    "reason": " ".join(warnings),
                    "item": sanitize_for_agent(value),
                }
            ],
            unsupported=[
                {
                    "topic": "rd_capitalization",
                    "status": "source_required",
                    "reason": " ".join(warnings),
                }
            ],
            validation_warnings=warnings,
        )
    return _result(
        ok=True,
        status="valid_accounting_and_claims",
        accepted_mcp_inputs={
            "isExpensesCapitalize": True,
            "rdAmortizationMethod": amortization_policy["method"],
            "rdAmortizationPeriodYears": amortization_policy["amortization_period_years"],
        },
        governed_scenarios=[
            {
                "topic": "rd_capitalization",
                "status": "governed_scenario_supported",
                "model_action": "isExpensesCapitalize",
                "history_years": len(history or []),
                "amortization_policy": amortization_policy,
                "source_provenance": provenance,
            }
        ],
        limitations=[
            "R&D capitalization is an explicit governed scenario input; autonomous researched mode must not toggle it."
        ],
    )


def _invalid_rd(reason: str) -> dict[str, Any]:
    return _result(
        ok=False,
        status="invalid_accounting_and_claims",
        rejected_claims=[{"topic": "rd_capitalization", "status": "source_required", "reason": reason}],
        unsupported=[{"topic": "rd_capitalization", "status": "source_required", "reason": reason}],
        validation_warnings=[reason],
    )


def _valid_rd_history(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or len(value) < 3:
        return None
    records: list[dict[str, Any]] = []
    fiscal_years: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            return None
        amount = _number_or_none(item.get("amount"))
        source_url = str(item.get("source_url") or "").strip()
        source_date = str(item.get("source_date") or "").strip()
        fiscal_year = str(item.get("fiscal_year") or item.get("year") or "").strip()
        if amount is None or amount <= 0:
            return None
        if not fiscal_year or fiscal_year in fiscal_years:
            return None
        if not _is_valid_source_url(source_url) or not _is_iso_date(source_date):
            return None
        fiscal_years.add(fiscal_year)
        records.append(
            sanitize_for_agent(
                {
                    "fiscal_year": fiscal_year,
                    "amount": amount,
                    "source_url": source_url,
                    "source_date": source_date,
                }
            )
        )
    return records


def _valid_amortization_policy(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    method = str(value.get("method") or "").strip()
    period = _number_or_none(value.get("amortization_period_years"))
    if method not in {"straight_line", "service_industry_policy"}:
        return None
    if period is None or period < 2 or period > 10:
        return None
    return sanitize_for_agent(
        {
            "method": method,
            "amortization_period_years": int(period),
        }
    )


def _valid_source_provenance(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    source_class = str(value.get("source_class") or value.get("sourceClass") or "").strip()
    provider = str(value.get("provider") or "").strip()
    source_date = str(value.get("source_date") or value.get("sourceDate") or "").strip()
    retrieval_status = str(value.get("retrieval_status") or value.get("retrievalStatus") or "").strip()
    if source_class not in SOURCE_CLASSES or source_class == "yahoo_normalized":
        return None
    if not provider or not _is_iso_date(source_date):
        return None
    if retrieval_status not in RETRIEVAL_STATUSES or retrieval_status != "retrieved":
        return None
    return sanitize_for_agent(
        {
            "source_class": source_class,
            "provider": provider,
            "source_date": source_date,
            "retrieval_status": retrieval_status,
            "source_policy_status": str(value.get("source_policy_status") or value.get("sourcePolicyStatus") or "").strip(),
        }
    )


def _is_valid_source_url(value: str) -> bool:
    parts = urlsplit(value)
    return parts.scheme in {"http", "https"} and bool(parts.netloc) and "google." not in parts.netloc


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return len(value) == 10


def _number_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _result(
    *,
    ok: bool,
    status: str,
    accepted_mcp_inputs: dict[str, Any] | None = None,
    governed_scenarios: list[dict[str, Any]] | None = None,
    report_only_diagnostics: list[dict[str, Any]] | None = None,
    rejected_claims: list[dict[str, Any]] | None = None,
    unsupported: list[dict[str, Any]] | None = None,
    validation_warnings: list[str] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "accepted_mcp_inputs": accepted_mcp_inputs or {},
        "governed_scenarios": governed_scenarios or [],
        "report_only_diagnostics": report_only_diagnostics or [],
        "rejected_claims": rejected_claims or [],
        "unsupported": unsupported or [],
        "validation_warnings": validation_warnings or [],
        "limitations": limitations or [],
    }
