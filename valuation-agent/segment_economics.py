"""Segment economics validation for agent-native researched valuations."""

from __future__ import annotations

from typing import Any

from .evidence_packet import validate_evidence_packet
from .security import sanitize_for_agent
from .segment_discovery import sanitize_segment_package
from .source_provenance import RETRIEVAL_STATUSES, SOURCE_CLASSES

SEGMENT_DRIVERS = ("revenue_mix", "growth", "margin", "reinvestment_intensity")
REINVESTMENT_BASES = {
    "capex_intensity",
    "rd_intensity",
    "r_and_d_intensity",
    "working_capital_need",
    "sales_to_capital",
    "asset_intensity",
}
DRIVER_TO_EVIDENCE_DRIVER = {
    "growth": "revenue_growth",
    "margin": "operating_margin",
    "reinvestment_intensity": "reinvestment_sales_to_capital",
}
DRIVER_TO_SECTOR_PARAMETER = {
    "growth": "revenue_growth",
    "margin": "operating_margin",
    "reinvestment_intensity": "sales_to_capital",
}
SERVICE_SECTOR_KEY_FIELDS = (
    "sector_key",
    "sectorKey",
    "yahoo_industry_key",
    "yahooIndustryKey",
    "service_sector_key",
    "serviceSectorKey",
    "service_sector",
    "serviceSector",
)


def validate_segment_economics(artifact: Any) -> dict[str, Any]:
    """Validate segment economics before they can affect MCP recalculation."""
    if not isinstance(artifact, dict):
        return _result(
            ok=False,
            status="invalid_packet",
            quality="segment_evidence_insufficient",
            validation_warnings=["SegmentEconomics artifact must be a JSON object."],
        )

    raw_segments = artifact.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        return _result(
            ok=True,
            status="single_segment_or_no_segment_economics",
            quality="insufficient_evidence",
            validation_warnings=["No segment economics were provided."],
            limitations=["No segment economics artifact was available; keep the report concise and avoid fake segment precision."],
        )

    validation_warnings = _required_packet_warnings(artifact)
    validation_warnings.extend(_segment_source_warnings(raw_segments))
    segment_validation = sanitize_segment_package({"segments": raw_segments})
    raw_by_name = {
        str(segment.get("segment_name") or segment.get("name") or segment.get("segment") or "").strip(): segment
        for segment in raw_segments
        if isinstance(segment, dict)
    }
    segment_validation = _enforce_segment_economics_mapping_contract(segment_validation, raw_by_name)
    accepted_segment_package = _accepted_segment_package(segment_validation, raw_by_name)

    evidence_validation = (
        validate_evidence_packet(artifact.get("evidence_packet"))
        if "evidence_packet" in artifact
        else None
    )
    accepted_evidence = [
        item
        for item in (evidence_validation or {}).get("governed_evidence", [])
        if isinstance(item, dict)
    ]
    segment_decisions: list[dict[str, Any]] = []
    accepted_sector_overrides: list[dict[str, Any]] = []
    rejected_economics: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for segment in segment_validation["segments"]:
        decision = _revenue_only_segment_decision(segment)
        raw_segment = raw_by_name.get(str(segment.get("segment_name") or ""))
        driver_result = _apply_driver_economics(
            decision=decision,
            raw_segment=raw_segment,
            accepted_evidence=accepted_evidence,
        )
        accepted_sector_overrides.extend(driver_result["accepted_sector_overrides"])
        rejected_economics.extend(driver_result["rejected_economics"])
        unsupported.extend(driver_result["unsupported"])
        segment_decisions.append(decision)

    report_only_facts = _report_only_facts(artifact.get("report_only_facts"))
    limitations: list[str] = []
    if accepted_segment_package:
        limitations.append(
            "Revenue-only segment evidence supports revenue mix or baseline context only; it does not support segment growth, margin, or reinvestment changes."
        )
    if report_only_facts:
        limitations.append(
            "Sub-business or partial segment facts are preserved for explanation only unless direct driver-specific evidence supports a governed model action."
        )
    limitations.extend(str(warning) for warning in segment_validation.get("validation_warnings", []))

    quality = _quality_from_segment_validation(segment_validation["baseline_quality"], bool(accepted_segment_package))
    if accepted_sector_overrides:
        quality = "validated_full_economics" if _all_segment_drivers_supported(segment_decisions) else "partial_economics"
    status = quality
    ok = not validation_warnings and segment_validation["baseline_quality"] in {
        "segment_weighted_baseline",
        "single_industry_fallback",
    }
    if validation_warnings:
        status = "invalid_packet"
    elif segment_validation["baseline_quality"] == "segment_mapping_blocked":
        status = "segment_mapping_blocked"
    elif segment_validation["baseline_quality"] == "segment_evidence_insufficient":
        status = "segment_evidence_insufficient"
    elif rejected_economics:
        status = "blocked_by_rejected_segment_economics"
        ok = False

    return _result(
        ok=ok,
        status=status,
        quality=quality,
        accepted_segment_package=accepted_segment_package,
        accepted_sector_overrides=accepted_sector_overrides,
        segment_decisions=segment_decisions,
        report_only_facts=report_only_facts,
        rejected_economics=rejected_economics,
        unsupported=unsupported,
        metadata={"evidence_packet": _evidence_packet_metadata(evidence_validation)}
        if evidence_validation is not None
        else {},
        validation_warnings=validation_warnings,
        limitations=limitations,
    )


def _required_packet_warnings(artifact: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for key in ("ticker", "company", "run_mode"):
        if not str(artifact.get(key) or "").strip():
            warnings.append(f"{key} is required.")
    return warnings


def _segment_source_warnings(raw_segments: list[Any]) -> list[str]:
    warnings: list[str] = []
    for index, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            warnings.append(f"segments[{index}] must be a JSON object.")
            continue
        source_class = str(raw.get("source_class") or raw.get("sourceClass") or "").strip()
        provider = str(raw.get("provider") or "").strip()
        retrieval_status = str(raw.get("retrieval_status") or raw.get("source_status") or raw.get("status") or "").strip()
        disclosure_level = str(raw.get("disclosure_level") or raw.get("disclosureLevel") or "").strip()
        if source_class not in SOURCE_CLASSES:
            warnings.append(f"segments[{index}].source_class must be primary_filing, yahoo_normalized, company_ir, or agent_researched.")
        if not provider:
            warnings.append(f"segments[{index}].provider is required.")
        if retrieval_status not in RETRIEVAL_STATUSES:
            warnings.append(f"segments[{index}].retrieval_status is invalid.")
        if not disclosure_level:
            warnings.append(f"segments[{index}].disclosure_level is required.")
    return warnings


def _enforce_segment_economics_mapping_contract(
    segment_validation: dict[str, Any],
    raw_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if segment_validation["baseline_quality"] != "segment_weighted_baseline":
        return segment_validation

    blockers: list[str] = []
    for segment in segment_validation["segments"]:
        segment_name = str(segment.get("segment_name") or "").strip()
        raw = raw_by_name.get(segment_name) or {}
        disclosure_level = str(raw.get("disclosure_level") or raw.get("disclosureLevel") or "").strip().lower()
        if disclosure_level == "geography" and not _has_operating_segment_basis(raw):
            blockers.append(
                f"Geographic disclosure for {segment_name} cannot support SegmentEconomics baseline use without an explicit operating-segment basis and mapping rationale."
            )
        if not _service_sector_key(raw):
            blockers.append(
                f"{segment_name} requires sector_key or yahoo_industry_key for service baseline mapping; mapped_industry is display-only."
            )

    if not blockers:
        return segment_validation
    return {
        **segment_validation,
        "baseline_quality": "segment_mapping_blocked",
        "segment_aware": False,
        "segments": [],
        "validation_warnings": _dedupe(
            [str(warning) for warning in segment_validation.get("validation_warnings", [])]
            + blockers
        ),
    }


def _accepted_segment_package(
    segment_validation: dict[str, Any],
    raw_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if segment_validation["baseline_quality"] != "segment_weighted_baseline":
        return None

    accepted_segments: list[dict[str, Any]] = []
    for segment in segment_validation["segments"]:
        segment_name = str(segment.get("segment_name") or "").strip()
        sector_key = _service_sector_key(raw_by_name.get(segment_name) or {})
        accepted = dict(segment)
        accepted["sector"] = sector_key
        accepted["sector_key"] = sector_key
        accepted["yahoo_industry_key"] = sector_key
        accepted_segments.append(sanitize_for_agent(accepted))
    return {"segments": accepted_segments}


def _has_operating_segment_basis(raw: dict[str, Any]) -> bool:
    basis = raw.get("operating_segment_basis")
    if basis is None:
        basis = raw.get("operatingSegmentBasis")
    rationale = str(
        raw.get("mapping_rationale")
        or raw.get("mappingRationale")
        or raw.get("operating_segment_rationale")
        or raw.get("operatingSegmentRationale")
        or ""
    ).strip()
    return basis is True and bool(rationale)


def _service_sector_key(raw: dict[str, Any]) -> str:
    for key in SERVICE_SECTOR_KEY_FIELDS:
        value = str(raw.get(key) or "").strip()
        if value:
            return value
    sector = str(raw.get("sector") or raw.get("sectorName") or "").strip()
    return sector if _looks_like_service_sector_key(sector) else ""


def _looks_like_service_sector_key(value: str) -> bool:
    if not value or value != value.lower():
        return False
    return all(character.isalnum() or character == "-" for character in value)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _revenue_only_segment_decision(segment: dict[str, Any]) -> dict[str, Any]:
    segment_name = str(segment.get("segment_name") or "").strip()
    return sanitize_for_agent(
        {
            "segment_name": segment_name,
            "mapped_industry": str(segment.get("mapped_industry") or "").strip(),
            "drivers": {
                "revenue_mix": {
                    "status": "model_supported",
                    "model_action": "segment_package",
                    "evidence_status": "accepted_revenue_mix",
                },
                "growth": _unavailable_driver("growth", segment_name),
                "margin": _unavailable_driver("margin", segment_name),
                "reinvestment_intensity": _unavailable_driver("reinvestment_intensity", segment_name),
            },
        }
    )


def _unavailable_driver(driver: str, segment_name: str) -> dict[str, str]:
    return {
        "status": "unavailable",
        "model_action": "report_only_limitation",
        "reason": f"No driver-specific {driver} evidence was accepted for {segment_name}.",
    }


def _quality_from_segment_validation(baseline_quality: str, has_segment_package: bool) -> str:
    if has_segment_package:
        return "revenue_only_segments"
    if baseline_quality == "segment_mapping_blocked":
        return "segment_mapping_blocked"
    if baseline_quality == "segment_evidence_insufficient":
        return "segment_evidence_insufficient"
    return "insufficient_evidence"


def _report_only_facts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [sanitize_for_agent(item) for item in value if isinstance(item, dict)]


def _all_segment_drivers_supported(segment_decisions: list[dict[str, Any]]) -> bool:
    if not segment_decisions:
        return False
    for decision in segment_decisions:
        drivers = decision.get("drivers")
        if not isinstance(drivers, dict):
            return False
        for driver in ("growth", "margin", "reinvestment_intensity"):
            driver_status = drivers.get(driver)
            if not isinstance(driver_status, dict) or driver_status.get("status") != "model_supported":
                return False
    return True


def _apply_driver_economics(
    *,
    decision: dict[str, Any],
    raw_segment: dict[str, Any] | None,
    accepted_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(raw_segment, dict) or not isinstance(raw_segment.get("drivers"), dict):
        return {"accepted_sector_overrides": [], "rejected_economics": [], "unsupported": []}

    segment_name = str(decision.get("segment_name") or "")
    segment_sector_key = _service_sector_key(raw_segment or {})
    accepted_sector_overrides: list[dict[str, Any]] = []
    rejected_economics: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for driver, evidence_driver in DRIVER_TO_EVIDENCE_DRIVER.items():
        raw_driver = raw_segment["drivers"].get(driver)
        if raw_driver is None:
            continue
        if not isinstance(raw_driver, dict):
            rejection = _driver_rejection(segment_name, driver, raw_driver, "invalid_driver_evidence", "Driver evidence must be a JSON object.")
            rejected_economics.append(rejection)
            unsupported.append(_unsupported_from_rejection(rejection))
            continue

        reason = _driver_provenance_rejection(raw_driver)
        if reason is not None:
            rejection = _driver_rejection(segment_name, driver, raw_driver, "missing_driver_provenance", reason)
            rejected_economics.append(rejection)
            unsupported.append(_unsupported_from_rejection(rejection))
            continue

        if not _has_matching_evidence(raw_driver, accepted_evidence, evidence_driver):
            rejection = _driver_rejection(
                segment_name,
                driver,
                raw_driver,
                "missing_governed_evidence",
                f"Segment {driver} requires evidence_ref driver {evidence_driver} with exact source_url and source_date matching accepted EvidencePacket evidence.",
            )
            rejected_economics.append(rejection)
            unsupported.append(_unsupported_from_rejection(rejection))
            continue

        reinvestment_basis = _reinvestment_basis(raw_driver) if driver == "reinvestment_intensity" else None
        if driver == "reinvestment_intensity" and reinvestment_basis is None:
            rejection = _driver_rejection(
                segment_name,
                driver,
                raw_driver,
                "missing_reinvestment_basis",
                "Reinvestment evidence must explicitly identify capex, R&D intensity, working-capital need, sales-to-capital, or asset intensity.",
            )
            rejected_economics.append(rejection)
            unsupported.append(_unsupported_from_rejection(rejection))
            continue

        sector_override = _accepted_sector_override(raw_driver, driver, segment_sector_key)
        if sector_override is None:
            rejection = _driver_rejection(
                segment_name,
                driver,
                raw_driver,
                "invalid_sector_override",
                f"Segment {driver} evidence must map to a supported sector override.",
            )
            rejected_economics.append(rejection)
            unsupported.append(_unsupported_from_rejection(rejection))
            continue

        accepted_sector_overrides.append(sector_override)
        decision["drivers"][driver] = sanitize_for_agent(
            {
                "status": "model_supported",
                "model_action": "governed_sector_override",
                "evidence_driver": evidence_driver,
                "sector_override": sector_override,
            }
        )
        if reinvestment_basis is not None:
            decision["drivers"][driver]["reinvestment_basis"] = reinvestment_basis

    return {
        "accepted_sector_overrides": accepted_sector_overrides,
        "rejected_economics": rejected_economics,
        "unsupported": unsupported,
    }


def _driver_provenance_rejection(raw_driver: dict[str, Any]) -> str | None:
    source_class = str(raw_driver.get("source_class") or raw_driver.get("sourceClass") or "").strip()
    provider = str(raw_driver.get("provider") or "").strip()
    retrieval_status = str(raw_driver.get("retrieval_status") or raw_driver.get("source_status") or raw_driver.get("status") or "").strip()
    disclosure_level = str(raw_driver.get("disclosure_level") or raw_driver.get("disclosureLevel") or "").strip()
    if source_class not in SOURCE_CLASSES:
        return "source_class must be primary_filing, yahoo_normalized, company_ir, or agent_researched."
    if not provider:
        return "provider is required."
    if retrieval_status not in RETRIEVAL_STATUSES:
        return "retrieval_status is invalid."
    if not disclosure_level:
        return "disclosure_level is required."
    return None


def _has_matching_evidence(
    raw_driver: dict[str, Any],
    accepted_evidence: list[dict[str, Any]],
    evidence_driver: str,
) -> bool:
    evidence_ref = raw_driver.get("evidence_ref")
    if not isinstance(evidence_ref, dict):
        return False
    source_url = str(evidence_ref.get("source_url") or "").strip()
    source_date = str(evidence_ref.get("source_date") or "").strip()
    ref_driver = str(evidence_ref.get("driver") or "").strip()
    if ref_driver != evidence_driver or not source_url or not source_date:
        return False
    for item in accepted_evidence:
        if str(item.get("driver") or "") != evidence_driver:
            continue
        if str(item.get("source_url") or "") != source_url:
            continue
        if str(item.get("source_date") or "") != source_date:
            continue
        return True
    return False


def _reinvestment_basis(raw_driver: dict[str, Any]) -> str | None:
    basis = str(
        raw_driver.get("reinvestment_basis")
        or raw_driver.get("economic_basis")
        or raw_driver.get("basis")
        or ""
    ).strip()
    return basis if basis in REINVESTMENT_BASES else None


def _accepted_sector_override(raw_driver: dict[str, Any], driver: str, segment_sector_key: str) -> dict[str, Any] | None:
    raw_override = raw_driver.get("sector_override")
    if not isinstance(raw_override, dict):
        return None
    parameter = str(raw_override.get("parameter") or raw_override.get("parameter_type") or "").strip()
    expected = DRIVER_TO_SECTOR_PARAMETER[driver]
    if parameter != expected:
        return None
    override_sector_key = _service_sector_key(raw_override)
    if override_sector_key and segment_sector_key and override_sector_key != segment_sector_key:
        return None
    sector = override_sector_key or segment_sector_key
    adjustment_type = str(raw_override.get("adjustment_type") or "").strip()
    timeframe = str(raw_override.get("timeframe") or "both").strip()
    unit = str(raw_override.get("unit") or "percent").strip()
    value = raw_override.get("value")
    if not sector or adjustment_type not in {"absolute", "relative_multiplier", "relative_additive"}:
        return None
    if timeframe not in {"years_1_to_5", "years_6_to_10", "both"}:
        return None
    if unit not in {"percent", "x"}:
        return None
    if not isinstance(value, int | float):
        return None
    return sanitize_for_agent(
        {
            "sector": sector,
            "parameter": parameter,
            "value": float(value),
            "unit": unit,
            "adjustment_type": adjustment_type,
            "timeframe": timeframe,
        }
    )


def _driver_rejection(
    segment_name: str,
    driver: str,
    raw_driver: Any,
    status: str,
    reason: str,
) -> dict[str, Any]:
    return sanitize_for_agent(
        {
            "segment_name": segment_name,
            "driver": driver,
            "status": status,
            "reason": reason,
            "item": raw_driver,
        }
    )


def _unsupported_from_rejection(rejection: dict[str, Any]) -> dict[str, Any]:
    return {
        "field": f"segment_economics.{rejection.get('segment_name')}.{rejection.get('driver')}",
        "status": str(rejection.get("status") or "rejected_segment_economics"),
        "reason": str(rejection.get("reason") or "Rejected segment economics."),
    }


def _evidence_packet_metadata(validation: dict[str, Any] | None) -> dict[str, Any]:
    if validation is None:
        return {}
    return {
        "ok": validation.get("ok"),
        "status": validation.get("status"),
        "governed_evidence": validation.get("governed_evidence", []),
        "report_only_evidence": validation.get("report_only_evidence", []),
        "rejected_evidence": validation.get("rejected_evidence", []),
        "source_family_status": validation.get("source_family_status", []),
        "validation_warnings": validation.get("validation_warnings", []),
        "unsupported_blockers": validation.get("unsupported_blockers", []),
    }


def _result(
    *,
    ok: bool,
    status: str,
    quality: str,
    accepted_segment_package: dict[str, Any] | None = None,
    accepted_sector_overrides: list[dict[str, Any]] | None = None,
    segment_decisions: list[dict[str, Any]] | None = None,
    report_only_facts: list[dict[str, Any]] | None = None,
    rejected_economics: list[dict[str, Any]] | None = None,
    unsupported: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    validation_warnings: list[str] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    accepted_inputs = {
        "segments": accepted_segment_package,
        "sector_overrides": accepted_sector_overrides or [],
    }
    return {
        "ok": ok,
        "status": status,
        "quality": quality,
        "accepted_mcp_inputs": accepted_inputs,
        "accepted_segment_package": accepted_segment_package,
        "accepted_sector_overrides": accepted_sector_overrides or [],
        "segment_decisions": segment_decisions or [],
        "report_only_facts": report_only_facts or [],
        "rejected_economics": rejected_economics or [],
        "unsupported": unsupported or [],
        "metadata": metadata or {},
        "validation_warnings": validation_warnings or [],
        "limitations": limitations or [],
    }
