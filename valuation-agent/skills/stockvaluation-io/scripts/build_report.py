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
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

NO_ADVICE_LINE = (
    "Educational analysis only. This is not financial advice and makes no buy, sell, or hold recommendation."
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


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return lines


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
        return []
    return ["## What The Price Would Need", ""] + _table(["Assumption", "Required value", "Note"], table_rows)


def _key_assumptions_section(data: dict) -> list[str]:
    rows = []
    for item in data.get("key_assumptions") or []:
        if not isinstance(item, dict):
            continue
        driver = _text(item.get("driver"))
        value = item.get("value")
        source = _text(item.get("source"))
        if not driver or value in (None, "") or not source:
            continue
        unit = _text(item.get("unit"))
        rows.append([driver.replace("_", " "), f"{value} {unit}".strip(), source])
    if not rows:
        return []
    return ["## Key Assumptions", ""] + _table(["Driver", "Value", "Source"], rows)


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
        _market_implied_section,
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the StockValuation report from structured run data.")
    parser.add_argument("--input", type=Path, default=None, help="Report data JSON; defaults to stdin.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory for report artifacts.")
    parser.add_argument("--skip-html", action="store_true", help="Emit markdown only.")
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
            renderer.build_html(markdown, title, _text(data.get("company")) or None, _text(data.get("ticker")) or None, generated_at),
            encoding="utf-8",
        )
        outputs["html"] = str(html_path)
        outputs["browser_link"] = renderer._file_uri(html_path)

    print(json.dumps(outputs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
