#!/usr/bin/env python3
"""Assemble the StockValuation.io report from run data plus model prose.

Code owns the structure: section order, data-populated tables, the single
no-advice line, and the compact Audit block. The model only writes the named
narrative prose fields. Sections without underlying data are omitted
entirely — the builder never writes "Unavailable" filler. The prose linter
runs before rendering and the builder refuses to render on error findings.

Input: one JSON file (or stdin) with:
  company, ticker, title?, currency?
  valuation: {point: {value_per_share, label?}} or
             {range: {low, high, unresolved_drivers: [...]}}
  prose: {business_story, growth, profitability, reinvestment, risk, bottom_line}
  market_implied_diagnostics?: {rows: [{assumption, required_value, note?}]}
  key_assumptions?: [{driver, value, unit?, source}]  # source: anchor:<label>|user_input|service|segments:anchor:<label>|segments:user_input
  guided_judgment?: [{question, driver, answer, source?}]
  data_limits?: [string]
  sources?: [{title, url?, date?}]
  audit?: {workflow_state?, evidence_review?, guided_refinement?, source_class?,
           skill_version?, service_version?, mcp_version?, run_id?}
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys
import webbrowser
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

NO_ADVICE_LINE = (
    "Educational analysis only. This is not financial advice."
)

PROSE_SECTIONS = (
    ("business_story", "Business Story"),
    ("growth", "Growth"),
    ("profitability", "Profitability"),
    ("reinvestment", "Reinvestment"),
    ("risk", "Risk"),
)


def _load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _fmt(value, suffix: str = "", decimals: int = 2) -> str:
    number = _number(value)
    if number is None:
        return ""
    formatted = f"{number:,.{decimals}f}"
    return f"{formatted}{suffix}" if suffix else formatted


def _fmt_unit(value, unit: str = "") -> str:
    normalized = _text(unit).lower()
    if normalized in {"percent", "%"}:
        return _fmt(value, "%")
    if normalized in {"multiple", "x", "ratio"}:
        return _fmt(value, "x")
    return _fmt(value)


def _first_present(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return lines


def _valuation_output(data: dict) -> dict:
    for key in ("valuation_output", "valuationOutput", "raw_valuation", "rawValuation", "valuation_json", "valuationJson"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    valuation = data.get("valuation")
    if isinstance(valuation, dict) and any(key in valuation for key in ("companyDTO", "financialDTO", "terminalValueDTO")):
        return valuation
    return {}


def _series(container: dict, key: str) -> list:
    value = container.get(key)
    return value if isinstance(value, list) else []


def _valuation_view(data: dict) -> list[str]:
    valuation = data.get("valuation") or {}
    currency = _text(data.get("currency")) or "USD"
    point = valuation.get("point") if isinstance(valuation, dict) else None
    value_range = valuation.get("range") if isinstance(valuation, dict) else None
    lines: list[str] = []
    if isinstance(point, dict) and isinstance(point.get("value_per_share"), (int, float)):
        label = _text(point.get("label")) or "Estimated value per share"
        lines.append(f"{label}: **{point['value_per_share']:.2f} {currency}**.")
    elif isinstance(value_range, dict):
        low = value_range.get("low")
        high = value_range.get("high")
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            lines.append(
                f"Value range: **{min(low, high):.2f}-{max(low, high):.2f} {currency}** per share."
            )
            drivers = [str(d) for d in value_range.get("unresolved_drivers") or [] if d]
            if drivers:
                lines.append(
                    "The spread comes from unresolved driver(s): "
                    + ", ".join(driver.replace("_", " ") for driver in drivers)
                    + ". A single point estimate appears only when every material driver is pinned."
                )
    return lines


def _market_implied_section(data: dict) -> list[str]:
    diagnostics = data.get("market_implied_diagnostics")
    rows = diagnostics.get("rows") if isinstance(diagnostics, dict) else None
    table_rows = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        assumption = _text(row.get("assumption"))
        required = row.get("required_value")
        if not assumption or required in (None, ""):
            continue
        table_rows.append([assumption, required, _text(row.get("note"))])
    if not table_rows:
        return _service_market_implied_section(data)
    return ["## What The Price Would Need", ""] + _table(["Assumption", "Required value", "Note"], table_rows)


def _service_market_implied_section(data: dict) -> list[str]:
    transparency = _dict(_valuation_output(data).get("assumptionTransparency"))
    diagnostics = _dict(transparency.get("marketImpliedExpectations"))
    rows = []
    for metric in _list(diagnostics.get("metrics")):
        if not isinstance(metric, dict):
            continue
        label = _text(metric.get("label") or metric.get("key"))
        if not label:
            continue
        unit = _text(metric.get("unit"))
        rows.append(
            [
                label,
                _fmt_unit(metric.get("modelValue"), unit),
                _fmt_unit(metric.get("impliedValue"), unit),
                _fmt_unit(metric.get("gap"), unit),
                _text(metric.get("note")),
            ]
        )
    if not rows:
        return []
    return ["## What The Price Would Need", ""] + _table(
        ["Driver", "Model", "Market-implied", "Gap", "Note"],
        rows,
    )


def _service_key_drivers_section(data: dict) -> list[str]:
    if data.get("key_assumptions"):
        return []
    valuation = _valuation_output(data)
    transparency = _dict(valuation.get("assumptionTransparency"))
    operating = _dict(transparency.get("operatingAssumptions"))
    discount = _dict(transparency.get("discountRate"))
    terminal = _dict(valuation.get("terminalValueDTO"))
    rows = []

    def add(label: str, value, unit: str = "", source: str = "", rationale: str = "") -> None:
        formatted = _fmt_unit(value, unit)
        if formatted:
            rows.append([label, formatted, _text(source), _text(rationale)])

    add(
        "Revenue growth years 2-5",
        operating.get("revenueGrowthRateYears2To5"),
        "percent",
        operating.get("revenueGrowthSource"),
        operating.get("revenueGrowthRationale"),
    )
    add(
        "Operating margin next year",
        operating.get("operatingMarginNextYear"),
        "percent",
        operating.get("operatingMarginSource"),
        operating.get("operatingMarginRationale"),
    )
    add(
        "Target operating margin",
        operating.get("targetOperatingMargin"),
        "percent",
        operating.get("operatingMarginSource"),
        operating.get("operatingMarginRationale"),
    )
    add("Margin convergence year", operating.get("convergenceYearMargin"))
    add(
        "Sales-to-capital years 1-5",
        operating.get("salesToCapitalYears1To5"),
        "multiple",
        operating.get("salesToCapitalSource"),
        operating.get("salesToCapitalRationale"),
    )
    add(
        "Sales-to-capital years 6-10",
        operating.get("salesToCapitalYears6To10"),
        "multiple",
        operating.get("salesToCapitalSource"),
        operating.get("salesToCapitalRationale"),
    )
    add(
        "Initial cost of capital",
        discount.get("initialCostOfCapital"),
        "percent",
        discount.get("initialCostOfCapitalSource"),
    )
    add(
        "Terminal cost of capital",
        _first_present(terminal.get("costOfCapital"), discount.get("terminalCostOfCapital")),
        "percent",
        discount.get("equityRiskPremiumSource"),
        discount.get("costOfCapitalFormula"),
    )
    add("Terminal growth", terminal.get("growthRate"), "percent")
    add("Terminal return on capital", terminal.get("returnOnCapital"), "percent")
    if not rows:
        return []
    has_detail = any(row[2] or row[3] for row in rows)
    if has_detail:
        return ["## Model Driver Snapshot", ""] + _table(["Driver", "Value", "Source", "Rationale"], rows)
    return ["## Model Driver Snapshot", ""] + _table(["Driver", "Value"], [row[:2] for row in rows])


def _priced_in_expectations_section(data: dict) -> list[str]:
    transparency = _dict(_valuation_output(data).get("assumptionTransparency"))
    priced_in = _dict(transparency.get("pricedInExpectations"))
    base_case = _dict(priced_in.get("baseCase"))
    frontier = _list(priced_in.get("frontier"))
    lines: list[str] = []
    base_value = _fmt(base_case.get("intrinsicValue"))
    market_price = _fmt(priced_in.get("marketPrice"))
    if base_value and market_price:
        gap = _fmt(base_case.get("gapToMarket"))
        gap_pct = _fmt(base_case.get("gapToMarketPct"), "%")
        detail = f"Base case value is {base_value} versus market price {market_price}."
        if gap and gap_pct:
            detail += f" Gap to market is {gap} ({gap_pct})."
        lines.extend(["## Priced-In Expectations", "", detail, ""])
    rows = []
    for row in frontier:
        if not isinstance(row, dict):
            continue
        margin = _fmt(row.get("operatingMargin"), "%")
        implied_growth = _fmt(row.get("impliedRevenueGrowth"), "%")
        value = _fmt(row.get("intrinsicValue"))
        if not margin or not implied_growth:
            continue
        status = "Solved" if row.get("solved") is True else "Nearest sampled point"
        rows.append([margin, implied_growth, value, status, _text(row.get("note"))])
    if rows:
        if not lines:
            lines.extend(["## Priced-In Expectations", ""])
        lines.extend(_table(["Operating margin", "Implied growth", "Value/share", "Status", "Note"], rows))
    return lines


def _key_assumptions_section(data: dict) -> list[str]:
    rows = []
    has_source_detail = False
    for item in data.get("key_assumptions") or []:
        if not isinstance(item, dict):
            continue
        driver = _text(item.get("driver"))
        value = item.get("value")
        source = _text(item.get("source"))
        if not driver or value in (None, "") or not source:
            continue
        unit = _text(item.get("unit"))
        source_detail = _anchor_explanation_text(item)
        has_source_detail = has_source_detail or bool(source_detail)
        rows.append([driver.replace("_", " "), f"{value} {unit}".strip(), source, source_detail])
    if not rows:
        return []
    if has_source_detail:
        return ["## Key Assumptions", ""] + _table(["Driver", "Value", "Source", "Source detail"], rows)
    return ["## Key Assumptions", ""] + _table(["Driver", "Value", "Source"], [row[:3] for row in rows])


def _projection_walk_section(data: dict) -> list[str]:
    valuation = _valuation_output(data)
    financial = _dict(valuation.get("financialDTO"))
    revenues = _series(financial, "revenues")
    if not revenues:
        return []
    revenue_growth = _series(financial, "revenueGrowthRate")
    margins = _series(financial, "ebitOperatingMargin")
    ebit = _series(financial, "ebitOperatingIncome")
    fcff = _series(financial, "fcff")
    pv_fcff = _series(financial, "pvFcff")
    projection_years = int(_number(valuation.get("projectionYears")) or max(0, len(revenues) - 2))
    max_year = min(projection_years, len(revenues) - 2, 10)
    rows: list[list[str]] = []
    for year in range(0, max_year + 1):
        rows.append(
            [
                "Base" if year == 0 else f"Year {year}",
                _fmt(_first_present(revenues[year] if year < len(revenues) else None)),
                _fmt(revenue_growth[year] if year < len(revenue_growth) else None, "%"),
                _fmt(margins[year] if year < len(margins) else None, "%"),
                _fmt(ebit[year] if year < len(ebit) else None),
                _fmt(fcff[year] if year < len(fcff) else None),
                _fmt(pv_fcff[year] if year < len(pv_fcff) else None),
            ]
        )
    if len(rows) <= 1:
        return []
    return ["## Projection Walk", ""] + _table(
        ["Year", "Revenue", "Growth", "EBIT margin", "EBIT", "FCFF", "PV FCFF"],
        rows,
    )


def _valuation_bridge_section(data: dict) -> list[str]:
    valuation = _valuation_output(data)
    company = _dict(valuation.get("companyDTO"))
    rows = []
    for label, value, suffix in (
        ("PV explicit cash flows", company.get("pvCFOverNext10Years"), ""),
        ("PV terminal value", company.get("pvTerminalValue"), ""),
        ("Operating asset value", company.get("valueOfOperatingAssets"), ""),
        ("Cash", company.get("cash"), ""),
        ("Non-operating assets", company.get("nonOperatingAssets"), ""),
        ("Debt", company.get("debt"), ""),
        ("Minority interests", company.get("minorityInterests"), ""),
        ("Equity value", company.get("valueOfEquity"), ""),
        ("Option value", company.get("valueOfOptions"), ""),
        ("Common equity value", company.get("valueOfEquityInCommonStock"), ""),
        ("Shares", company.get("numberOfShares"), ""),
        ("Estimated value per share", company.get("estimatedValuePerShare"), ""),
        ("Market price", company.get("price"), ""),
        ("Price as percent of value", company.get("priceAsPercentageOfValue"), "%"),
    ):
        formatted = _fmt(value, suffix)
        if formatted:
            rows.append([label, formatted])
    if not rows:
        return []
    return ["## Valuation Bridge", ""] + _table(["Item", "Value"], rows)


def _terminal_value_section(data: dict) -> list[str]:
    valuation = _valuation_output(data)
    terminal = _dict(valuation.get("terminalValueDTO"))
    company = _dict(valuation.get("companyDTO"))
    rows = []
    for label, value, suffix in (
        ("Terminal growth", terminal.get("growthRate"), "%"),
        ("Terminal cost of capital", terminal.get("costOfCapital"), "%"),
        ("Terminal return on capital", terminal.get("returnOnCapital"), "%"),
        ("Terminal reinvestment rate", terminal.get("reinvestmentRate"), "%"),
        ("Terminal cash flow", company.get("terminalCashFlow"), ""),
        ("Terminal value", company.get("terminalValue"), ""),
        ("PV terminal value", company.get("pvTerminalValue"), ""),
    ):
        formatted = _fmt(value, suffix)
        if formatted:
            rows.append([label, formatted])
    pv_terminal = _number(company.get("pvTerminalValue"))
    operating_assets = _number(company.get("valueOfOperatingAssets"))
    if pv_terminal is not None and operating_assets and operating_assets != 0:
        rows.append(["PV terminal share of operating assets", _fmt(pv_terminal / operating_assets * 100.0, "%")])
    if not rows:
        return []
    return ["## Terminal Value", ""] + _table(["Driver", "Value"], rows)


def _scenario_section(data: dict) -> list[str]:
    book = _dict(data.get("scenario_book") or data.get("scenarioBook"))
    scenarios = _list(book.get("scenarios"))
    if not scenarios:
        scenarios = _list(_dict(book.get("book")).get("scenarios"))
    if not scenarios:
        scenarios = _list(data.get("scenarios"))
    rows = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        label = _text(scenario.get("label") or scenario.get("scenario_id") or scenario.get("scenarioId"))
        scenario_type = _text(scenario.get("type"))
        status = _text(scenario.get("status"))
        source = _text(scenario.get("source"))
        value = _scenario_value_text(scenario)
        if label and (value or status or source):
            rows.append([label, scenario_type, value, status, source])
    if not rows:
        return []
    return ["## Scenario Cases", ""] + _table(["Case", "Type", "Value/share", "Status", "Source"], rows)


def _scenario_value_text(scenario: dict) -> str:
    for key in ("value_per_share", "valuePerShare", "estimatedValuePerShare", "estimated_value_per_share"):
        formatted = _fmt(scenario.get(key))
        if formatted:
            return formatted
    response = _dict(scenario.get("service_response") or scenario.get("serviceResponse"))
    company = _dict(response.get("companyDTO"))
    formatted = _fmt(company.get("estimatedValuePerShare"))
    return formatted


def _anchor_explanation_text(item: dict) -> str:
    explanation = item.get("anchor_explanation") or item.get("anchorExplanation")
    if not isinstance(explanation, dict):
        return _text(item.get("source_detail") or item.get("sourceDetail"))
    parts: list[str] = []
    summary = _text(explanation.get("summary"))
    if summary:
        parts.append(summary)
    weighted = explanation.get("weighted_anchors") or explanation.get("weightedAnchors")
    if isinstance(weighted, dict):
        anchors = []
        for label in ("low", "base", "high"):
            value = weighted.get(label)
            if value not in (None, ""):
                anchors.append(f"{label} {value}")
        if anchors:
            parts.append("Weighted anchors: " + ", ".join(anchors))
    for row in explanation.get("segment_rows") or explanation.get("segmentRows") or []:
        if not isinstance(row, dict):
            continue
        segment = _text(row.get("segment"))
        industry = _text(row.get("industry_group") or row.get("industryGroup"))
        if not segment or not industry:
            continue
        weight_text = _anchor_weight_text(row)
        values = [
            str(row.get(label))
            for label in ("low", "base", "high")
            if row.get(label) not in (None, "")
        ]
        value_text = f", low/base/high {'/'.join(values)}" if values else ""
        parts.append(f"{segment} -> {industry}{weight_text}{value_text}")
    warnings = [_text(item) for item in explanation.get("warnings") or [] if _text(item)]
    if warnings:
        parts.append("Warnings: " + "; ".join(warnings))
    return "; ".join(parts)


def _anchor_weight_text(row: dict) -> str:
    filing = row.get("filing_weight_pct")
    effective = row.get("effective_anchor_weight_pct")
    if filing in (None, ""):
        filing = row.get("revenue_weight_pct")
    try:
        filing_number = float(filing)
    except (TypeError, ValueError):
        filing_number = None
    try:
        effective_number = float(effective)
    except (TypeError, ValueError):
        effective_number = None
    if filing_number is None and effective_number is None:
        return ""
    if effective_number is None or filing_number == effective_number:
        return f", filing weight {filing_number:g}%" if filing_number is not None else ""
    if filing_number is None:
        return f", effective anchor weight {effective_number:g}%"
    return f", filing weight {filing_number:g}%, effective anchor weight {effective_number:g}%"


def _guided_judgment_section(data: dict) -> list[str]:
    rows = []
    for item in data.get("guided_judgment") or []:
        if not isinstance(item, dict):
            continue
        question = _text(item.get("question"))
        answer = _text(str(item.get("answer") or ""))
        if not question or not answer:
            continue
        rows.append([question, _text(item.get("driver")).replace("_", " "), answer, _text(item.get("source"))])
    if not rows:
        return []
    return ["## Guided Judgment", ""] + _table(["Question", "Driver", "Answer", "Source"], rows)


def _data_limits_section(data: dict) -> list[str]:
    limits = [_text(item) for item in data.get("data_limits") or [] if _text(item)]
    if not limits:
        return []
    return ["## Data Limits", ""] + [f"- {item}" for item in limits]


def _sources_section(data: dict) -> list[str]:
    entries = []
    for item in data.get("sources") or []:
        if not isinstance(item, dict):
            continue
        title = _text(item.get("title"))
        if not title:
            continue
        parts = [title]
        if _text(item.get("url")):
            parts.append(f"<{_text(item.get('url'))}>")
        if _text(item.get("date")):
            parts.append(f"({_text(item.get('date'))})")
        entries.append("- " + " ".join(parts))
    if not entries:
        return []
    return ["## Sources", ""] + entries


def _audit_section(data: dict) -> list[str]:
    audit = data.get("audit")
    if not isinstance(audit, dict):
        return []
    rows: list[list[str]] = []
    workflow_state = audit.get("workflow_state")
    if isinstance(workflow_state, dict):
        gates = workflow_state.get("gates")
        if isinstance(gates, dict):
            for gate, entry in sorted(gates.items()):
                if not isinstance(entry, dict):
                    continue
                status = _text(entry.get("status"))
                detail = _text(entry.get("outcome"))
                if _text(entry.get("reason")):
                    detail = f"{detail} ({_text(entry.get('reason'))})".strip()
                rows.append([f"Gate: {gate.replace('_', ' ')}", " ".join(part for part in [status, detail] if part)])
        if _text(workflow_state.get("run_id")):
            rows.append(["Run", _text(workflow_state.get("run_id"))])
    existing_labels = {row[0] for row in rows}
    for key, label in (
        ("evidence_review", "Evidence review"),
        ("guided_refinement", "Guided refinement"),
        ("source_class", "Source class"),
        ("skill_version", "Skill version"),
        ("service_version", "Service version"),
        ("mcp_version", "MCP version"),
        ("run_id", "Run"),
    ):
        value = _text(str(audit.get(key) or ""))
        if value and label not in existing_labels:
            rows.append([label, value])
            existing_labels.add(label)
    if not rows:
        return []
    return ["## Audit", ""] + _table(["Item", "Status"], rows)


def build_report_markdown(data: dict) -> str:
    company = _text(data.get("company")) or _text(data.get("ticker")) or "Valuation"
    title = _text(data.get("title")) or f"{company} Valuation Report"
    sections: list[list[str]] = []

    valuation_view = _valuation_view(data)
    if valuation_view:
        sections.append(["## Valuation View", ""] + valuation_view)

    prose = data.get("prose") if isinstance(data.get("prose"), dict) else {}
    for key, heading in PROSE_SECTIONS:
        body = _text(prose.get(key))
        if body:
            sections.append([f"## {heading}", "", body])

    for builder in (
        _service_key_drivers_section,
        _market_implied_section,
        _priced_in_expectations_section,
        _projection_walk_section,
        _valuation_bridge_section,
        _terminal_value_section,
        _scenario_section,
        _key_assumptions_section,
        _guided_judgment_section,
    ):
        section = builder(data)
        if section:
            sections.append(section)

    section = _data_limits_section(data)
    if section:
        sections.append(section)

    bottom_line = _text(prose.get("bottom_line"))
    if bottom_line:
        sections.append(["## Bottom Line", "", bottom_line])

    for builder in (_sources_section, _audit_section):
        section = builder(data)
        if section:
            sections.append(section)

    lines: list[str] = [f"# {title}", "", NO_ADVICE_LINE, ""]
    for section in sections:
        lines.extend(section)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _browser_open_default() -> bool:
    value = os.environ.get("STOCKVALUATION_OPEN_REPORT", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _open_report_in_browser(html_path: Path, renderer) -> bool:
    try:
        return bool(webbrowser.open_new_tab(renderer._file_uri(html_path)))
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the StockValuation report from structured run data.")
    parser.add_argument("--input", type=Path, default=None, help="Report data JSON; defaults to stdin.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory for report artifacts.")
    parser.add_argument("--skip-html", action="store_true", help="Emit markdown only.")
    parser.add_argument(
        "--open-browser",
        dest="open_browser",
        action="store_true",
        default=None,
        help="Open the generated HTML report in the default browser.",
    )
    parser.add_argument(
        "--no-open",
        dest="open_browser",
        action="store_false",
        help="Do not open the generated HTML report.",
    )
    args = parser.parse_args()

    raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
    data = json.loads(raw)
    markdown = build_report_markdown(data)

    prose_lint = _load_module("prose_lint")
    findings = prose_lint.lint_markdown(markdown)
    errors = prose_lint.error_findings(findings)
    if errors:
        print(json.dumps({"ok": False, "reason": "prose_lint_errors", "findings": errors}, indent=2))
        return 1

    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = out_dir / "report.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    outputs = {"ok": True, "markdown": str(markdown_path), "findings": findings}

    if not args.skip_html:
        renderer = _load_module("render_report_html")
        title = _text(data.get("title")) or f"{_text(data.get('company')) or _text(data.get('ticker')) or 'Valuation'} Valuation Report"
        html_path = out_dir / "index.html"
        generated_at = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
        html_path.write_text(
            renderer.build_html(
                markdown,
                title,
                _text(data.get("company")) or None,
                _text(data.get("ticker")) or None,
                generated_at,
                report_data=data,
            ),
            encoding="utf-8",
        )
        outputs["html"] = str(html_path)
        outputs["browser_link"] = renderer._file_uri(html_path)
        should_open = args.open_browser if args.open_browser is not None else _browser_open_default()
        outputs["browser_opened"] = _open_report_in_browser(html_path, renderer) if should_open else False

    print(json.dumps(outputs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
