"""Evidence packet validation for agent-native researched valuations."""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlsplit

from .security import sanitize_for_agent

GOVERNED_DRIVERS = {
    "revenue_growth",
    "operating_margin",
    "reinvestment_sales_to_capital",
}
REPORT_ONLY_DRIVERS = {
    "risk_wacc",
    "terminal_value_mature_state",
    "accounting_adjustments",
}
SUPPORTED_DRIVERS = GOVERNED_DRIVERS | REPORT_ONLY_DRIVERS
GOVERNED_ACTION = "governed assumption change"
STALE_EVIDENCE_DAYS = 550
SUPPORTED_SOURCE_FAMILIES = {
    "annual_report",
    "quarterly_report_or_earnings_release",
    "investor_presentation_or_transcript",
    "segment_disclosure",
    "material_news",
    "macro_risk",
    "filings_annual_report_research",
    "earnings_ir_research",
    "latest_news_research",
    "segment_evidence_research",
    "macro_risk_research",
}
SUPPORTED_SOURCE_FAMILY_STATUSES = {
    "checked",
    "missing",
    "unavailable",
    "not_applicable",
}
SUPPORTED_SOURCES_CHECKED_STATUSES = {
    "checked",
    "retrieved",
    "used",
    "not_used",
    "missing",
    "unavailable",
    "not_applicable",
}
SUPPORTED_SOURCE_TYPES = {
    "filing",
    "annual_report",
    "earnings",
    "presentation",
    "transcript",
    "company_news",
    "macro",
    "segment",
}
GENERIC_SOURCE_PHRASES = {
    "10-k found",
    "earnings release found",
    "investor presentation available",
    "sec filing source captured",
    "the company has a risk factors section",
}


def validate_evidence_packet(packet: Any) -> dict[str, Any]:
    """Validate and sanitize a compact research evidence packet."""
    if not isinstance(packet, dict):
        return _result(
            ok=False,
            status="invalid_packet",
            sanitized_packet={},
            validation_warnings=["EvidencePacket must be a JSON object."],
        )

    sanitized_packet = sanitize_for_agent(packet)
    packet_warnings = (
        _packet_validation_warnings(packet)
        + _source_family_validation_warnings(packet)
        + _sources_checked_validation_warnings(packet)
    )
    validation_warnings = list(packet_warnings)
    source_family_status = [
        _sanitize_source_family(item)
        for item in packet.get("source_families", [])
        if isinstance(item, dict)
    ]
    governed_evidence: list[dict[str, Any]] = []
    report_only_evidence: list[dict[str, Any]] = []
    rejected_evidence: list[dict[str, Any]] = []
    unsupported_blockers: list[dict[str, Any]] = []
    for item in packet.get("evidence_items", []):
        if not isinstance(item, dict):
            rejected_evidence.append(
                {
                    "item": sanitize_for_agent(item),
                    "status": "invalid_evidence_item",
                    "reason": "Evidence item must be a JSON object.",
                }
            )
            continue
        sanitized_item = _sanitize_evidence_item(item)
        missing_reason = _missing_evidence_reason(item, sanitized_item)
        if missing_reason is not None:
            rejected_evidence.append(
                {
                    "item": sanitized_item,
                    "status": "missing_required_evidence_field",
                    "reason": missing_reason,
                }
            )
            continue
        rejection = _evidence_rejection(sanitized_item)
        if rejection is not None:
            rejected_evidence.append({"item": sanitized_item, **rejection})
            continue
        strength_rejection = _governed_strength_rejection(packet, sanitized_item)
        if strength_rejection is not None:
            rejected_evidence.append({"item": sanitized_item, **strength_rejection})
            continue
        classification = _classify_evidence(sanitized_item)
        if classification == "governed":
            governed_evidence.append(sanitized_item)
        elif classification == "report_only":
            report_only_evidence.append(sanitized_item)
        else:
            reason = (
                f"{sanitized_item['driver']} is report-only in autonomous researched evidence validation."
            )
            rejected_evidence.append(
                {
                    "item": sanitized_item,
                    "status": "unsupported_governed_driver",
                    "reason": reason,
                }
            )
            unsupported_blockers.append(
                {
                    "field": sanitized_item["driver"],
                    "status": "unsupported_governed_driver",
                    "reason": reason,
                }
            )

    governed_evidence, conflict_rejections = _reject_conflicting_governed_evidence(governed_evidence)
    rejected_evidence.extend(conflict_rejections)

    fatal_rejected_statuses = {
        "missing_required_evidence_field",
        "generic_source_presence",
        "search_result_url",
        "unsupported_driver",
        "invalid_source_url",
        "invalid_source_date",
    }
    fatal_rejected = any(item["status"] in fatal_rejected_statuses for item in rejected_evidence)
    if not governed_evidence and any(_is_soft_no_change_rejection(item) for item in rejected_evidence):
        validation_warnings.append(
            "No governed evidence accepted; weak, mixed, stale, or undated evidence is report context only."
        )
    ok = not packet_warnings and not fatal_rejected and not unsupported_blockers
    status = "valid_governed_evidence" if governed_evidence else "valid_no_governed_change"
    if packet_warnings or fatal_rejected:
        status = "invalid_packet"
    elif unsupported_blockers:
        status = "blocked_by_unsupported_fields"
    return _result(
        ok=ok,
        status=status,
        sanitized_packet=sanitized_packet,
        governed_evidence=governed_evidence,
        report_only_evidence=report_only_evidence,
        rejected_evidence=rejected_evidence,
        source_family_status=source_family_status,
        validation_warnings=validation_warnings,
        unsupported_blockers=unsupported_blockers,
    )


def _packet_validation_warnings(packet: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for key in ("ticker", "company", "run_mode"):
        if not str(packet.get(key) or "").strip():
            warnings.append(f"{key} is required.")
    for key in ("source_families", "sources_checked", "evidence_items"):
        if not isinstance(packet.get(key), list) or not packet.get(key):
            if key == "source_families":
                warnings.append("source_families must contain at least one source-family status.")
            else:
                warnings.append(f"{key} must contain at least one item.")
    return warnings


def _source_family_validation_warnings(packet: dict[str, Any]) -> list[str]:
    raw_families = packet.get("source_families")
    if not isinstance(raw_families, list):
        return []

    warnings: list[str] = []
    for index, raw in enumerate(raw_families):
        if not isinstance(raw, dict):
            warnings.append(f"source_families[{index}] must be a JSON object.")
            continue
        family = str(raw.get("family") or "").strip()
        status = str(raw.get("status") or "").strip().lower()
        source_url = str(raw.get("source_url") or "").strip()
        source_date = str(raw.get("source_date") or "").strip()
        if not family or not status:
            warnings.append(f"source_families[{index}] requires family and status.")
            continue
        if family not in SUPPORTED_SOURCE_FAMILIES:
            warnings.append(f"source_families[{index}].family is unsupported.")
        if status not in SUPPORTED_SOURCE_FAMILY_STATUSES:
            warnings.append(f"source_families[{index}].status is unsupported.")
        if status == "checked" and (
            not _is_valid_source_url(source_url) or not _is_valid_source_date(source_date, allow_unknown=False)
        ):
            warnings.append(
                f"source_families[{index}] checked status requires direct source_url and source_date."
            )
    return warnings


def _sources_checked_validation_warnings(packet: dict[str, Any]) -> list[str]:
    raw_sources = packet.get("sources_checked")
    if not isinstance(raw_sources, list):
        return []

    warnings: list[str] = []
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict):
            warnings.append(f"sources_checked[{index}] must be a JSON object.")
            continue
        source_url = str(raw.get("source_url") or "").strip()
        source_reference = str(raw.get("source_reference") or raw.get("reference") or "").strip()
        source_date = str(raw.get("source_date") or "").strip()
        status = str(raw.get("status") or raw.get("source_status") or "").strip().lower()
        source_type = str(raw.get("source_type") or raw.get("type") or "").strip()

        if source_url:
            if not _is_valid_source_url(source_url):
                warnings.append(f"sources_checked[{index}] requires a direct source_url or source_reference.")
        elif not source_reference:
            warnings.append(f"sources_checked[{index}] requires a direct source_url or source_reference.")

        if not _is_valid_source_date(source_date):
            warnings.append(f"sources_checked[{index}].source_date must be YYYY-MM-DD or unknown.")
        if not status:
            warnings.append(f"sources_checked[{index}].status is required.")
        elif status not in SUPPORTED_SOURCES_CHECKED_STATUSES:
            warnings.append(f"sources_checked[{index}].status is unsupported.")
        if source_type and source_type not in SUPPORTED_SOURCE_TYPES:
            warnings.append(f"sources_checked[{index}].source_type is unsupported.")
    return warnings


def _sanitize_source_family(item: dict[str, Any]) -> dict[str, Any]:
    family = {
        "family": str(item.get("family") or "").strip(),
        "status": str(item.get("status") or "").strip(),
    }
    source_title = str(item.get("source_title") or item.get("source_name") or "").strip()
    source_url = str(item.get("source_url") or "").strip()
    source_date = str(item.get("source_date") or "").strip()
    reason = str(item.get("reason") or "").strip()
    if source_title:
        family["source_title"] = source_title
    if source_url:
        family["source_url"] = source_url
    if source_date:
        family["source_date"] = source_date
    if reason:
        family["reason"] = reason
    return sanitize_for_agent(family)


def _sanitize_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    return sanitize_for_agent(
        {
            "driver": str(item.get("driver") or "").strip(),
            "source_title": str(item.get("source_title") or item.get("source_name") or "").strip(),
            "source_url": str(item.get("source_url") or "").strip(),
            "source_date": str(item.get("source_date") or "").strip(),
            "evidence_summary": str(item.get("evidence_summary") or item.get("claim") or "").strip(),
            "direction": str(item.get("direction") or "").strip(),
            "confidence": str(item.get("confidence") or "").strip(),
            "assumption_implication": str(item.get("assumption_implication") or "").strip(),
            "allowed_to_affect_autonomous_recalculation": bool(
                item.get("allowed_to_affect_autonomous_recalculation")
            ),
            "model_action": str(item.get("model_action") or "").strip(),
        }
    )


def _missing_evidence_reason(raw: dict[str, Any], item: dict[str, Any]) -> str | None:
    for key in (
        "driver",
        "source_title",
        "source_url",
        "source_date",
        "evidence_summary",
        "direction",
        "confidence",
        "assumption_implication",
        "model_action",
    ):
        if not item[key]:
            return f"{key} is required."
    if "allowed_to_affect_autonomous_recalculation" not in raw or not isinstance(
        raw.get("allowed_to_affect_autonomous_recalculation"), bool
    ):
        return "allowed_to_affect_autonomous_recalculation is required."
    return None


def _classify_evidence(item: dict[str, Any]) -> str:
    if item["model_action"] == GOVERNED_ACTION and item["allowed_to_affect_autonomous_recalculation"]:
        if item["driver"] in GOVERNED_DRIVERS:
            return "governed"
        return "unsupported_governed"
    return "report_only"


def _evidence_rejection(item: dict[str, Any]) -> dict[str, str] | None:
    if item["driver"] not in SUPPORTED_DRIVERS:
        return {
            "status": "unsupported_driver",
            "reason": f"{item['driver']} is not a supported EvidencePacket driver.",
        }
    if _is_search_result_url(item["source_url"]):
        return {
            "status": "search_result_url",
            "reason": "source_url must be a direct source URL, not a search-result URL.",
        }
    if not _is_valid_source_url(item["source_url"]):
        return {
            "status": "invalid_source_url",
            "reason": "source_url must be a valid http(s) direct source URL.",
        }
    if not _is_valid_source_date(item["source_date"]):
        return {
            "status": "invalid_source_date",
            "reason": "source_date must be YYYY-MM-DD or unknown.",
        }
    if _is_generic_source_presence(item["evidence_summary"]):
        return {
            "status": "generic_source_presence",
            "reason": "Generic source presence is not valuation-driver evidence.",
        }
    return None


def _is_valid_source_url(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not _is_search_result_url(url)


def _is_valid_source_date(value: str, *, allow_unknown: bool = True) -> bool:
    if allow_unknown and value.lower() == "unknown":
        return True
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return len(value) == 10


def _governed_strength_rejection(packet: dict[str, Any], item: dict[str, Any]) -> dict[str, str] | None:
    if item["model_action"] != GOVERNED_ACTION or not item["allowed_to_affect_autonomous_recalculation"]:
        return None
    if item["driver"] not in GOVERNED_DRIVERS:
        return None
    if item["confidence"].lower() == "low":
        return {
            "status": "low_confidence_governed_change",
            "reason": "Low-confidence evidence cannot govern autonomous recalculation.",
        }
    if item["direction"].lower() == "neutral/mixed":
        return {
            "status": "mixed_governed_change",
            "reason": "Neutral or mixed evidence cannot govern autonomous recalculation.",
        }
    if item["source_date"].lower() == "unknown":
        return {
            "status": "undated_governed_change",
            "reason": "Evidence with unknown source date cannot govern autonomous recalculation.",
        }
    if _is_stale_evidence_date(packet, item):
        return {
            "status": "stale_governed_change",
            "reason": "Stale evidence cannot govern autonomous recalculation.",
        }
    return None


def _is_soft_no_change_rejection(item: dict[str, Any]) -> bool:
    return item.get("status") in {
        "conflicting_governed_evidence",
        "low_confidence_governed_change",
        "mixed_governed_change",
        "stale_governed_change",
        "undated_governed_change",
    }


def _reject_conflicting_governed_evidence(
    governed_evidence: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    directions_by_driver: dict[str, set[str]] = {}
    for item in governed_evidence:
        driver = str(item.get("driver") or "")
        direction = _direction_bucket(str(item.get("direction") or ""))
        directions_by_driver.setdefault(driver, set()).add(direction)

    conflicted_drivers = {
        driver
        for driver, directions in directions_by_driver.items()
        if "higher" in directions and "lower" in directions
    }
    if not conflicted_drivers:
        return governed_evidence, []

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in governed_evidence:
        if item.get("driver") not in conflicted_drivers:
            accepted.append(item)
            continue
        rejected.append(
            {
                "item": item,
                "status": "conflicting_governed_evidence",
                "reason": "Conflicting evidence for the same driver cannot govern autonomous recalculation.",
            }
        )
    return accepted, rejected


def _direction_bucket(direction: str) -> str:
    normalized = direction.lower()
    if "higher" in normalized:
        return "higher"
    if "lower" in normalized:
        return "lower"
    return normalized.strip()


def _is_stale_evidence_date(packet: dict[str, Any], item: dict[str, Any]) -> bool:
    as_of_raw = str(packet.get("as_of_date") or "").strip()
    source_date_raw = str(item.get("source_date") or "").strip()
    if not as_of_raw:
        return False
    try:
        as_of = date.fromisoformat(as_of_raw)
        source_date = date.fromisoformat(source_date_raw)
    except ValueError:
        return False
    return (as_of - source_date).days > STALE_EVIDENCE_DAYS


def _is_generic_source_presence(text: str) -> bool:
    normalized = " ".join(text.lower().strip().rstrip(".").split())
    return normalized in GENERIC_SOURCE_PHRASES


def _is_search_result_url(url: str) -> bool:
    parsed = urlsplit(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parsed.query.lower()
    if host in {"www.google.com", "google.com"} and path.startswith("/search"):
        return True
    if host in {"www.bing.com", "bing.com"} and path.startswith("/search"):
        return True
    if host in {"duckduckgo.com", "www.duckduckgo.com"} and query:
        return True
    if host in {"search.yahoo.com", "www.search.yahoo.com"}:
        return True
    return False


def _result(
    *,
    ok: bool,
    status: str,
    sanitized_packet: dict[str, Any],
    governed_evidence: list[dict[str, Any]] | None = None,
    report_only_evidence: list[dict[str, Any]] | None = None,
    rejected_evidence: list[dict[str, Any]] | None = None,
    source_family_status: list[dict[str, Any]] | None = None,
    validation_warnings: list[str] | None = None,
    unsupported_blockers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "sanitized_packet": sanitized_packet,
        "governed_evidence": governed_evidence or [],
        "report_only_evidence": report_only_evidence or [],
        "rejected_evidence": rejected_evidence or [],
        "source_family_status": source_family_status or [],
        "validation_warnings": validation_warnings or [],
        "unsupported_blockers": unsupported_blockers or [],
    }
