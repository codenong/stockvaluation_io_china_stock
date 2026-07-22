"""Deterministic per-driver anchor sets for material numeric scenario drivers.

Anchors are pure functions of the run's structured facts: prospectus packet
financial history, offering terms, or the service baseline assumptions. The
same inputs always yield identical anchors, and no model-supplied value ever
enters the computation. A guided "default" is defined as the base anchor.
"""

from __future__ import annotations

import math
from typing import Any

ANCHOR_SCHEMA_VERSION = "driver_anchors.v1"

GROWTH_LOW_FACTOR = 0.5
GROWTH_HIGH_FACTOR = 1.25
MARGIN_LOW_FACTOR = 0.5
MARGIN_HIGH_FACTOR = 1.5
BASELINE_LOW_FACTOR = 0.8
BASELINE_HIGH_FACTOR = 1.2
SALES_TO_CAPITAL_MIN = 0.05
SALES_TO_CAPITAL_MAX = 20.0

# Prospectus scenario keys that carry the same number as an anchored driver
# field (see guided_prospectus_scenario_candidate).
PROSPECTUS_SCENARIO_KEY_TO_DRIVER_FIELD = {
    "net_proceeds": "net_proceeds",
    "compound_annual_growth_2_5": "revenue_growth",
    "target_revenue": "terminal_revenue",
    "terminal_return_on_capital": "terminal_roic",
    "target_operating_margin": "target_operating_margin",
    "sales_to_capital_years_1_to_5": "sales_to_capital",
    "sales_to_capital_years_6_to_10": "sales_to_capital",
}

# Scenario keys the MCP layer sets when valuing the low/high anchor set for
# an unresolved driver field in prospectus mode.
ANCHOR_FIELD_TO_PROSPECTUS_KEYS = {
    "revenue_growth": ("compound_annual_growth_2_5",),
    "target_operating_margin": ("target_operating_margin",),
    "sales_to_capital": ("sales_to_capital_years_1_to_5", "sales_to_capital_years_6_to_10"),
    "net_proceeds": ("net_proceeds",),
}

# Recalculate override keys that carry the same number as an anchored driver
# field.
RECALCULATE_KEY_TO_DRIVER_FIELD = {
    "net_proceeds": "net_proceeds",
    "revenue_growth": "revenue_growth",
    "terminal_revenue": "terminal_revenue",
    "target_revenue": "terminal_revenue",
    "revenue_year_10": "terminal_revenue",
    "year_10_revenue": "terminal_revenue",
    "operating_margin": "target_operating_margin",
    "target_operating_margin": "target_operating_margin",
    "target_pre_tax_operating_margin": "target_operating_margin",
    "sales_to_capital": "sales_to_capital",
    "sales_to_capital_years_1_to_5": "sales_to_capital",
    "sales_to_capital_years_6_to_10": "sales_to_capital",
    "wacc": "wacc",
    "terminal_roic": "terminal_roic",
    "terminal_return_on_capital": "terminal_roic",
    "terminal_return_on_invested_capital": "terminal_roic",
}

# Numeric scenario keys that are driver inputs but may have no computable
# anchor; on tracked runs these require an explicit user-input flag.
NUMERIC_DRIVER_KEYS = set(PROSPECTUS_SCENARIO_KEY_TO_DRIVER_FIELD) | set(RECALCULATE_KEY_TO_DRIVER_FIELD) | {
    "operating_margin_next_year",
    "margin_convergence_year",
    "convergence_year_margin",
    "wacc",
    "terminal_growth",
    "tax_rate",
}


def _round2(value: float) -> float:
    return round(value, 2)


def _anchor(value: float, provenance: str) -> dict[str, Any]:
    return {"value": _round2(value), "provenance": provenance}


def _anchor_set(field: str, unit: str, low: dict[str, Any], base: dict[str, Any], high: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": ANCHOR_SCHEMA_VERSION,
        "driver": field,
        "field": field,
        "unit": unit,
        "anchors": {"low": low, "base": base, "high": high},
    }


def anchor_values(anchor_set: dict[str, Any]) -> dict[str, float]:
    anchors = anchor_set.get("anchors") if isinstance(anchor_set, dict) else None
    values: dict[str, float] = {}
    for label in ("low", "base", "high"):
        entry = (anchors or {}).get(label)
        if isinstance(entry, dict) and isinstance(entry.get("value"), (int, float)):
            values[label] = float(entry["value"])
    return values


def _first_value_per_period(rows: Any) -> dict[str, float]:
    """First occurrence per fiscal period, in packet order (consolidated rows
    precede segment duplicates in extraction output)."""
    values: dict[str, float] = {}
    if not isinstance(rows, list):
        return values
    for row in rows:
        if not isinstance(row, dict):
            continue
        period = row.get("periodEnd")
        value = row.get("normalizedValue")
        if not isinstance(period, str) or not isinstance(value, (int, float)):
            continue
        if not math.isfinite(float(value)):
            continue
        values.setdefault(period, float(value))
    return values


def _income_statement_series(packet: dict[str, Any], fields: tuple[str, ...]) -> dict[str, float]:
    rows = (((packet.get("financials") or {}).get("incomeStatement")) or [])
    selected = [row for row in rows if isinstance(row, dict) and row.get("canonicalField") in fields]
    return _first_value_per_period(selected)


def _cash_flow_series(packet: dict[str, Any], field: str) -> dict[str, float]:
    rows = (((packet.get("financials") or {}).get("cashFlowOrCapex")) or [])
    selected = [row for row in rows if isinstance(row, dict) and row.get("canonicalField") == field]
    return _first_value_per_period(selected)


def anchors_from_prospectus_packet(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Anchor sets derived only from the reviewed extraction packet."""
    if not isinstance(packet, dict):
        return {}
    anchors: dict[str, dict[str, Any]] = {}

    revenue = _income_statement_series(packet, ("revenue", "prior_revenue"))
    periods = sorted(revenue)
    if len(periods) >= 2 and revenue[periods[0]] > 0:
        oldest, latest = periods[0], periods[-1]
        span = len(periods) - 1
        cagr_pct = ((revenue[latest] / revenue[oldest]) ** (1.0 / span) - 1.0) * 100.0
        source = f"filing_revenue_history: FY{oldest[:4]}-FY{latest[:4]} revenue CAGR from the prospectus income statement"
        anchors["revenue_growth"] = _anchor_set(
            "revenue_growth",
            "percent",
            _anchor(cagr_pct * GROWTH_LOW_FACTOR, f"{source}; low rule: {GROWTH_LOW_FACTOR}x CAGR"),
            _anchor(cagr_pct, f"{source}; base rule: CAGR as reported"),
            _anchor(cagr_pct * GROWTH_HIGH_FACTOR, f"{source}; high rule: {GROWTH_HIGH_FACTOR}x CAGR"),
        )

    operating_income = _income_statement_series(packet, ("operating_income",))
    margins = {
        period: operating_income[period] / revenue[period] * 100.0
        for period in operating_income
        if period in revenue and revenue[period] > 0
    }
    if margins:
        best_period = max(sorted(margins), key=lambda period: margins[period])
        best_margin = margins[best_period]
        if best_margin > 0:
            source = f"filing_margin_history: best reported operating margin FY{best_period[:4]} from the prospectus income statement"
            anchors["target_operating_margin"] = _anchor_set(
                "target_operating_margin",
                "percent",
                _anchor(best_margin * MARGIN_LOW_FACTOR, f"{source}; low rule: {MARGIN_LOW_FACTOR}x best margin"),
                _anchor(best_margin, f"{source}; base rule: best reported margin"),
                _anchor(best_margin * MARGIN_HIGH_FACTOR, f"{source}; high rule: {MARGIN_HIGH_FACTOR}x best margin"),
            )

    capex = _cash_flow_series(packet, "capital_expenditures")
    if len(periods) >= 2:
        latest = periods[-1]
        previous = periods[-2]
        revenue_delta = revenue[latest] - revenue[previous]
        latest_capex = capex.get(latest)
        if latest_capex and latest_capex > 0 and revenue_delta > 0:
            ratio = revenue_delta / latest_capex
            ratio = max(SALES_TO_CAPITAL_MIN, min(SALES_TO_CAPITAL_MAX, ratio))
            source = (
                f"filing_reinvestment_history: FY{latest[:4]} revenue change / FY{latest[:4]} capital expenditures from the prospectus"
            )
            anchors["sales_to_capital"] = _anchor_set(
                "sales_to_capital",
                "ratio",
                _anchor(max(SALES_TO_CAPITAL_MIN, ratio * BASELINE_LOW_FACTOR), f"{source}; low rule: {BASELINE_LOW_FACTOR}x ratio"),
                _anchor(ratio, f"{source}; base rule: ratio as computed"),
                _anchor(min(SALES_TO_CAPITAL_MAX, ratio * BASELINE_HIGH_FACTOR), f"{source}; high rule: {BASELINE_HIGH_FACTOR}x ratio"),
            )

    offering = packet.get("offering") or {}
    net_proceeds = offering.get("netProceeds") if isinstance(offering, dict) else None
    if isinstance(net_proceeds, (int, float)) and net_proceeds > 0:
        source = "offering_terms: net proceeds disclosed in the prospectus offering section"
        anchors["net_proceeds"] = _anchor_set(
            "net_proceeds",
            "USD",
            _anchor(float(net_proceeds), f"{source}; single disclosed value"),
            _anchor(float(net_proceeds), f"{source}; single disclosed value"),
            _anchor(float(net_proceeds), f"{source}; single disclosed value"),
        )

    return anchors


def _first_finite(values: Any, skip_first: bool = True) -> float | None:
    if not isinstance(values, list):
        return None
    candidates = values[1:] if skip_first else values
    for value in candidates:
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return None


def _last_finite(values: Any) -> float | None:
    if not isinstance(values, list):
        return None
    for value in reversed(values):
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return None


def anchors_from_valuation_baseline(valuation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Anchor sets derived only from the deterministic service baseline."""
    if not isinstance(valuation, dict):
        return {}
    financial = valuation.get("financialDTO") or {}
    if not isinstance(financial, dict):
        return {}
    anchors: dict[str, dict[str, Any]] = {}

    growth = _first_finite(financial.get("revenueGrowthRate"))
    if growth is not None:
        source = "service_baseline: revenue growth from the deterministic valuation-service baseline"
        anchors["revenue_growth"] = _anchor_set(
            "revenue_growth",
            "percent",
            _anchor(growth * BASELINE_LOW_FACTOR, f"{source}; low rule: {BASELINE_LOW_FACTOR}x baseline"),
            _anchor(growth, f"{source}; base rule: baseline as returned"),
            _anchor(growth * BASELINE_HIGH_FACTOR, f"{source}; high rule: {BASELINE_HIGH_FACTOR}x baseline"),
        )

    margin = _last_finite(financial.get("ebitOperatingMargin"))
    if margin is not None and margin > 0:
        source = "service_baseline: terminal-year operating margin from the deterministic valuation-service baseline"
        anchors["target_operating_margin"] = _anchor_set(
            "target_operating_margin",
            "percent",
            _anchor(margin * BASELINE_LOW_FACTOR, f"{source}; low rule: {BASELINE_LOW_FACTOR}x baseline"),
            _anchor(margin, f"{source}; base rule: baseline as returned"),
            _anchor(margin * BASELINE_HIGH_FACTOR, f"{source}; high rule: {BASELINE_HIGH_FACTOR}x baseline"),
        )

    sales_to_capital = _first_finite(financial.get("salesToCapitalRatio"))
    if sales_to_capital is not None and sales_to_capital > 0:
        source = "service_baseline: sales-to-capital from the deterministic valuation-service baseline"
        anchors["sales_to_capital"] = _anchor_set(
            "sales_to_capital",
            "ratio",
            _anchor(max(SALES_TO_CAPITAL_MIN, sales_to_capital * BASELINE_LOW_FACTOR), f"{source}; low rule: {BASELINE_LOW_FACTOR}x baseline"),
            _anchor(sales_to_capital, f"{source}; base rule: baseline as returned"),
            _anchor(min(SALES_TO_CAPITAL_MAX, sales_to_capital * BASELINE_HIGH_FACTOR), f"{source}; high rule: {BASELINE_HIGH_FACTOR}x baseline"),
        )

    transparency = valuation.get("assumptionTransparency") or {}
    discount = transparency.get("discountRate") if isinstance(transparency, dict) else {}
    if not isinstance(discount, dict):
        discount = {}
    risk_free_rate = discount.get("riskFreeRate")
    initial_cost = discount.get("initialCostOfCapital")
    if not isinstance(risk_free_rate, (int, float)) or not math.isfinite(float(risk_free_rate)):
        risk_free_rate = None
    if not isinstance(initial_cost, (int, float)) or not math.isfinite(float(initial_cost)):
        initial_cost = _first_finite(financial.get("costOfCapital"), skip_first=False)
    if initial_cost is not None:
        initial_cost = float(initial_cost)
        risk_free = float(risk_free_rate) if risk_free_rate is not None else initial_cost
        spread = max(0.0, initial_cost - risk_free)
        adjustment = spread * 0.2
        source = "service_baseline: initial cost of capital and risk-free rate from the deterministic valuation-service baseline"
        anchors["wacc"] = _anchor_set(
            "wacc",
            "percent",
            _anchor(max(risk_free, initial_cost - adjustment), f"{source}; low rule: 20% lower risk spread"),
            _anchor(initial_cost, f"{source}; base rule: baseline initial cost of capital"),
            _anchor(initial_cost + adjustment, f"{source}; high rule: 20% higher risk spread"),
        )

    return anchors


def driver_field_for_key(key: str) -> str | None:
    """Map a scenario or override key to its anchored driver field, if any."""
    return PROSPECTUS_SCENARIO_KEY_TO_DRIVER_FIELD.get(key) or RECALCULATE_KEY_TO_DRIVER_FIELD.get(key)


def matches_anchor(anchor_set: dict[str, Any], value: Any) -> str | None:
    """Return the anchor label the value matches, or None."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    values = anchor_values(anchor_set)
    for label in ("base", "low", "high"):
        if label in values and math.isclose(float(value), values[label], rel_tol=0.0, abs_tol=0.005):
            return label
    return None
