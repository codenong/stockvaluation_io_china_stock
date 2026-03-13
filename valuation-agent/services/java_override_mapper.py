"""Shared helpers for mapping analyst and user-friendly overrides to Java DCF payloads."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def normalize_percent_like_value(value: float) -> float:
    """Normalize decimal-like inputs (0.105) to percent-form numbers (10.5)."""
    if abs(value) <= 1.0:
        return value * 100.0
    return value


def normalize_sales_to_capital_value(value: float) -> float:
    """Normalize legacy percentage-style sales-to-capital inputs to x units."""
    if abs(value) > 50.0:
        return value / 100.0
    return value


def normalize_sector_sales_to_capital_value(value: float) -> float:
    """Normalize sector-level sales-to-capital inputs to x units."""
    if abs(value) > 50.0:
        return value / 100.0
    return value


def map_adjustments_to_java_overrides(
    adjustments: Any,
    sector_adjustments: Any = None,
    mapped_segments: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Map analyzer instructions to valuation-service FinancialDataInput overrides."""
    if not isinstance(adjustments, list):
        adjustments = []
    if not isinstance(sector_adjustments, list):
        sector_adjustments = []

    overrides: Dict[str, Any] = {}
    mapped = []
    unmapped = []

    for item in adjustments:
        if not isinstance(item, dict):
            continue

        param = str(item.get("parameter", "")).strip().lower()
        unit = str(item.get("unit", "")).strip().lower()
        new_value = item.get("new_value")
        try:
            new_value = float(new_value)
        except (TypeError, ValueError):
            unmapped.append({"parameter": param, "reason": "invalid_new_value", "value": item.get("new_value")})
            continue
        rounded_value = round(new_value, 2)

        if param == "revenue_cagr":
            overrides["compoundAnnualGrowth2_5"] = rounded_value
        elif param == "operating_margin":
            overrides["targetPreTaxOperatingMargin"] = rounded_value
        elif param == "wacc":
            overrides["initialCostCapital"] = round(normalize_percent_like_value(new_value), 2)
        elif param in {"terminal_growth", "terminal_growth_rate"}:
            overrides["terminalGrowthRate"] = round(normalize_percent_like_value(new_value), 2)
        elif param == "tax_rate":
            overrides["overrideAssumptionTaxRate"] = {
                "overrideCost": round(normalize_percent_like_value(new_value), 2),
                "isOverride": True,
                "additionalInputValue": 0.0,
                "additionalRadioValue": None,
            }
        elif param in {"sales_to_capital", "sales_to_capital_ratio", "reinvestment", "reinvestment_rate"}:
            stc_value = round(normalize_sales_to_capital_value(new_value), 2)
            overrides["salesToCapitalYears1To5"] = stc_value
            overrides.setdefault("salesToCapitalYears6To10", stc_value)
        else:
            unmapped.append({"parameter": param, "reason": "unsupported_parameter", "value": new_value, "unit": unit})
            continue

        mapped.append({
            "parameter": param,
            "new_value": rounded_value,
            "unit": unit,
            "rationale": str(item.get("rationale", "")).strip(),
        })

    allowed_adjustment_types = {"absolute", "relative_multiplier", "relative_additive"}
    allowed_timeframes = {"years_1_to_5", "years_6_to_10", "both"}
    allowed_sector_params = {"revenue_growth", "operating_margin", "sales_to_capital"}
    valid_sector_lookup = {
        str(item.get("sector", "")).strip().lower(): str(item.get("sector", "")).strip()
        for item in (mapped_segments or [])
        if isinstance(item, dict) and str(item.get("sector", "")).strip()
    }
    sector_mapped = []
    sector_unmapped = []
    java_sector_overrides: List[Dict[str, Any]] = []

    for item in sector_adjustments:
        if not isinstance(item, dict):
            continue

        raw_sector = str(item.get("sector", "")).strip()
        sector_name = valid_sector_lookup.get(raw_sector.lower())
        if not sector_name:
            sector_unmapped.append({"sector": raw_sector, "reason": "unknown_sector"})
            continue

        parameter = str(item.get("parameter", "")).strip().lower()
        if parameter not in allowed_sector_params:
            sector_unmapped.append(
                {"sector": sector_name, "parameter": parameter, "reason": "unsupported_parameter"}
            )
            continue

        value = item.get("value", item.get("new_value"))
        try:
            value = float(value)
        except (TypeError, ValueError):
            sector_unmapped.append(
                {"sector": sector_name, "parameter": parameter, "reason": "invalid_value", "value": value}
            )
            continue

        unit = str(item.get("unit", "")).strip().lower()
        if parameter == "sales_to_capital":
            normalized_value = round(normalize_sector_sales_to_capital_value(value), 2)
        elif unit in {"percent", "%"}:
            normalized_value = round(normalize_percent_like_value(value), 2)
        else:
            normalized_value = round(value, 2)

        adjustment_type = str(item.get("adjustment_type", "absolute")).strip().lower()
        if adjustment_type not in allowed_adjustment_types:
            sector_unmapped.append(
                {
                    "sector": sector_name,
                    "parameter": parameter,
                    "reason": "invalid_adjustment_type",
                    "adjustment_type": adjustment_type,
                }
            )
            continue

        timeframe = str(item.get("timeframe", "both")).strip().lower()
        if timeframe not in allowed_timeframes:
            timeframe = "both"

        java_item = {
            "sectorName": sector_name,
            "parameterType": parameter,
            "value": normalized_value,
            "adjustmentType": adjustment_type,
            "timeframe": timeframe,
        }
        java_sector_overrides.append(java_item)
        sector_mapped.append(
            {
                "sector": sector_name,
                "parameter": parameter,
                "value": normalized_value,
                "adjustmentType": adjustment_type,
                "timeframe": timeframe,
            }
        )

    if java_sector_overrides:
        overrides["sectorOverrides"] = java_sector_overrides

    return overrides, {
        "count": len(adjustments),
        "mapped": mapped,
        "unmapped": unmapped,
        "sector_count": len(sector_adjustments),
        "sector_mapped": sector_mapped,
        "sector_unmapped": sector_unmapped,
    }


def map_friendly_recalculate_request(
    top_level_overrides: Any,
    sector_overrides: Any = None,
    mapped_segments: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Map the BullBearGPT-friendly recalc request shape to Java overrides."""
    if not isinstance(top_level_overrides, dict):
        top_level_overrides = {}

    adjustments = []
    for source_key, target_key in (
        ("revenue_growth", "revenue_cagr"),
        ("operating_margin", "operating_margin"),
        ("sales_to_capital", "sales_to_capital"),
        ("wacc", "wacc"),
        ("terminal_growth", "terminal_growth"),
    ):
        if source_key not in top_level_overrides:
            continue
        adjustments.append({
            "parameter": target_key,
            "new_value": top_level_overrides.get(source_key),
        })

    overrides, meta = map_adjustments_to_java_overrides(
        adjustments=adjustments,
        sector_adjustments=sector_overrides,
        mapped_segments=mapped_segments,
    )
    meta["friendly_top_level_keys"] = list(top_level_overrides.keys())
    return overrides, meta
