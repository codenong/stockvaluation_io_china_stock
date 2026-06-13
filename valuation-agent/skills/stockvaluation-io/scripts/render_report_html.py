#!/usr/bin/env python3
"""Render a StockValuation.io Markdown report as a local HTML artifact."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import quote


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "valuation-report"


def _default_output_dir() -> Path:
    configured = os.environ.get("STOCKVALUATION_REPORT_DIR")
    if configured:
        return Path(configured).expanduser()
    cwd = Path.cwd()
    if (cwd / ".git").exists() or (cwd / "valuation-agent" / "skills" / "stockvaluation-io").exists():
        return cwd / "tmp" / "valuation-reports"
    return Path(tempfile.gettempdir()) / "stockvaluation-io-reports"


def _file_uri(path: Path) -> str:
    return "file://" + quote(str(path.resolve()))


def _inline(markdown: str) -> str:
    text = html.escape(markdown, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)

    def link(match: re.Match[str]) -> str:
        label = match.group(1)
        url = html.escape(match.group(2), quote=True)
        return f'<a href="{url}">{label}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def _heading_id(text: str, used: set[str]) -> str:
    base = _slug(re.sub(r"<[^>]+>", "", text))
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def render_markdown(markdown: str) -> tuple[str, list[tuple[int, str, str]]]:
    lines = markdown.splitlines()
    output: list[str] = []
    headings: list[tuple[int, str, str]] = []
    used_heading_ids: set[str] = set()
    paragraph: list[str] = []
    list_type: str | None = None
    in_code = False
    code_lines: list[str] = []
    i = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            output.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            output.append(f"</{list_type}>")
            list_type = None

    while i < len(lines):
        raw = lines[i].rstrip()

        if raw.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                output.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(raw)
            i += 1
            continue

        if not raw.strip():
            flush_paragraph()
            close_list()
            i += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", raw)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            title = _inline(heading.group(2).strip())
            heading_id = _heading_id(title, used_heading_ids)
            headings.append((level, heading.group(2).strip(), heading_id))
            output.append(f'<h{level} id="{heading_id}">{title}</h{level}>')
            i += 1
            continue

        if raw.startswith("|") and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            flush_paragraph()
            close_list()
            headers = _split_table_row(raw)
            rows: list[list[str]] = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_split_table_row(lines[i]))
                i += 1
            output.append('<div class="table-wrap"><table>')
            output.append("<thead><tr>" + "".join(f"<th>{_inline(cell)}</th>" for cell in headers) + "</tr></thead>")
            output.append("<tbody>")
            for row in rows:
                cells = row + [""] * max(0, len(headers) - len(row))
                output.append("<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in cells[: len(headers)]) + "</tr>")
            output.append("</tbody></table></div>")
            continue

        bullet = re.match(r"^\s*[-*]\s+(.+)$", raw)
        numbered = re.match(r"^\s*\d+\.\s+(.+)$", raw)
        if bullet or numbered:
            flush_paragraph()
            wanted = "ul" if bullet else "ol"
            if list_type != wanted:
                close_list()
                list_type = wanted
                output.append(f"<{list_type}>")
            item = bullet.group(1) if bullet else numbered.group(1)
            output.append(f"<li>{_inline(item)}</li>")
            i += 1
            continue

        close_list()
        paragraph.append(raw.strip())
        i += 1

    flush_paragraph()
    close_list()
    if in_code:
        output.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    return "\n".join(output), headings


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


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


def _fmt_compact(value, suffix: str = "") -> str:
    number = _number(value)
    if number is None:
        return ""
    sign = "-" if number < 0 else ""
    absolute = abs(number)
    for threshold, label in ((1_000_000_000_000, "T"), (1_000_000_000, "B"), (1_000_000, "M")):
        if absolute >= threshold:
            return f"{sign}{absolute / threshold:,.2f}{label}{suffix}"
    return f"{number:,.2f}{suffix}"


def _valuation_output(data: dict) -> dict:
    for key in ("valuation_output", "valuationOutput", "raw_valuation", "rawValuation", "valuation_json", "valuationJson"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    valuation = data.get("valuation")
    if isinstance(valuation, dict) and any(key in valuation for key in ("companyDTO", "financialDTO", "terminalValueDTO")):
        return valuation
    return {}


def _series(container: dict, key: str) -> list[float]:
    values = []
    for value in _list(container.get(key)):
        number = _number(value)
        if number is not None:
            values.append(number)
    return values


def _plain(markdown: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", markdown)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    return " ".join(text.split())


def _section_text(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    start = None
    target = f"## {heading}".lower()
    for index, line in enumerate(lines):
        if line.strip().lower() == target:
            start = index + 1
            break
    if start is None:
        return ""
    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        section.append(line)
    return _plain("\n".join(section))


def _shorten(text: str, limit: int = 260) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "..."


def _metric(label: str, value: str, note: str = "", tone: str = "") -> str:
    if not value:
        return ""
    note_html = f'<span class="metric-note">{html.escape(note)}</span>' if note else ""
    tone_class = f" {tone}" if tone else ""
    return (
        f'<div class="summary-metric{tone_class}">'
        f'<span class="metric-label">{html.escape(label)}</span>'
        f'<strong>{html.escape(value)}</strong>'
        f"{note_html}</div>"
    )


def _valuation_text(data: dict) -> str:
    currency = _text(data.get("currency")) or _text(_valuation_output(data).get("currency")) or "USD"
    valuation = _dict(data.get("valuation"))
    point = _dict(valuation.get("point"))
    value_range = _dict(valuation.get("range"))
    point_value = _number(point.get("value_per_share"))
    if point_value is not None:
        return f"{point_value:,.2f} {currency}"
    low = _number(value_range.get("low"))
    high = _number(value_range.get("high"))
    if low is not None and high is not None:
        return f"{min(low, high):,.2f}-{max(low, high):,.2f} {currency}"
    company = _dict(_valuation_output(data).get("companyDTO"))
    fallback = _number(company.get("estimatedValuePerShare"))
    return f"{fallback:,.2f} {currency}" if fallback is not None else ""


def _status_chips(data: dict) -> str:
    audit = _dict(data.get("audit"))
    workflow = _dict(audit.get("workflow_state"))
    gates = _dict(workflow.get("gates"))
    chips: list[str] = []
    for gate_key, label in (("evidence_review", "Evidence"), ("guided_refinement", "Guided")):
        entry = _dict(gates.get(gate_key))
        status = _text(entry.get("outcome")) or _text(entry.get("status")) or _text(audit.get(gate_key))
        if status:
            chips.append(f'<span class="status-chip">{html.escape(label)}: {html.escape(status.replace("_", " "))}</span>')
    source_class = _text(audit.get("source_class"))
    if source_class:
        chips.append(f'<span class="status-chip source">{html.escape(source_class.replace("_", " "))}</span>')
    return "\n".join(chips)


def _report_summary_html(markdown: str, data: dict, company: str | None, ticker: str | None, generated_at: str) -> str:
    valuation = _valuation_output(data)
    company_dto = _dict(valuation.get("companyDTO"))
    priced_in = _dict(_dict(_dict(valuation.get("assumptionTransparency")).get("pricedInExpectations")))
    base_case = _dict(priced_in.get("baseCase"))
    company_name = _text(data.get("company")) or _text(company) or _text(valuation.get("companyName")) or "Valuation"
    ticker_text = _text(data.get("ticker")) or _text(ticker)
    report_label = "StockValuation.io report" + (f" / {ticker_text}" if ticker_text else "")
    market_price = _number(company_dto.get("price"))
    if market_price is None:
        market_price = _number(priced_in.get("marketPrice"))
    gap_pct = _number(company_dto.get("priceAsPercentageOfValue"))
    if gap_pct is None:
        gap_pct = _number(base_case.get("gapToMarketPct"))
    value_per_share = _valuation_text(data)
    bottom_line = _section_text(markdown, "Bottom Line") or _section_text(markdown, "Business Story")
    gap_note = "market versus model"
    gap_text = f"{gap_pct:+,.2f}%" if gap_pct is not None else ""
    metrics = "\n".join(
        item
        for item in (
            _metric("Value view", value_per_share, "per share or unresolved range", "primary"),
            _metric("Market price", _fmt(market_price), "latest returned price"),
            _metric("Price gap", gap_text, gap_note, "negative" if gap_pct and gap_pct > 0 else "positive"),
            _metric("Equity value", _fmt_compact(company_dto.get("valueOfEquity")), "model output"),
        )
        if item
    )
    chips = _status_chips(data)
    thesis = _shorten(bottom_line, 330) if bottom_line else "The report connects business story, assumptions, valuation math, and data limits in one local artifact."
    return f"""
<section class="report-brief" aria-label="Report summary">
  <div class="brief-copy">
    <p class="eyebrow">{html.escape(report_label)}</p>
    <h2>{html.escape(company_name)}</h2>
    <p class="brief-thesis">{html.escape(thesis)}</p>
    <div class="status-row">{chips}</div>
  </div>
  <div class="summary-grid">{metrics}</div>
  <p class="generated-line">Generated {html.escape(generated_at)}. Educational analysis only.</p>
</section>
"""


def _market_expectations_html(data: dict) -> str:
    valuation = _valuation_output(data)
    transparency = _dict(valuation.get("assumptionTransparency"))
    priced_in = _dict(transparency.get("pricedInExpectations"))
    base_case = _dict(priced_in.get("baseCase"))
    frontier = _list(priced_in.get("frontier"))
    if not priced_in and not data.get("market_implied_diagnostics"):
        return ""
    model_value = _fmt(base_case.get("intrinsicValue") or priced_in.get("modelIntrinsicValue"))
    market_price = _fmt(priced_in.get("marketPrice"))
    gap = _fmt(base_case.get("gapToMarketPct"), "%")
    solved = [row for row in frontier if isinstance(row, dict) and row.get("solved") is True]
    frontier_rows = []
    for row in solved[:3]:
        margin = _fmt(row.get("operatingMargin"), "%")
        growth = _fmt(row.get("impliedRevenueGrowth"), "%")
        if margin and growth:
            frontier_rows.append(f"<li><strong>{html.escape(margin)}</strong> margin needs about <strong>{html.escape(growth)}</strong> growth.</li>")
    frontier_html = "<ul>" + "".join(frontier_rows) + "</ul>" if frontier_rows else ""
    diagnostics = _dict(data.get("market_implied_diagnostics")).get("rows")
    diag_rows = []
    for row in diagnostics or []:
        if isinstance(row, dict) and _text(row.get("assumption")) and row.get("required_value") not in (None, ""):
            diag_rows.append(
                f"<li><strong>{html.escape(_text(row.get('assumption')))}</strong>: "
                f"{html.escape(str(row.get('required_value')))}</li>"
            )
    diag_html = "<ul>" + "".join(diag_rows[:3]) + "</ul>" if diag_rows else ""
    details = frontier_html or diag_html or "<p>Returned diagnostics are shown in the full report below.</p>"
    return f"""
<section class="market-panel">
  <div>
    <p class="eyebrow">Market expectations</p>
    <h3>What the current price is asking the model to believe</h3>
    <p>These diagnostics are report-only. They explain the price hurdle and do not change the main valuation case.</p>
  </div>
  <dl class="market-facts">
    <div><dt>Model value</dt><dd>{html.escape(model_value or "See report")}</dd></div>
    <div><dt>Market price</dt><dd>{html.escape(market_price or "See report")}</dd></div>
    <div><dt>Base gap</dt><dd>{html.escape(gap or "See report")}</dd></div>
  </dl>
  <div class="market-detail">{details}</div>
</section>
"""


def _driver_cards_html(markdown: str, data: dict) -> str:
    prose = _dict(data.get("prose"))
    cards = []
    for key, title, label in (
        ("growth", "Growth", "Revenue path"),
        ("profitability", "Profitability", "Margin path"),
        ("reinvestment", "Reinvestment", "Capital intensity"),
        ("risk", "Risk", "Discount and uncertainty"),
    ):
        text = _text(prose.get(key)) or _section_text(markdown, title)
        if text:
            cards.append(
                f'<article class="driver-card"><span>{html.escape(label)}</span>'
                f'<h3>{html.escape(title)}</h3><p>{html.escape(_shorten(text, 230))}</p></article>'
            )
    if not cards:
        return ""
    return '<section class="driver-grid" aria-label="Valuation drivers">' + "\n".join(cards) + "</section>"


def _svg_line_chart(title: str, values: list[float], color: str, suffix: str = "") -> str:
    if len(values) < 2:
        return ""
    values = values[:10]
    width = 560
    height = 180
    pad = 28
    low = min(values)
    high = max(values)
    spread = high - low or 1.0
    step = (width - pad * 2) / (len(values) - 1)
    points = []
    for index, value in enumerate(values):
        x = pad + index * step
        y = height - pad - ((value - low) / spread * (height - pad * 2))
        points.append(f"{x:.1f},{y:.1f}")
    low_label = _fmt_compact(low, suffix)
    high_label = _fmt_compact(high, suffix)
    return f"""
<figure class="mini-chart">
  <figcaption>{html.escape(title)}</figcaption>
  <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
    <line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" />
    <polyline points="{' '.join(points)}" style="stroke:{color}" />
    <circle cx="{points[-1].split(',')[0]}" cy="{points[-1].split(',')[1]}" r="4" style="fill:{color}" />
    <text x="{pad}" y="18">{html.escape(low_label)}</text>
    <text x="{width - pad}" y="18" text-anchor="end">{html.escape(high_label)}</text>
  </svg>
</figure>
"""


def _bridge_html(data: dict) -> str:
    company = _dict(_valuation_output(data).get("companyDTO"))
    rows = [
        ("PV explicit cash flows", _number(company.get("pvCFOverNext10Years")), "positive"),
        ("PV terminal value", _number(company.get("pvTerminalValue")), "positive"),
        ("Cash", _number(company.get("cash")), "positive"),
        ("Debt", _number(company.get("debt")), "negative"),
    ]
    rows = [(label, value, tone) for label, value, tone in rows if value is not None]
    if len(rows) < 2:
        return ""
    max_value = max(abs(value) for _, value, _ in rows) or 1.0
    rendered = []
    for label, value, tone in rows:
        width = max(3, min(100, abs(value) / max_value * 100))
        rendered.append(
            f'<div class="bridge-row"><span>{html.escape(label)}</span>'
            f'<div class="bridge-track"><i class="{tone}" style="width:{width:.1f}%"></i></div>'
            f'<strong>{html.escape(_fmt_compact(value))}</strong></div>'
        )
    return '<figure class="bridge-chart"><figcaption>Valuation bridge</figcaption>' + "\n".join(rendered) + "</figure>"


def _visuals_html(data: dict) -> str:
    valuation = _valuation_output(data)
    financial = _dict(valuation.get("financialDTO"))
    charts = [
        _svg_line_chart("Revenue path", _series(financial, "revenues"), "#0f766e"),
        _svg_line_chart("Operating margin", _series(financial, "ebitOperatingMargin"), "#a16207", "%"),
        _svg_line_chart("Free cash flow", _series(financial, "fcff"), "#2563eb"),
        _bridge_html(data),
    ]
    charts = [chart for chart in charts if chart]
    if not charts:
        return ""
    return '<section class="visual-grid" aria-label="Report visuals">' + "\n".join(charts) + "</section>"


def build_html(
    markdown: str,
    title: str,
    company: str | None,
    ticker: str | None,
    generated_at: str,
    report_data: dict | None = None,
) -> str:
    body, headings = render_markdown(markdown)
    data = report_data or {}
    toc_items = [
        f'<a class="toc-link level-{level}" href="#{heading_id}">{html.escape(text)}</a>'
        for level, text, heading_id in headings
        if level <= 2
    ]
    identity = " / ".join(part for part in [company, ticker] if part)
    subtitle = identity or "Educational valuation report"
    header_title = company or title
    header_subtitle = f"Valuation report for {subtitle}." if identity else "Educational valuation report."
    toc = "\n".join(toc_items) if toc_items else '<span class="muted">No sections found</span>'
    dashboard = "\n".join(
        part
        for part in (
            _report_summary_html(markdown, data, company, ticker, generated_at),
            _driver_cards_html(markdown, data),
            _visuals_html(data),
            _market_expectations_html(data),
        )
        if part
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #edf0ee;
      --paper: #fffefa;
      --ink: #171a17;
      --muted: #68716c;
      --line: #d9ded9;
      --line-strong: #aeb9b2;
      --accent: #0c6b5d;
      --accent-2: #9a6a11;
      --accent-3: #245f8f;
      --header: #111412;
      --soft: #edf5f2;
      --warn-soft: #fbf4e4;
      --blue-soft: #eaf2f8;
      --shadow: none;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font: 15px/1.58 "Avenir Next", Avenir, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      max-width: 1360px;
      margin: 0 auto;
      color: var(--header);
      padding: 34px min(5vw, 56px) 22px;
      border-bottom: 1px solid var(--line-strong);
    }}
    .kicker {{
      color: var(--accent);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin: 0 0 8px;
      font-weight: 800;
    }}
    h1 {{
      font-family: Charter, "Iowan Old Style", Georgia, serif;
      font-size: clamp(34px, 4vw, 58px);
      font-weight: 650;
      line-height: 1;
      margin: 0 0 12px;
      letter-spacing: 0;
      overflow-wrap: break-word;
      text-wrap: balance;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      max-width: 860px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(170px, 230px) minmax(0, 1fr);
      gap: 30px;
      max-width: 1360px;
      margin: 0 auto;
      padding: 24px min(5vw, 52px) 56px;
      align-items: start;
    }}
    aside {{
      position: sticky;
      top: 16px;
      background: transparent;
      border-left: 2px solid var(--line-strong);
      padding: 6px 0 6px 14px;
    }}
    aside h2 {{
      font-size: 11px;
      margin: 0 0 10px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .toc-link {{
      display: block;
      color: #4e5752;
      text-decoration: none;
      padding: 6px 0;
      border-top: 1px solid rgba(174, 185, 178, 0.45);
      font-size: 13px;
    }}
    .toc-link:hover {{ color: var(--accent); }}
    main {{
      min-width: 0;
    }}
    .report-brief,
    .market-panel,
    .visual-grid,
    .report-body {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .report-brief {{
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
      gap: 28px;
      padding: clamp(24px, 4vw, 42px);
      border-top: 6px solid var(--header);
    }}
    .brief-copy h2 {{
      margin: 0 0 12px;
      font-family: Charter, "Iowan Old Style", Georgia, serif;
      font-size: clamp(30px, 3.2vw, 46px);
      font-weight: 650;
      line-height: 1;
      overflow-wrap: break-word;
      text-wrap: balance;
    }}
    .brief-thesis {{
      max-width: 68ch;
      color: var(--muted);
      font-size: 16.5px;
      margin: 0;
    }}
    .generated-line {{
      grid-column: 1 / -1;
      color: var(--muted);
      font-size: 13px;
      margin: 0;
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }}
    .status-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 18px;
    }}
    .status-chip {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      color: var(--muted);
      background: #f8f9f6;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .status-chip.source {{ background: var(--blue-soft); color: #244e78; }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0;
      align-content: start;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .summary-metric {{
      min-width: 0;
      border-right: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      padding: 14px 15px;
      background: #fffefa;
    }}
    .summary-metric:nth-child(2n) {{ border-right: 0; }}
    .summary-metric:nth-last-child(-n + 2) {{ border-bottom: 0; }}
    .summary-metric.primary {{
      background: var(--soft);
      border-color: var(--line);
    }}
    .summary-metric.negative {{ background: var(--warn-soft); border-color: #edd2a5; }}
    .summary-metric.positive {{ background: #edf8ef; border-color: #c8e5ce; }}
    .metric-label,
    .eyebrow,
    .fact-label {{
      color: var(--muted);
      display: block;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .summary-metric strong {{
      display: block;
      margin-top: 5px;
      font-size: clamp(21px, 2.2vw, 32px);
      line-height: 1;
      overflow-wrap: anywhere;
    }}
    .metric-note {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-top: 7px;
    }}
    .market-panel {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 0.62fr);
      gap: 20px;
      margin-top: 18px;
      padding: 20px 22px;
      background: #f8f7f2;
      border-color: #e2ddcf;
    }}
    .market-panel h3 {{
      margin: 4px 0 8px;
      font-family: Charter, "Iowan Old Style", Georgia, serif;
      font-size: 24px;
      font-weight: 650;
      line-height: 1.12;
    }}
    .market-panel p {{ margin: 0; color: var(--muted); }}
    .market-facts {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 0;
      margin: 0;
      border: 1px solid #e2ddcf;
      border-radius: 8px;
      overflow: hidden;
    }}
    .market-facts div {{
      border: 0;
      border-bottom: 1px solid #e2ddcf;
      border-radius: 0;
      padding: 11px 12px;
      background: #fffefa;
    }}
    .market-facts div:last-child {{ border-bottom: 0; }}
    .market-facts dt,
    .market-facts dd {{ margin: 0; }}
    .market-facts dt {{ color: var(--muted); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; }}
    .market-facts dd {{ margin-top: 5px; font-size: 18px; font-weight: 800; }}
    .market-detail {{
      grid-column: 1 / -1;
      border-top: 1px solid #e2ddcf;
      padding-top: 14px;
    }}
    .market-detail ul {{ margin-bottom: 0; columns: 2; column-gap: 24px; }}
    .driver-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 0;
      margin: 18px 0 0;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .driver-card {{
      background: var(--paper);
      border: 0;
      border-right: 1px solid var(--line);
      border-radius: 0;
      padding: 17px;
      min-width: 0;
    }}
    .driver-card:last-child {{ border-right: 0; }}
    .driver-card span {{
      color: var(--accent);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .driver-card h3 {{
      margin: 5px 0 8px;
      font-family: Charter, "Iowan Old Style", Georgia, serif;
      font-size: 21px;
      font-weight: 650;
    }}
    .driver-card p {{ margin: 0; color: var(--muted); font-size: 14px; }}
    .visual-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      padding: 0;
      margin: 18px 0 0;
      background: transparent;
      border: 0;
    }}
    .mini-chart,
    .bridge-chart {{
      margin: 0;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
      padding: 14px;
    }}
    .mini-chart figcaption,
    .bridge-chart figcaption {{
      color: var(--header);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
      text-transform: uppercase;
    }}
    .mini-chart svg {{ width: 100%; height: auto; display: block; }}
    .mini-chart line {{ stroke: #cfd8d4; stroke-width: 1; }}
    .mini-chart polyline {{ fill: none; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }}
    .mini-chart text {{ fill: var(--muted); font-size: 12px; font-weight: 700; }}
    .bridge-row {{
      display: grid;
      grid-template-columns: minmax(130px, 0.9fr) minmax(130px, 1.2fr) minmax(70px, 0.4fr);
      gap: 10px;
      align-items: center;
      margin: 9px 0;
      font-size: 13px;
    }}
    .bridge-track {{
      height: 10px;
      background: #e6ece9;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bridge-track i {{ display: block; height: 100%; border-radius: inherit; }}
    .bridge-track i.positive {{ background: var(--accent); }}
    .bridge-track i.negative {{ background: #b94747; }}
    .bridge-row strong {{ text-align: right; }}
    .report-body {{
      margin-top: 18px;
      padding: clamp(20px, 4vw, 42px);
    }}
    .report-body h1 {{
      color: var(--header);
      font-family: Charter, "Iowan Old Style", Georgia, serif;
      font-size: 36px;
      font-weight: 650;
      margin-top: 0;
    }}
    .report-body h2 {{
      color: var(--header);
      font-family: Charter, "Iowan Old Style", Georgia, serif;
      font-size: 27px;
      font-weight: 650;
      margin: 34px 0 12px;
      padding-top: 22px;
      border-top: 1px solid var(--line);
    }}
    .report-body h3 {{ color: var(--accent); font-size: 18px; margin-top: 26px; }}
    .report-body h4 {{ color: var(--accent-2); font-size: 16px; margin-top: 22px; }}
    p {{ margin: 0 0 14px; }}
    ul, ol {{ padding-left: 24px; margin: 0 0 16px; }}
    li {{ margin: 5px 0; }}
    code {{
      background: #eef2f4;
      border: 1px solid #dde5e9;
      border-radius: 4px;
      padding: 1px 4px;
      font-size: 0.92em;
    }}
    pre {{
      overflow: auto;
      background: #111827;
      color: #f8fafc;
      border-radius: 8px;
      padding: 16px;
    }}
    pre code {{ background: transparent; border: 0; color: inherit; padding: 0; }}
    .table-wrap {{ overflow-x: auto; margin: 16px 0 22px; border: 1px solid var(--line); border-radius: 8px; }}
    table {{ border-collapse: collapse; width: 100%; min-width: 680px; background: #fff; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e7ebf0; vertical-align: top; text-align: left; }}
    th {{ background: #eef4f1; color: #123936; font-weight: 700; }}
    tr:last-child td {{ border-bottom: 0; }}
    a {{ color: var(--accent); }}
    .muted {{ color: var(--muted); }}
    footer {{
      color: var(--muted);
      font-size: 13px;
      padding: 0 min(5vw, 52px) 30px;
    }}
    @media (max-width: 860px) {{
      .layout {{ grid-template-columns: 1fr; padding: 16px 14px 48px; }}
      header {{ padding: 24px 20px 20px; }}
      h1 {{ font-size: 24px; line-height: 1.08; }}
      aside {{ display: none; }}
      .brief-copy h2 {{ font-size: 24px; line-height: 1.08; }}
      .subtitle,
      .brief-thesis {{ font-size: 14.5px; }}
      header h1,
      .subtitle,
      .brief-copy h2,
      .brief-thesis {{
        max-width: 320px;
      }}
      .report-brief {{ padding: 20px 16px; }}
      .status-row {{ display: grid; grid-template-columns: 1fr; }}
      .status-chip {{ justify-self: start; }}
      .report-brief,
      .market-panel,
      .visual-grid {{ grid-template-columns: 1fr; }}
      .summary-grid,
      .market-facts,
      .driver-grid {{ grid-template-columns: 1fr; }}
      .driver-card {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .driver-card:last-child {{ border-bottom: 0; }}
      .market-detail ul {{ columns: 1; }}
      .report-body {{ padding: 18px; }}
      table {{ min-width: 560px; }}
      .bridge-row {{ grid-template-columns: 1fr; }}
      .bridge-row strong {{ text-align: left; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      header, aside, footer {{ display: none; }}
      .layout {{ display: block; padding: 0; }}
      .report-brief,
      .market-panel,
      .visual-grid,
      .report-body {{ box-shadow: none; border: 0; padding: 0; }}
      a {{ color: inherit; text-decoration: none; }}
    }}
  </style>
</head>
<body>
  <header>
    <p class="kicker">StockValuation.io</p>
    <h1>{html.escape(header_title)}</h1>
    <p class="subtitle">{html.escape(header_subtitle)} Generated {html.escape(generated_at)}.</p>
  </header>
  <div class="layout">
    <aside>
      <h2>Sections</h2>
      <nav>{toc}</nav>
    </aside>
    <main>
      {dashboard}
      <article class="report-body">
{body}
      </article>
    </main>
  </div>
  <footer>Local HTML artifact generated from the agent-written educational report.</footer>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a StockValuation.io Markdown report to HTML.")
    parser.add_argument("--source", type=Path, help="Markdown report file. Reads stdin when omitted.")
    parser.add_argument("--out-dir", type=Path, default=_default_output_dir(), help="Directory for report artifacts.")
    parser.add_argument("--title", default="StockValuation.io Valuation Report")
    parser.add_argument("--company")
    parser.add_argument("--ticker")
    parser.add_argument("--slug")
    parser.add_argument("--generated-at", default=dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    markdown = args.source.read_text(encoding="utf-8") if args.source else input_from_stdin()
    slug_source = args.slug or args.ticker or args.company or args.title
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = args.out_dir.expanduser().resolve() / f"{_slug(slug_source)}-{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = report_dir / "report.md"
    html_path = report_dir / "index.html"
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(
        build_html(markdown, args.title, args.company, args.ticker, args.generated_at),
        encoding="utf-8",
    )

    print(f"HTML report: {html_path}")
    print(f"Markdown source: {markdown_path}")
    print(f"Browser link: {_file_uri(html_path)}")
    return 0


def input_from_stdin() -> str:
    try:
        import sys

        return sys.stdin.read()
    except KeyboardInterrupt:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
