"""StockValuation MCP tool contracts and implementation."""

from __future__ import annotations

import json
import math
import re
from typing import Any, Callable

from . import __version__
from .security import sanitize_for_agent
from .segment_discovery import parse_revenue_weight, sanitize_segment_package
from .service_client import (
    DEFAULT_SERVICE_URL,
    NonJsonServiceResponse,
    ServiceHTTPError,
    ServiceUnavailable,
    ValuationServiceClient,
    ValuationServiceError,
)

TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")
MIN_MARGIN_CONVERGENCE_YEAR = 1.0
MAX_MARGIN_CONVERGENCE_YEAR = 10.0
MIN_SALES_TO_CAPITAL = 0.05
MAX_SALES_TO_CAPITAL = 20.0

SUPPORTED_OVERRIDE_FIELDS = {
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
    "wacc",
    "terminal_growth",
    "tax_rate",
    "segments",
    "sector_overrides",
    "growth_pattern_override",
}

REQUEST_POLICY_MODES = {
    "mechanical_baseline",
    "autonomous_researched",
    "user_refined_scenario",
    "explicit_scenario",
    "researched_autonomous",
    "researched_baseline",
}

RECALCULATE_METADATA_FIELDS = {"rationale", "evidence_used", "request_policy", "user_judgment"}
AUTONOMOUS_RESEARCHED_FIELDS = {"revenue_growth", "operating_margin", "sales_to_capital", "segments", "sector_overrides"}
USER_REFINED_SCENARIO_FIELDS = {
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
REPORT_ONLY_OVERRIDE_FIELDS = {
    "rd_capitalization",
    "r_and_d_capitalization",
    "leases",
    "operating_leases",
    "options",
    "warrants",
    "nols",
    "cash",
    "debt",
    "share_count",
    "accounting_adjustments",
}
DIRECT_VALUATION_OUTPUT_FIELDS = {
    "fair_value",
    "fair_value_per_share",
    "target_price",
    "price_target",
    "equity_value",
    "terminal_value",
    "intrinsic_value",
    "intrinsic_value_per_share",
    "estimated_value_per_share",
    "upside",
    "downside",
    "upside_downside",
    "market_price",
    "price_value_gap",
    "direct_market_price_calibration",
}

TOOL_NAMES = [
    "stockvaluation.health",
    "stockvaluation.value_ticker",
    "stockvaluation.recalculate",
    "stockvaluation.get_assumptions",
    "stockvaluation.get_growth_anchor",
    "stockvaluation.get_reference_data_status",
    "stockvaluation.explain_failure",
]

KNOWN_FAILURE_CATEGORIES = {
    "unsupported_company",
    "insufficient_financial_data",
    "missing_configuration",
    "stale_reference_data",
    "non_json_service_response",
    "missing_local_service",
    "currency_conversion_failed",
    "upstream_service_error",
    "invalid_ticker",
    "unsupported_overrides",
    "unknown_failure",
}

SUPPORTED_PROTOCOL_VERSIONS = (
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
    "2024-10-07",
)


def _object_schema(properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties or {},
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "tool": {"type": "string"},
            "error": {"type": "object"},
        },
        "required": ["ok", "tool"],
        "additionalProperties": True,
    }


def tool_definitions() -> list[dict[str, Any]]:
    ticker_property = {
        "ticker": {
            "type": "string",
            "description": "Public equity ticker symbol, e.g. MSFT. No company names or shell syntax.",
        }
    }
    return [
        {
            "name": "stockvaluation.health",
            "title": "StockValuation Health",
            "description": "Check whether the local valuation service is reachable.",
            "inputSchema": _object_schema(),
            "outputSchema": _output_schema(),
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "stockvaluation.value_ticker",
            "title": "Value Ticker",
            "description": "Fetch deterministic local DCF JSON for a supported ticker.",
            "inputSchema": _object_schema(ticker_property, ["ticker"]),
            "outputSchema": _output_schema(),
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "stockvaluation.recalculate",
            "title": "Recalculate Valuation",
            "description": "Recalculate local DCF JSON using governed scenario overrides.",
            "inputSchema": _object_schema(
                {
                    **ticker_property,
                    "overrides": {
                        "type": "object",
                        "description": "Supported keys: revenue_growth, operating_margin_next_year, operating_margin/target_operating_margin, margin_convergence_year, sales_to_capital, sales_to_capital_years_1_to_5, sales_to_capital_years_6_to_10, segments, sector_overrides, wacc, terminal_growth, tax_rate, growth_pattern_override, request_policy, rationale, evidence_used, user_judgment.",
                        "additionalProperties": True,
                    },
                },
                ["ticker", "overrides"],
            ),
            "outputSchema": _output_schema(),
            "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "stockvaluation.get_assumptions",
            "title": "Get Assumptions",
            "description": "Return the assumption transparency slice for a ticker.",
            "inputSchema": _object_schema(ticker_property, ["ticker"]),
            "outputSchema": _output_schema(),
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "stockvaluation.get_growth_anchor",
            "title": "Get Growth Anchor",
            "description": "Return mapped Damodaran growth-anchor context for a ticker.",
            "inputSchema": _object_schema(ticker_property, ["ticker"]),
            "outputSchema": _output_schema(),
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "stockvaluation.get_reference_data_status",
            "title": "Get Reference Data Status",
            "description": "Return service and reference-data status used for reproducibility notes.",
            "inputSchema": _object_schema({**ticker_property}, []),
            "outputSchema": _output_schema(),
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "stockvaluation.explain_failure",
            "title": "Explain Failure",
            "description": "Classify an MCP or valuation-service failure into an agent-readable recovery path.",
            "inputSchema": _object_schema(
                {
                    "error": {
                        "description": "Error string or structured error object from another StockValuation tool.",
                    }
                },
                ["error"],
            ),
            "outputSchema": _output_schema(),
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
    ]


class MCPToolRegistry:
    """Callable registry for StockValuation MCP tools."""

    def __init__(self, service_client: Any | None = None):
        self.service_client = service_client or ValuationServiceClient()
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "stockvaluation.health": self._health,
            "stockvaluation.value_ticker": self._value_ticker,
            "stockvaluation.recalculate": self._recalculate,
            "stockvaluation.get_assumptions": self._get_assumptions,
            "stockvaluation.get_growth_anchor": self._get_growth_anchor,
            "stockvaluation.get_reference_data_status": self._get_reference_data_status,
            "stockvaluation.explain_failure": self._explain_failure,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return tool_definitions()

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        if name not in self._handlers:
            content = error_payload(name, "UNKNOWN_TOOL", "Unknown StockValuation tool.", "unknown_tool")
            return tool_result(content, is_error=True)
        content = self._handlers[name](args)
        return tool_result(content, is_error=not bool(content.get("ok")))

    def _health(self, _: dict[str, Any]) -> dict[str, Any]:
        tool = "stockvaluation.health"
        try:
            health = self.service_client.health()
            return {
                "ok": True,
                "tool": tool,
                "service": {
                    "name": "stockvaluation-service",
                    "status": health.get("status", "unknown"),
                    "raw": sanitize_for_agent(health),
                },
                "mcp": mcp_metadata(),
                "policy": policy_metadata(),
            }
        except ValuationServiceError as exc:
            return service_exception_payload(tool, exc)

    def _value_ticker(self, args: dict[str, Any]) -> dict[str, Any]:
        tool = "stockvaluation.value_ticker"
        ticker, error = normalize_ticker(args.get("ticker"))
        if error:
            return error_payload(tool, "INVALID_TICKER", error, "invalid_ticker")
        try:
            valuation = self.service_client.value_ticker(ticker)
            return valuation_success_payload(tool, ticker, valuation)
        except ValuationServiceError as exc:
            return service_exception_payload(tool, exc, ticker=ticker)

    def _recalculate(self, args: dict[str, Any]) -> dict[str, Any]:
        tool = "stockvaluation.recalculate"
        ticker, error = normalize_ticker(args.get("ticker"))
        if error:
            return error_payload(tool, "INVALID_TICKER", error, "invalid_ticker")
        requested = args.get("overrides")
        if not isinstance(requested, dict):
            return error_payload(
                tool,
                "INVALID_OVERRIDES",
                "overrides must be a JSON object.",
                "invalid_overrides",
                extra={"assumptions": {"requested": requested, "mapped": {}, "unsupported": {}, "effective": {}}},
            )

        mapped, unsupported, metadata = map_recalculate_overrides(requested)
        assumption_meta = {
            "requested": sanitize_for_agent(requested),
            "mapped": mapped,
            "unsupported": unsupported,
            "effective": {},
        }
        if metadata:
            assumption_meta["metadata"] = metadata
        if unsupported:
            return error_payload(
                tool,
                "UNSUPPORTED_OVERRIDES",
                "One or more override fields are not governed by the MCP contract.",
                "unsupported_overrides",
                extra={"ticker": ticker, "assumptions": assumption_meta, "baseline": blocked_baseline_contract(unsupported)},
            )
        try:
            valuation = self.service_client.value_ticker(ticker, mapped)
            assumption_meta["effective"] = effective_assumptions(valuation)
            payload = valuation_success_payload(
                tool,
                ticker,
                valuation,
                {
                    "researchedBaselineMode": mapped.get("researchedBaselineMode"),
                    "requestPolicyMode": mapped.get("requestPolicyMode"),
                },
            )
            payload["assumptions"] = assumption_meta
            return payload
        except ValuationServiceError as exc:
            payload = service_exception_payload(tool, exc, ticker=ticker)
            payload["assumptions"] = assumption_meta
            return payload

    def _get_assumptions(self, args: dict[str, Any]) -> dict[str, Any]:
        tool = "stockvaluation.get_assumptions"
        ticker, error = normalize_ticker(args.get("ticker"))
        if error:
            return error_payload(tool, "INVALID_TICKER", error, "invalid_ticker")
        try:
            valuation = self.service_client.value_ticker(ticker)
            return {
                "ok": True,
                "tool": tool,
                "ticker": ticker,
                "assumptions": extract_assumptions(valuation),
                "policy": policy_metadata(),
                "version": version_metadata(valuation),
            }
        except ValuationServiceError as exc:
            return service_exception_payload(tool, exc, ticker=ticker)

    def _get_growth_anchor(self, args: dict[str, Any]) -> dict[str, Any]:
        tool = "stockvaluation.get_growth_anchor"
        ticker, error = normalize_ticker(args.get("ticker"))
        if error:
            return error_payload(tool, "INVALID_TICKER", error, "invalid_ticker")
        try:
            valuation = self.service_client.value_ticker(ticker)
            return {
                "ok": True,
                "tool": tool,
                "ticker": ticker,
                "growthAnchor": extract_growth_anchor(valuation),
                "version": version_metadata(valuation),
            }
        except ValuationServiceError as exc:
            return service_exception_payload(tool, exc, ticker=ticker)

    def _get_reference_data_status(self, args: dict[str, Any]) -> dict[str, Any]:
        tool = "stockvaluation.get_reference_data_status"
        ticker_value = args.get("ticker")
        if ticker_value:
            ticker, error = normalize_ticker(ticker_value)
            if error:
                return error_payload(tool, "INVALID_TICKER", error, "invalid_ticker")
            try:
                valuation = self.service_client.value_ticker(ticker)
                return {
                    "ok": True,
                    "tool": tool,
                    "ticker": ticker,
                    "referenceData": reference_data_status(valuation),
                    "version": version_metadata(valuation),
                }
            except ValuationServiceError as exc:
                return service_exception_payload(tool, exc, ticker=ticker)
        health_payload = self._health({})
        return {
            "ok": health_payload.get("ok", False),
            "tool": tool,
            "service": health_payload.get("service"),
            "referenceData": reference_data_status({}),
            "version": {"mcp": mcp_metadata()},
        }

    def _explain_failure(self, args: dict[str, Any]) -> dict[str, Any]:
        return explain_failure(args.get("error"))


def normalize_ticker(raw: Any) -> tuple[str, str | None]:
    if not isinstance(raw, str):
        return "", "ticker must be a string."
    ticker = raw.strip().upper()
    if not ticker or not TICKER_RE.fullmatch(ticker):
        return "", "ticker must be 1-15 characters using letters, numbers, dots, or hyphens only."
    return ticker, None


def map_recalculate_overrides(requested: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    mapped: dict[str, Any] = {}
    unsupported: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    request_policy_mode, request_policy_error = normalize_request_policy_mode(requested.get("request_policy"))
    if request_policy_error is not None:
        unsupported["request_policy"] = request_policy_error
    autonomous_researched = request_policy_mode == "autonomous_researched"
    user_refined_scenario = request_policy_mode == "user_refined_scenario"
    for key, value in requested.items():
        if key in RECALCULATE_METADATA_FIELDS:
            metadata[key] = sanitize_for_agent(value)
            continue
        if key not in SUPPORTED_OVERRIDE_FIELDS:
            unsupported[key] = unsupported_override_field(key, value)
            continue
        if autonomous_researched and key not in AUTONOMOUS_RESEARCHED_FIELDS:
            unsupported[key] = {
                "value": sanitize_for_agent(value),
                "status": "scenario_only_in_autonomous_researched_mode",
                "reason": "scenario_only_in_autonomous_researched_mode",
                "message": f"{key} is available only for explicit user scenarios, not autonomous researched recalculation.",
            }
            continue
        if user_refined_scenario and key not in USER_REFINED_SCENARIO_FIELDS:
            unsupported[key] = {
                "value": sanitize_for_agent(value),
                "status": "explicit_scenario_only_in_user_refined_scenario_mode",
                "reason": "explicit_scenario_only_in_user_refined_scenario_mode",
                "message": f"{key} is available only for explicit scenarios, not bounded user-refined guided refinement.",
            }
            continue
        if key == "segments":
            segments, segment_error = map_segments(value)
            if segment_error is not None:
                unsupported[key] = {"value": sanitize_for_agent(value), **segment_error}
            else:
                mapped["segments"] = segments
            continue
        if key == "sector_overrides":
            sector_overrides = map_sector_overrides(value)
            if sector_overrides is None:
                unsupported[key] = {"value": sanitize_for_agent(value), "reason": "invalid_sector_overrides"}
            else:
                mapped["sectorOverrides"] = sector_overrides
            continue
        if key == "growth_pattern_override":
            growth_pattern = map_growth_pattern_override(value)
            if growth_pattern is None:
                unsupported[key] = {"value": sanitize_for_agent(value), "reason": "invalid_growth_pattern_override"}
            else:
                mapped["growthPatternOverride"] = growth_pattern
            continue
        number = _number_or_none(value)
        if number is None:
            unsupported[key] = {"value": sanitize_for_agent(value), "reason": "not_numeric"}
            continue
        if not math.isfinite(number):
            unsupported[key] = {
                "value": sanitize_for_agent(value),
                "status": "invalid_numeric_value",
                "reason": "not_finite",
                "message": f"{key} must be a finite numeric value.",
            }
            continue
        if key == "revenue_growth":
            mapped["compoundAnnualGrowth2_5"] = round(normalize_percent(number), 2)
        elif key == "operating_margin_next_year":
            mapped["operatingMarginNextYear"] = round(normalize_percent(number), 2)
        elif key == "operating_margin":
            mapped["targetPreTaxOperatingMargin"] = round(normalize_percent(number), 2)
        elif key in {"target_operating_margin", "target_pre_tax_operating_margin"}:
            mapped["targetPreTaxOperatingMargin"] = round(normalize_percent(number), 2)
        elif key in {"margin_convergence_year", "convergence_year_margin"}:
            if not within_bounds(number, MIN_MARGIN_CONVERGENCE_YEAR, MAX_MARGIN_CONVERGENCE_YEAR):
                unsupported[key] = bounded_numeric_unsupported(
                    key,
                    value,
                    MIN_MARGIN_CONVERGENCE_YEAR,
                    MAX_MARGIN_CONVERGENCE_YEAR,
                    "projection year",
                )
                continue
            mapped["convergenceYearMargin"] = round(number, 2)
        elif key == "sales_to_capital":
            normalized = normalize_sales_to_capital(number)
            if not within_bounds(normalized, MIN_SALES_TO_CAPITAL, MAX_SALES_TO_CAPITAL):
                unsupported[key] = bounded_numeric_unsupported(
                    key,
                    value,
                    MIN_SALES_TO_CAPITAL,
                    MAX_SALES_TO_CAPITAL,
                    "sales-to-capital multiple",
                )
                continue
            mapped["salesToCapitalYears1To5"] = round(normalized, 2)
            mapped["salesToCapitalYears6To10"] = round(normalized, 2)
        elif key == "sales_to_capital_years_1_to_5":
            normalized = normalize_sales_to_capital(number)
            if not within_bounds(normalized, MIN_SALES_TO_CAPITAL, MAX_SALES_TO_CAPITAL):
                unsupported[key] = bounded_numeric_unsupported(
                    key,
                    value,
                    MIN_SALES_TO_CAPITAL,
                    MAX_SALES_TO_CAPITAL,
                    "sales-to-capital multiple",
                )
                continue
            mapped["salesToCapitalYears1To5"] = round(normalized, 2)
        elif key == "sales_to_capital_years_6_to_10":
            normalized = normalize_sales_to_capital(number)
            if not within_bounds(normalized, MIN_SALES_TO_CAPITAL, MAX_SALES_TO_CAPITAL):
                unsupported[key] = bounded_numeric_unsupported(
                    key,
                    value,
                    MIN_SALES_TO_CAPITAL,
                    MAX_SALES_TO_CAPITAL,
                    "sales-to-capital multiple",
                )
                continue
            mapped["salesToCapitalYears6To10"] = round(normalized, 2)
        elif key == "wacc":
            mapped["initialCostCapital"] = round(normalize_percent(number), 2)
        elif key == "terminal_growth":
            mapped["terminalGrowthRate"] = round(normalize_percent(number), 2)
        elif key == "tax_rate":
            mapped["overrideAssumptionTaxRate"] = {
                "overrideCost": round(normalize_percent(number), 2),
                "isOverride": True,
                "additionalInputValue": 0.0,
                "additionalRadioValue": None,
            }
    if autonomous_researched:
        mapped["researchedBaselineMode"] = True
    if request_policy_mode is not None:
        mapped["requestPolicyMode"] = request_policy_mode
    return mapped, unsupported, metadata


def normalize_request_policy_mode(value: Any) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(value, dict):
        return None, None
    mode = str(value.get("mode") or value.get("baseline_mode") or "").strip().lower()
    if not mode:
        return None, None
    if mode not in REQUEST_POLICY_MODES:
        return None, {
            "value": sanitize_for_agent(value),
            "status": "invalid_request_policy_mode",
            "reason": "invalid_request_policy_mode",
            "message": "request_policy.mode must be one of mechanical_baseline, autonomous_researched, user_refined_scenario, or explicit_scenario.",
        }
    if mode in {"researched_autonomous", "researched_baseline"}:
        return "autonomous_researched", None
    return mode, None


def map_segments(value: Any) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    raw_segments = value.get("segments") if isinstance(value, dict) else value
    if not isinstance(raw_segments, list) or not raw_segments:
        return None, {"reason": "invalid_segments", "message": "segments must be a non-empty list."}

    validation = sanitize_segment_package({"segments": raw_segments})
    if validation["baseline_quality"] != "segment_weighted_baseline":
        warnings = validation.get("validation_warnings") or []
        return None, {
            "reason": str(validation["baseline_quality"]),
            "message": "; ".join(str(warning) for warning in warnings) or "segment package did not pass validation.",
        }

    segments: list[dict[str, Any]] = []
    for raw in raw_segments:
        if not isinstance(raw, dict):
            return None, {"reason": "invalid_segments", "message": "each segment must be a JSON object."}
        segment: dict[str, Any] = {}
        segment_name = _string_or_none(_first_present(raw.get("segment_name"), raw.get("segmentName"), raw.get("name")))
        sector = _string_or_none(_first_present(raw.get("sector"), raw.get("mapped_industry"), raw.get("mappedIndustry")))
        industry = _string_or_none(_first_present(raw.get("mapped_industry"), raw.get("mappedIndustry"), raw.get("industry")))
        if sector:
            segment["sector"] = sector
        if industry:
            segment["industry"] = industry
        if segment_name:
            segment["segmentName"] = segment_name
        components = raw.get("components")
        if components is not None:
            if not isinstance(components, list):
                return None, {"reason": "invalid_segments", "message": "components must be a list when present."}
            segment["components"] = [str(item) for item in components]
        elif segment_name:
            segment["components"] = [segment_name]
        for source_keys, target in [
            (("mapping_score", "mappingScore"), "mappingScore"),
            (("operating_margin", "operatingMargin"), "operatingMargin"),
        ]:
            raw_number = _first_present(*(raw.get(source_key) for source_key in source_keys))
            if raw_number is None:
                continue
            number = _number_or_none(raw_number)
            if number is None:
                return None, {"reason": "invalid_segments", "message": f"{target} must be numeric when present."}
            segment[target] = number
        revenue_share = parse_revenue_weight(raw)
        if revenue_share is None:
            return None, {"reason": "segment_evidence_insufficient", "message": "segment weighting requires sourced revenue weights or revenue amounts."}
        segment["revenueShare"] = round(revenue_share, 6)
        for source_keys, target in [
            (("mapping_confidence", "mappingConfidence"), "mappingConfidence"),
            (("source_name", "sourceName"), "sourceName"),
            (("source_date", "sourceDate"), "sourceDate"),
            (("source_url", "sourceUrl", "source_reference", "sourceReference"), "sourceUrl"),
        ]:
            text = _string_or_none(_first_present(*(raw.get(source_key) for source_key in source_keys)))
            if text:
                segment[target] = text
        validation_warnings = raw.get("validation_warnings") or raw.get("validationWarnings")
        if isinstance(validation_warnings, list):
            segment["validationWarnings"] = [str(item) for item in validation_warnings]
        if not segment:
            return None, {"reason": "invalid_segments", "message": "each segment must contain mapped fields."}
        segments.append(segment)
    return {"segments": segments}, None


def map_sector_overrides(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or not value:
        return None

    overrides: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            return None
        sector_name = _string_or_none(
            _first_present(raw.get("sector"), raw.get("sector_name"), raw.get("sectorName"))
        )
        parameter_type = _string_or_none(
            _first_present(raw.get("parameter"), raw.get("parameter_type"), raw.get("parameterType"))
        )
        parameter_aliases = {
            "target_operating_margin": "operating_margin",
            "target_pre_tax_operating_margin": "operating_margin",
            "reinvestment_sales_to_capital": "sales_to_capital",
        }
        if parameter_type in parameter_aliases:
            parameter_type = parameter_aliases[parameter_type]
        adjustment_type = _string_or_none(
            _first_present(raw.get("adjustment_type"), raw.get("adjustmentType"))
        )
        timeframe = _string_or_none(raw.get("timeframe")) or "both"
        number = _number_or_none(raw.get("value"))
        unit = (_string_or_none(raw.get("unit")) or "percent").lower()

        if (
            sector_name is None
            or parameter_type not in {"revenue_growth", "operating_margin", "sales_to_capital"}
            or adjustment_type not in {"absolute", "relative_multiplier", "relative_additive"}
            or timeframe not in {"years_1_to_5", "years_6_to_10", "both"}
            or number is None
            or unit not in {"percent", "x"}
        ):
            return None

        if unit == "percent":
            number = normalize_percent(number)
        elif parameter_type == "sales_to_capital":
            number = normalize_sales_to_capital(number)

        overrides.append(
            {
                "sectorName": sector_name,
                "parameterType": parameter_type,
                "value": round(number, 2),
                "adjustmentType": adjustment_type,
                "timeframe": timeframe,
            }
        )
    return overrides


def map_growth_pattern_override(value: Any) -> str | None:
    text = _string_or_none(value)
    if text is None:
        return None
    normalized = text.upper().replace("-", "_").replace(" ", "_")
    normalized = normalized.removesuffix("_GROWTH")
    aliases = {
        "STABLE": "STABLE",
        "TWO_STAGE": "TWO_STAGE",
        "THREE_STAGE": "THREE_STAGE",
        "N_STAGE": "N_STAGE",
        "NSTAGE": "N_STAGE",
    }
    return aliases.get(normalized)


def within_bounds(value: float, minimum: float, maximum: float) -> bool:
    return math.isfinite(value) and minimum <= value <= maximum


def bounded_numeric_unsupported(
    key: str,
    value: Any,
    minimum: float,
    maximum: float,
    unit: str,
) -> dict[str, Any]:
    return {
        "value": sanitize_for_agent(value),
        "status": "scenario_input_out_of_bounds",
        "reason": "scenario_input_out_of_bounds",
        "message": f"{key} must be between {minimum:g} and {maximum:g} {unit}.",
        "minimum": minimum,
        "maximum": maximum,
    }


def normalize_percent(value: float) -> float:
    if abs(value) <= 1.0:
        return value * 100.0
    return value


def normalize_sales_to_capital(value: float) -> float:
    if abs(value) > 50.0:
        return value / 100.0
    return value


def valuation_success_payload(
    tool: str,
    ticker: str,
    valuation: dict[str, Any],
    baseline_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = extract_baseline_contract(valuation, baseline_context)
    return {
        "ok": True,
        "tool": tool,
        "ticker": ticker,
        "valuation": sanitize_for_agent(valuation),
        "dcf": extract_dcf_summary(valuation),
        "baseline": baseline,
        "assumptions": extract_assumptions(valuation),
        "growthAnchor": extract_growth_anchor(valuation),
        "referenceData": reference_data_status(valuation),
        "version": version_metadata(valuation),
        "policy": policy_metadata(),
        "warnings": extract_warnings(valuation),
    }


def extract_baseline_contract(
    valuation: dict[str, Any],
    baseline_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    transparency = _dict(valuation.get("assumptionTransparency"))
    operating = _dict(transparency.get("operatingAssumptions"))
    context = baseline_context or {}

    baseline_quality = str(transparency.get("baselineQuality") or "single_industry_fallback")
    segment_aware = bool(transparency.get("segmentAware"))
    segment_count = _int_or_zero(transparency.get("segmentCount"))
    segment_coverage_pct = _number_or_none(transparency.get("segmentCoveragePct"))
    if segment_coverage_pct is None:
        segment_coverage_pct = 0.0
    mapped_industries = _string_list(transparency.get("mappedIndustries"))
    weighted_assumptions = _dict(transparency.get("weightedBaselineAssumptions"))
    researched_mode = bool(context.get("researchedBaselineMode"))

    baseline_use_status = _string_or_none(transparency.get("baselineUseStatus"))
    if baseline_use_status is None:
        baseline_use_status = derive_baseline_use_status(
            baseline_quality=baseline_quality,
            segment_aware=segment_aware,
            researched_mode=researched_mode,
        )

    target_margin = _first_present(
        operating.get("targetOperatingMargin"),
        extract_assumptions(valuation)["margin"]["targetOperatingMargin"],
    )
    target_status = _string_or_none(transparency.get("targetOperatingMarginStatus"))
    if target_status is None:
        target_status = "segment_weighted" if segment_aware else "single_industry_mechanical_fallback"
    target_source = _string_or_none(transparency.get("targetOperatingMarginSource"))
    if target_source is None:
        target_source = "Segment-weighted mechanical baseline" if segment_aware else "Single-industry mechanical fallback"

    warnings = _string_list(transparency.get("baselineWarnings"))
    unsupported_baseline_drivers = _issue_list(transparency.get("unsupportedBaselineDrivers"))
    if baseline_quality == "single_industry_fallback" and not segment_aware:
        warnings.append(
            "Single-industry mechanical fallback was used; target operating margin is not segment-weighted or researched evidence-supported."
        )
        if not any(item.get("field") == "target_operating_margin" for item in unsupported_baseline_drivers):
            unsupported_baseline_drivers.append(
                {
                    "field": "target_operating_margin",
                    "status": "mechanical_fallback",
                    "reason": "Target operating margin came from the company-level industry fallback, not validated segment weighting or governed evidence.",
                }
            )
    if researched_mode and not segment_aware:
        warnings.append(
            "researched baseline mode requires validated segment weighting or governed driver evidence; no valid segment package was used, so the baseline remains mechanical and challenged."
        )
        if not any(item.get("field") == "segments" for item in unsupported_baseline_drivers):
            unsupported_baseline_drivers.append(
                {
                    "field": "segments",
                    "status": "segment_evidence_insufficient",
                    "reason": "Researched baseline mode did not receive a validated segment package.",
                }
            )

    unsupported_adjustment_fields = _issue_list(transparency.get("unsupportedAdjustmentFields"))
    if not unsupported_adjustment_fields:
        unsupported_adjustment_fields = default_unsupported_adjustment_fields()

    return {
        "baselineQuality": baseline_quality,
        "baselineUseStatus": baseline_use_status,
        "requestPolicyMode": _string_or_none(transparency.get("requestPolicyMode"))
        or _string_or_none(context.get("requestPolicyMode")),
        "segmentAware": segment_aware,
        "segmentCount": segment_count,
        "segmentCoveragePct": round(segment_coverage_pct, 2),
        "mappedIndustries": mapped_industries,
        "weightedBaselineAssumptions": weighted_assumptions,
        "baselineWarnings": dedupe(warnings),
        "unsupportedBaselineDrivers": unsupported_baseline_drivers,
        "unsupportedAdjustmentFields": unsupported_adjustment_fields,
        "targetOperatingMargin": target_margin,
        "targetOperatingMarginSource": target_source,
        "targetOperatingMarginStatus": target_status,
    }


def derive_baseline_use_status(*, baseline_quality: str, segment_aware: bool, researched_mode: bool) -> str:
    if baseline_quality == "segment_weighted_baseline" and segment_aware:
        return "validated_segment_weighted"
    if researched_mode and not segment_aware:
        return "segment_evidence_insufficient"
    if baseline_quality.startswith("segment_") and baseline_quality != "segment_weighted_baseline":
        return "challenged_baseline"
    return "mechanical_only"


def default_unsupported_adjustment_fields() -> list[dict[str, str]]:
    return [
        {
            "field": "operating_margin_next_year",
            "status": "scenario_only_in_autonomous_researched_mode",
            "reason": "Next-year operating margin can be used for explicit user scenarios, but autonomous researched baselines must not change it.",
        },
        {
            "field": "wacc",
            "status": "scenario_only_in_autonomous_researched_mode",
            "reason": "WACC can be used for explicit scenarios, but autonomous researched baselines must not change it without a governed tested path.",
        },
        {
            "field": "terminal_growth",
            "status": "scenario_only_in_autonomous_researched_mode",
            "reason": "Terminal growth can be used for explicit scenarios, but autonomous researched baselines must not change it without a governed tested path.",
        },
        {
            "field": "tax_rate",
            "status": "scenario_only_in_autonomous_researched_mode",
            "reason": "Tax-rate changes are report-only or explicit-scenario fields in autonomous researched mode.",
        },
        {"field": "rd_capitalization", "status": "blocked_report_only", "reason": "R&D capitalization is explain/flag only unless a governed service contract applies it."},
        {"field": "leases", "status": "blocked_report_only", "reason": "Lease adjustments are explain/flag only unless a governed service contract applies them."},
        {"field": "options", "status": "blocked_report_only", "reason": "Options and warrants are explain/flag only unless a governed service contract applies them."},
        {"field": "nols", "status": "blocked_report_only", "reason": "NOL adjustments are explain/flag only unless a governed service contract applies them."},
        {"field": "cash", "status": "blocked_report_only", "reason": "Cash adjustments are report-only for autonomous researched baselines."},
        {"field": "debt", "status": "blocked_report_only", "reason": "Debt adjustments are report-only for autonomous researched baselines."},
        {"field": "share_count", "status": "blocked_report_only", "reason": "Share-count adjustments are report-only for autonomous researched baselines."},
        {"field": "accounting_adjustments", "status": "blocked_report_only", "reason": "Accounting cleanup fields are report-only unless an explicit governed service input is supported."},
    ]


def unsupported_override_field(key: str, value: Any) -> dict[str, Any]:
    if key in DIRECT_VALUATION_OUTPUT_FIELDS:
        return {
            "value": sanitize_for_agent(value),
            "status": "direct_valuation_output_rejected",
            "reason": "direct_valuation_output_rejected",
            "message": f"{key} is a valuation output or market-price calibration field, not a valid recalculate input.",
        }
    if key in REPORT_ONLY_OVERRIDE_FIELDS:
        return {
            "value": sanitize_for_agent(value),
            "status": "blocked_report_only",
            "reason": "blocked_report_only",
            "message": f"{key} is report-only in autonomous researched recalculation unless a governed service contract explicitly supports it.",
        }
    return {
        "value": sanitize_for_agent(value),
        "status": "unsupported_override_field",
        "reason": "unsupported_override_field",
        "message": f"{key} is not governed by the MCP recalculate contract.",
    }


def blocked_baseline_contract(unsupported: dict[str, Any]) -> dict[str, Any]:
    warnings = ["Recalculate was blocked before valuation-service execution because unsupported overrides were requested."]
    return {
        "baselineQuality": "not_calculated",
        "baselineUseStatus": "blocked",
        "segmentAware": False,
        "segmentCount": 0,
        "segmentCoveragePct": 0.0,
        "mappedIndustries": [],
        "weightedBaselineAssumptions": {},
        "baselineWarnings": warnings,
        "unsupportedBaselineDrivers": [],
        "unsupportedAdjustmentFields": [
            {
                "field": key,
                "status": _dict(value).get("status") or _dict(value).get("reason") or "unsupported_override_field",
                "reason": _dict(value).get("message") or _dict(value).get("reason") or "Unsupported override.",
            }
            for key, value in unsupported.items()
        ],
        "targetOperatingMargin": None,
        "targetOperatingMarginSource": None,
        "targetOperatingMarginStatus": "blocked",
    }


def extract_dcf_summary(valuation: dict[str, Any]) -> dict[str, Any]:
    company = _dict(valuation.get("companyDTO"))
    financial = _dict(valuation.get("financialDTO"))
    terminal = _dict(valuation.get("terminalValueDTO"))
    return {
        "companyName": valuation.get("companyName"),
        "currency": valuation.get("currency"),
        "stockCurrency": valuation.get("stockCurrency"),
        "primaryModel": valuation.get("primaryModel"),
        "growthPattern": valuation.get("growthPattern"),
        "projectionYears": valuation.get("projectionYears"),
        "estimatedValuePerShare": company.get("estimatedValuePerShare") or financial.get("intrinsicValue"),
        "marketPrice": company.get("price"),
        "valueOfEquity": company.get("valueOfEquity"),
        "numberOfShares": company.get("numberOfShares"),
        "terminalGrowthRate": terminal.get("growthRate"),
        "terminalCostOfCapital": terminal.get("costOfCapital"),
    }


def extract_assumptions(valuation: dict[str, Any]) -> dict[str, Any]:
    transparency = _dict(valuation.get("assumptionTransparency"))
    operating = _dict(transparency.get("operatingAssumptions"))
    discount = _dict(transparency.get("discountRate"))
    terminal = _dict(valuation.get("terminalValueDTO"))
    financial = _dict(valuation.get("financialDTO"))
    tax_rate = _first_present(operating.get("taxRate"), _last_number(financial.get("taxRate")))
    return {
        "growth": {
            "revenueGrowthRateYears2To5": _first_present(
                operating.get("revenueGrowthRateYears2To5"),
                _last_number(financial.get("revenueGrowthRate")),
            ),
            "source": operating.get("revenueGrowthSource"),
            "rationale": operating.get("revenueGrowthRationale"),
        },
        "margin": {
            "operatingMarginNextYear": operating.get("operatingMarginNextYear"),
            "targetOperatingMargin": _first_present(
                operating.get("targetOperatingMargin"),
                _last_number(financial.get("ebitOperatingMargin")),
            ),
            "convergenceYearMargin": operating.get("convergenceYearMargin"),
            "source": operating.get("operatingMarginSource"),
            "rationale": operating.get("operatingMarginRationale"),
        },
        "salesToCapital": {
            "years1To5": _first_present(
                operating.get("salesToCapitalYears1To5"),
                _last_number(financial.get("salesToCapitalRatio")),
            ),
            "years6To10": operating.get("salesToCapitalYears6To10"),
            "source": operating.get("salesToCapitalSource"),
            "rationale": operating.get("salesToCapitalRationale"),
        },
        "costOfCapital": {
            "riskFreeRate": discount.get("riskFreeRate"),
            "initialCostOfCapital": _first_present(
                discount.get("initialCostOfCapital"),
                _first_number(financial.get("costOfCapital")),
            ),
            "terminalCostOfCapital": _first_present(
                discount.get("terminalCostOfCapital"),
                terminal.get("costOfCapital"),
            ),
            "source": {
                "riskFreeRate": discount.get("riskFreeRateSource"),
                "equityRiskPremium": discount.get("equityRiskPremiumSource"),
                "initialCostOfCapital": discount.get("initialCostOfCapitalSource"),
            },
        },
        "terminalGrowth": {
            "rate": terminal.get("growthRate"),
            "limitNote": "Compare terminal growth to inflation and mature economy growth before presenting scenarios.",
        },
        "taxRate": tax_rate,
        "accountingAdjustments": {
            "rdCapitalization": valuation.get("rdCapitalization") or valuation.get("rdCapitalized"),
            "operatingLeaseConversion": valuation.get("operatingLeaseConversion"),
            "optionsOrWarrants": valuation.get("optionValueResultDTO") or valuation.get("valueOfOptions"),
        },
        "source": "valuation-service",
        "rationale": {
            "templateSelection": valuation.get("templateSelectionReason")
            or transparency.get("templateSelectionReason"),
            "modelSelection": valuation.get("modelSelectionRationale"),
        },
    }


def effective_assumptions(valuation: dict[str, Any]) -> dict[str, Any]:
    assumptions = extract_assumptions(valuation)
    return {
        "revenue_growth": assumptions["growth"]["revenueGrowthRateYears2To5"],
        "operating_margin_next_year": assumptions["margin"]["operatingMarginNextYear"],
        "operating_margin": assumptions["margin"]["targetOperatingMargin"],
        "target_operating_margin": assumptions["margin"]["targetOperatingMargin"],
        "margin_convergence_year": assumptions["margin"]["convergenceYearMargin"],
        "sales_to_capital": assumptions["salesToCapital"]["years1To5"],
        "sales_to_capital_years_1_to_5": assumptions["salesToCapital"]["years1To5"],
        "sales_to_capital_years_6_to_10": assumptions["salesToCapital"]["years6To10"],
        "wacc": assumptions["costOfCapital"]["initialCostOfCapital"],
        "terminal_growth": assumptions["terminalGrowth"]["rate"],
        "tax_rate": assumptions["taxRate"],
    }


def extract_growth_anchor(valuation: dict[str, Any]) -> dict[str, Any]:
    transparency = _dict(valuation.get("assumptionTransparency"))
    anchor = _dict(transparency.get("growthAnchor") or valuation.get("growthSkillContext"))
    warnings = []
    confidence = anchor.get("confidenceScore")
    if confidence is None:
        warnings.append("No growth-anchor confidence score was returned by valuation-service.")
    elif isinstance(confidence, (int, float)) and confidence < 0.5:
        warnings.append("Growth-anchor confidence is weak; treat industry comparison as directional.")
    return {
        "mappedEntity": anchor.get("entity"),
        "mappedEntityDisplay": anchor.get("entityDisplay"),
        "region": anchor.get("region"),
        "year": anchor.get("year"),
        "confidence": confidence,
        "percentileBand": {
            "p25": anchor.get("p25"),
            "p50": anchor.get("p50"),
            "p75": anchor.get("p75"),
        },
        "sourceDate": anchor.get("sourceDate") or anchor.get("year"),
        "source": anchor.get("source") or "valuation-service growth anchor",
        "warnings": warnings,
    }


def reference_data_status(valuation: dict[str, Any]) -> dict[str, Any]:
    anchor = extract_growth_anchor(valuation)
    return {
        "valuationServiceUrl": DEFAULT_SERVICE_URL,
        "marketData": {
            "provider": "Yahoo Finance via local yfinance service",
            "status": "queried_by_valuation_service" if valuation else "unknown_until_ticker_request",
            "warnings": ["Yahoo Finance coverage can be missing, stale, or insufficient for some companies."],
        },
        "damodaranReferenceData": {
            "status": "available_when_growth_anchor_present" if anchor.get("mappedEntity") else "not_returned",
            "mappedEntity": anchor.get("mappedEntity"),
            "region": anchor.get("region"),
            "year": anchor.get("year"),
            "sourceDate": anchor.get("sourceDate"),
            "confidence": anchor.get("confidence"),
            "warnings": anchor.get("warnings", []),
        },
    }


def version_metadata(valuation: dict[str, Any]) -> dict[str, Any]:
    return {
        "mcp": mcp_metadata(),
        "valuationService": {
            "serviceVersion": valuation.get("serviceVersion"),
            "dataVersion": valuation.get("dataVersion"),
            "modelVersion": valuation.get("modelVersion"),
        },
    }


def mcp_metadata() -> dict[str, Any]:
    return {
        "name": "valuation-agent",
        "version": __version__,
        "protocolVersion": SUPPORTED_PROTOCOL_VERSIONS[0],
        "supportedProtocolVersions": list(SUPPORTED_PROTOCOL_VERSIONS),
    }


def policy_metadata() -> dict[str, Any]:
    return {
        "educationalUseOnly": True,
        "notFinancialAdvice": True,
        "reportWriter": "user-agent",
        "prohibitedRecommendationLanguage": ["buy", "sell", "hold", "target price", "should invest"],
    }


def extract_warnings(valuation: dict[str, Any]) -> list[str]:
    transparency = _dict(valuation.get("assumptionTransparency"))
    notes = transparency.get("notes")
    if isinstance(notes, list):
        return [str(item) for item in notes]
    return []


def service_exception_payload(tool: str, exc: Exception, ticker: str | None = None) -> dict[str, Any]:
    if isinstance(exc, ServiceUnavailable):
        return error_payload(
            tool,
            "MISSING_LOCAL_SERVICE",
            "Local valuation service is not reachable.",
            "missing_local_service",
            extra={"ticker": ticker, "detail": sanitize_for_agent(str(exc))},
        )
    if isinstance(exc, NonJsonServiceResponse):
        return error_payload(
            tool,
            "NON_JSON_SERVICE_RESPONSE",
            "Local valuation service returned a non-JSON response.",
            "non_json_service_response",
            extra={"ticker": ticker, "detail": sanitize_for_agent(str(exc))},
        )
    if isinstance(exc, ServiceHTTPError):
        category = classify_failure(exc.message)
        if category == "unknown_failure" and exc.status >= 500:
            category = "upstream_service_error"
        return error_payload(
            tool,
            failure_code_for_category(category),
            exc.message,
            category,
            extra={"ticker": ticker, "status": exc.status, "upstream": sanitize_for_agent(exc.payload or {})},
        )
    if isinstance(exc, ValuationServiceError):
        category = classify_failure(str(exc))
        return error_payload(
            tool,
            failure_code_for_category(category),
            str(sanitize_for_agent(str(exc))),
            category,
            extra={"ticker": ticker},
        )
    return error_payload(tool, "VALUATION_SERVICE_ERROR", str(sanitize_for_agent(str(exc))), "unknown_failure")


def explain_failure(error: Any) -> dict[str, Any]:
    message = extract_failure_message(error)
    existing_category = extract_failure_category(error)
    category = existing_category if existing_category and existing_category != "unknown_failure" else classify_failure(message)
    if category == "unknown_failure" and existing_category:
        category = existing_category
    return {
        "ok": True,
        "tool": "stockvaluation.explain_failure",
        "failureCategory": category,
        "message": sanitize_for_agent(message),
        "recovery": recovery_for_category(category),
    }


def extract_failure_category(error: Any) -> str | None:
    if isinstance(error, str):
        stripped = error.strip()
        if not stripped:
            return None
        try:
            return extract_failure_category(json.loads(stripped))
        except json.JSONDecodeError:
            return None
    if isinstance(error, dict):
        for key in ("failureCategory", "failure_category", "code"):
            category = normalize_failure_category(error.get(key))
            if category:
                return category
        nested = error.get("error")
        if isinstance(nested, dict):
            for key in ("failureCategory", "failure_category", "code"):
                category = normalize_failure_category(nested.get(key))
                if category:
                    return category
    return None


def normalize_failure_category(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("-", "_")
    if normalized in KNOWN_FAILURE_CATEGORIES:
        return normalized
    return None


def extract_failure_message(error: Any) -> str:
    if isinstance(error, str):
        stripped = error.strip()
        if stripped:
            try:
                return extract_failure_message(json.loads(stripped))
            except json.JSONDecodeError:
                return stripped
        return str(error)
    if isinstance(error, dict):
        direct = error.get("message")
        if isinstance(direct, str) and direct.strip():
            return direct
        nested = error.get("error")
        if isinstance(nested, dict):
            nested_message = nested.get("message") or nested.get("error")
            if isinstance(nested_message, str) and nested_message.strip():
                return nested_message
            nested_code = nested.get("code")
            if isinstance(nested_code, str) and nested_code.strip():
                return nested_code
        if isinstance(nested, str) and nested.strip():
            return nested
        code = error.get("code")
        if isinstance(code, str) and code.strip():
            return code
    return str(error)


def classify_failure(message: str) -> str:
    lowered = message.lower()
    if (
        "currency" in lowered
        and any(term in lowered for term in ("conversion failed", "differs", "convert", "exchange-rate"))
    ):
        return "currency_conversion_failed"
    if (
        ("frankfurter" in lowered or "currency provider" in lowered)
        and any(term in lowered for term in ("unavailable", "failed", "missing", "rate", "loading"))
    ):
        return "currency_conversion_failed"
    if any(
        term in lowered
        for term in (
            "financial company",
            "financial sector",
            "financial services sector",
            "bank",
            "insurance",
            "unsupported",
        )
    ):
        return "unsupported_company"
    if "insufficient" in lowered or "missing financial" in lowered or "not enough financial" in lowered:
        return "insufficient_financial_data"
    if any(term in lowered for term in ("configuration", "environment variable", "required")):
        return "missing_configuration"
    if "stale" in lowered and "reference" in lowered:
        return "stale_reference_data"
    if "non-json" in lowered or "non json" in lowered or "html" in lowered:
        return "non_json_service_response"
    if "connection" in lowered or "refused" in lowered or "unreachable" in lowered or "timed out" in lowered:
        return "missing_local_service"
    if "upstream" in lowered or "dependency" in lowered or "service error" in lowered:
        return "upstream_service_error"
    return "unknown_failure"


def failure_code_for_category(category: str) -> str:
    return {
        "unsupported_company": "UNSUPPORTED_COMPANY",
        "insufficient_financial_data": "INSUFFICIENT_FINANCIAL_DATA",
        "missing_configuration": "MISSING_CONFIGURATION",
        "stale_reference_data": "STALE_REFERENCE_DATA",
        "non_json_service_response": "NON_JSON_SERVICE_RESPONSE",
        "missing_local_service": "MISSING_LOCAL_SERVICE",
        "currency_conversion_failed": "CURRENCY_CONVERSION_FAILED",
        "upstream_service_error": "UPSTREAM_SERVICE_ERROR",
    }.get(category, "VALUATION_SERVICE_ERROR")


def recovery_for_category(category: str) -> dict[str, Any]:
    recovery = {
        "unsupported_company": "Explain that the company type is unsupported and do not invent a DCF.",
        "insufficient_financial_data": "Tell the user which data is missing and avoid filling gaps with invented values.",
        "missing_configuration": "Ask the user to run `sv check-env` and configure the missing local environment variable.",
        "stale_reference_data": "Show the stale-data warning and treat growth anchors as directional.",
        "non_json_service_response": "Ask the user to run `sv service status`; the service may be returning an error page.",
        "missing_local_service": "Ask the user to run `sv service start` and then retry the MCP call.",
        "currency_conversion_failed": "Explain that valuation-service could not safely complete currency conversion. Ask the user to verify Frankfurter currency provider availability, then retry; do not manually convert and invent the valuation.",
        "upstream_service_error": "Tell the user the local valuation service returned an upstream error. Ask them to run `sv service status`, retry once, and preserve the failure category if it repeats.",
        "invalid_ticker": "Ask for a valid public ticker symbol.",
        "unsupported_overrides": "Ask before retrying with only governed scenario override fields.",
        "unknown_failure": "Summarize the failure and ask the user whether to run service status checks.",
    }
    return {
        "agentAction": recovery.get(category, recovery["unknown_failure"]),
        "canRetry": category in {"missing_local_service", "non_json_service_response", "missing_configuration"},
    }


def error_payload(
    tool: str,
    code: str,
    message: str,
    category: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "tool": tool,
        "failureCategory": category,
        "error": {
            "code": code,
            "message": sanitize_for_agent(message),
        },
        "recovery": recovery_for_category(category),
        "policy": policy_metadata(),
    }
    if extra:
        payload.update({key: sanitize_for_agent(value) for key, value in extra.items() if value is not None})
    return payload


def tool_result(payload: dict[str, Any], is_error: bool) -> dict[str, Any]:
    safe_payload = sanitize_for_agent(payload)
    return {
        "content": [
            {
                "type": "text",
                "text": compact_text_content(safe_payload, is_error),
            }
        ],
        "structuredContent": safe_payload,
        "isError": is_error,
    }


def compact_text_content(payload: dict[str, Any], is_error: bool) -> str:
    tool = str(payload.get("tool") or "stockvaluation")
    ticker = _string_or_none(payload.get("ticker"))
    subject = f"{tool} {ticker}" if ticker else tool
    if is_error or not payload.get("ok"):
        error = _dict(payload.get("error"))
        recovery = _dict(payload.get("recovery"))
        code = _string_or_none(error.get("code")) or "ERROR"
        category = _string_or_none(payload.get("failureCategory")) or "unknown_failure"
        message = _string_or_none(error.get("message")) or "The tool call failed."
        action = _string_or_none(recovery.get("agentAction"))
        parts = [
            f"{subject}: error {code} ({category}).",
            message,
        ]
        if action:
            parts.append(f"Recovery: {action}")
        parts.append("Full details are in structuredContent.")
        return " ".join(parts)

    policy = _dict(payload.get("policy"))
    policy_text = ""
    if policy.get("educationalUseOnly") or policy.get("notFinancialAdvice"):
        policy_text = " Educational use only; not financial advice."

    dcf = _dict(payload.get("dcf"))
    if dcf:
        company_name = _string_or_none(dcf.get("companyName"))
        currency = _string_or_none(dcf.get("currency")) or _string_or_none(dcf.get("stockCurrency"))
        estimated_value = compact_number(dcf.get("estimatedValuePerShare"))
        market_price = compact_number(dcf.get("marketPrice"))
        baseline = _dict(payload.get("baseline"))
        baseline_status = _string_or_none(baseline.get("baselineUseStatus"))
        summary = f"{subject}: ok."
        if company_name:
            summary += f" {company_name}."
        if estimated_value is not None:
            value_text = f" Estimated value/share {estimated_value}"
            if currency:
                value_text += f" {currency}"
            summary += value_text + "."
        if market_price is not None:
            price_text = f" Market price {market_price}"
            if currency:
                price_text += f" {currency}"
            summary += price_text + "."
        if baseline_status:
            summary += f" Baseline use {baseline_status}."
        return f"{summary}{policy_text} Full JSON is in structuredContent."

    if tool == "stockvaluation.health":
        service = _dict(payload.get("service"))
        status = _string_or_none(service.get("status")) or "unknown"
        return f"{subject}: ok. Service status {status}.{policy_text} Full JSON is in structuredContent."

    if tool == "stockvaluation.get_assumptions":
        return f"{subject}: ok. Assumption transparency returned.{policy_text} Full JSON is in structuredContent."

    if tool == "stockvaluation.get_growth_anchor":
        anchor = _dict(payload.get("growthAnchor"))
        entity = _string_or_none(anchor.get("mappedEntityDisplay")) or _string_or_none(anchor.get("mappedEntity"))
        suffix = f" Growth anchor {entity}." if entity else " Growth anchor returned."
        return f"{subject}: ok.{suffix}{policy_text} Full JSON is in structuredContent."

    if tool == "stockvaluation.get_reference_data_status":
        return f"{subject}: ok. Reference-data status returned.{policy_text} Full JSON is in structuredContent."

    if tool == "stockvaluation.explain_failure":
        category = _string_or_none(payload.get("failureCategory")) or "unknown_failure"
        message = _string_or_none(payload.get("message")) or "Failure classified."
        return f"{subject}: ok. {category}: {message} Full JSON is in structuredContent."

    return f"{subject}: ok.{policy_text} Full JSON is in structuredContent."


def compact_number(value: Any) -> str | None:
    number = _number_or_none(value)
    if number is None:
        return None
    if abs(number) >= 1000:
        return f"{number:,.2f}"
    return f"{number:.2f}"


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _issue_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    issues: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        field = _string_or_none(item.get("field"))
        if field is None:
            continue
        issues.append(
            {
                "field": field,
                "status": _string_or_none(item.get("status")) or "",
                "reason": _string_or_none(item.get("reason")) or _string_or_none(item.get("message")) or "",
            }
        )
    return issues


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _first_number(values: Any) -> float | None:
    if not isinstance(values, list):
        return None
    for value in values:
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _last_number(values: Any) -> float | None:
    if not isinstance(values, list):
        return None
    for value in reversed(values):
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None
