"""Valuation audit packet validation for agent-native researched runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from typing import Any

from .security import sanitize_for_agent

SCHEMA_VERSION = "valuation_audit_packet.v1"

FINAL_CASE_TYPES = {
    "evidence_constrained_no_change",
    "evidence_constrained_governed_recalculation",
    "user_refined_scenario",
    "insufficient_researched_evidence",
}

REQUIRED_SECTIONS = (
    "ticker",
    "company",
    "run_mode",
    "evidence_packet",
    "segment_validation",
    "baseline_plausibility",
    "assumption_judgment",
    "recalculate_payloads",
    "assumption_buckets",
    "guided_refinement",
    "final_case_type",
    "final_report_inputs",
    "data_quality_limitations",
    "mcp_call_references",
    "accounting_decisions",
)

REQUIRED_EVIDENCE_RESULT_FIELDS = (
    "ok",
    "status",
    "sanitized_packet",
    "governed_evidence",
    "report_only_evidence",
    "rejected_evidence",
    "source_family_status",
    "validation_warnings",
    "unsupported_blockers",
)

UNSAFE_AUDIT_KEY_PARTS = (
    ".env",
    "env_path",
    "local_data",
    "prompt_dump",
    "raw_article_body",
    "article_body",
    "raw_filing_body",
    "filing_body",
    "raw_search",
    "search_traces",
    "broad_search",
)

UNSAFE_AUDIT_STRING_PARTS = (
    "/.env",
    "\\.env",
    "local_data",
    "prompt_dump_from_container",
)

USER_FACING_CASE_KEYS = {
    "case_type",
    "final_case_type",
    "scenario_type",
    "main_scenario",
    "visible_case",
    "visible_scenario",
    "report_case",
}


def validate_valuation_audit_packet(packet: Any) -> dict[str, Any]:
    """Validate and sanitize a valuation audit packet."""
    if not isinstance(packet, dict):
        return _result(False, "invalid_packet", {}, ["ValuationAuditPacket must be a JSON object."])

    warnings = _required_section_warnings(packet)
    evidence_packet = packet.get("evidence_packet")
    if isinstance(evidence_packet, dict):
        warnings.extend(_evidence_result_warnings(evidence_packet))

    final_case_type = str(packet.get("final_case_type") or "").strip()
    if final_case_type and final_case_type not in FINAL_CASE_TYPES:
        warnings.append("final_case_type is unsupported.")
    warnings.extend(_mechanical_baseline_warnings(packet))
    warnings.extend(_final_report_input_warnings(packet))

    sanitized_packet = _sanitize_packet(packet)
    ok = not warnings
    status = "valid_audit_packet" if ok else "invalid_packet"
    return _result(ok, status, sanitized_packet if ok else sanitized_packet, warnings)


def build_valuation_audit_packet(
    *,
    ticker: str,
    company: str,
    run_mode: str,
    evidence_packet: dict[str, Any],
    segment_validation: dict[str, Any],
    baseline_plausibility: dict[str, Any],
    assumption_judgment: dict[str, Any],
    recalculate_payloads: list[dict[str, Any]],
    assumption_buckets: dict[str, Any],
    guided_refinement: dict[str, Any],
    final_case_type: str,
    final_report_inputs: dict[str, Any],
    data_quality_limitations: list[Any] | None = None,
    mcp_call_references: list[dict[str, Any]] | None = None,
    accounting_decisions: dict[str, Any] | None = None,
    internal_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "ticker": ticker,
        "company": company,
        "run_mode": run_mode,
        "evidence_packet": evidence_packet,
        "segment_validation": segment_validation,
        "baseline_plausibility": baseline_plausibility,
        "assumption_judgment": assumption_judgment,
        "recalculate_payloads": recalculate_payloads,
        "assumption_buckets": assumption_buckets,
        "guided_refinement": guided_refinement,
        "final_case_type": final_case_type,
        "final_report_inputs": final_report_inputs,
        "data_quality_limitations": data_quality_limitations or [],
        "mcp_call_references": mcp_call_references or [],
        "accounting_decisions": accounting_decisions or {
            "requested": {},
            "mapped": {},
            "unsupported": {},
            "report_only": [],
            "governed_scenarios": [],
            "rejected": [],
            "metadata": {},
            "effective": [],
        },
    }
    if internal_state is not None:
        packet["internal_state"] = internal_state
    return validate_valuation_audit_packet(packet)


def valuation_audit_packet_metadata(validation: dict[str, Any]) -> dict[str, Any]:
    packet = _dict(validation.get("packet"))
    reference = valuation_audit_packet_reference(packet)
    packet_with_reference = dict(packet)
    packet_with_reference["packet_reference"] = reference
    summary = dict(_dict(validation.get("summary")))
    summary["packet_reference"] = reference
    return {
        "reference": reference,
        "summary": summary,
        "packet": packet_with_reference,
    }


def valuation_audit_packet_reference(packet: dict[str, Any]) -> str:
    encoded = json.dumps(packet, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"valuation_audit_packet:{digest}"


def _required_section_warnings(packet: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for key in REQUIRED_SECTIONS:
        if key not in packet:
            warnings.append(f"{key} is required.")
            continue
        if key in {"ticker", "company", "run_mode", "final_case_type"}:
            if not str(packet.get(key) or "").strip():
                warnings.append(f"{key} is required.")
        elif key in {"recalculate_payloads", "data_quality_limitations", "mcp_call_references"}:
            if not isinstance(packet.get(key), list):
                warnings.append(f"{key} must be a list.")
        elif key == "assumption_buckets":
            buckets = packet.get(key)
            if not isinstance(buckets, dict):
                warnings.append("assumption_buckets must be a JSON object.")
            else:
                for bucket in ("requested", "mapped", "unsupported", "metadata", "effective"):
                    if bucket not in buckets:
                        warnings.append(f"assumption_buckets.{bucket} is required.")
        elif packet.get(key) is None:
            warnings.append(f"{key} is required.")
    return warnings


def _evidence_result_warnings(evidence_packet: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for key in REQUIRED_EVIDENCE_RESULT_FIELDS:
        if key not in evidence_packet:
            warnings.append(f"evidence_packet.{key} is required from Phase 1 validation.")
    return warnings


def _mechanical_baseline_warnings(packet: dict[str, Any]) -> list[str]:
    internal_state = packet.get("internal_state")
    if not isinstance(internal_state, dict):
        return []
    mechanical_baseline = internal_state.get("mechanical_baseline")
    if mechanical_baseline is None:
        return []
    if not isinstance(mechanical_baseline, dict):
        return ["internal_state.mechanical_baseline must be a JSON object."]
    if mechanical_baseline.get("visibility") != "internal_only":
        return ["internal_state.mechanical_baseline.visibility must be internal_only."]
    return []


def _final_report_input_warnings(packet: dict[str, Any]) -> list[str]:
    final_report_inputs = packet.get("final_report_inputs")
    if _has_visible_mechanical_baseline_case(final_report_inputs):
        return [
            "final_report_inputs must not expose mechanical_baseline as a visible report case or scenario."
        ]
    return []


def _has_visible_mechanical_baseline_case(value: Any, parent_key: str = "") -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if (
                key_text in USER_FACING_CASE_KEYS
                and isinstance(item, str)
                and item == "mechanical_baseline"
            ):
                return True
            if _has_visible_mechanical_baseline_case(item, key_text):
                return True
        return False

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_has_visible_mechanical_baseline_case(item, parent_key) for item in value)

    return (
        parent_key in USER_FACING_CASE_KEYS
        and isinstance(value, str)
        and value == "mechanical_baseline"
    )


def _sanitize_packet(packet: dict[str, Any]) -> dict[str, Any]:
    clean = sanitize_for_audit_packet(packet)
    clean["schema_version"] = SCHEMA_VERSION
    return clean


def sanitize_for_audit_packet(value: Any) -> Any:
    """Redact secrets and audit-unsafe raw/runtime material from packet output."""
    return _redact_audit_unsafe(sanitize_for_agent(value))


def _redact_audit_unsafe(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        redacted_index = 0
        for key, item in value.items():
            key_text = str(key)
            if _is_unsafe_audit_key(key_text):
                redacted[f"redacted_audit_unsafe_{redacted_index}"] = "[REDACTED]"
                redacted_index += 1
            else:
                redacted[key_text] = _redact_audit_unsafe(item)
        return redacted

    if isinstance(value, str):
        if _is_unsafe_audit_string(value):
            return "[REDACTED]"
        return value

    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_redact_audit_unsafe(item) for item in value]

    return value


def _is_unsafe_audit_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in UNSAFE_AUDIT_KEY_PARTS)


def _is_unsafe_audit_string(value: str) -> bool:
    lowered = value.lower()
    return any(part in lowered for part in UNSAFE_AUDIT_STRING_PARTS)


def _result(ok: bool, status: str, packet: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    summary = {
        "packet_status": status,
        "final_case_type": packet.get("final_case_type"),
        "evidence_status": _dict(packet.get("evidence_packet")).get("status"),
        "guided_refinement_status": _dict(packet.get("guided_refinement")).get("status"),
    }
    return {
        "ok": ok,
        "status": status,
        "packet": packet,
        "validation_warnings": warnings,
        "summary": summary,
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
