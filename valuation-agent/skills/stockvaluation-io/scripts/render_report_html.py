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


def _looks_numeric_cell(value: str) -> bool:
    clean = re.sub(r"<[^>]+>", "", value).strip()
    if not clean:
        return False
    return bool(
        re.fullmatch(
            r"-?\$?\d[\d,]*(?:\.\d+)?(?:\s?%|x|T|B|M|K| trillion| billion| million)?",
            clean,
            re.IGNORECASE,
        )
    )


def _cell_attrs(tag: str, value: str) -> str:
    if _looks_numeric_cell(value):
        return f'{tag} class="num"'
    return tag


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
            output.append(
                "<thead><tr>"
                + "".join(f"<{_cell_attrs('th', cell)}>{_inline(cell)}</th>" for cell in headers)
                + "</tr></thead>"
            )
            output.append("<tbody>")
            for row in rows:
                cells = row + [""] * max(0, len(headers) - len(row))
                output.append(
                    "<tr>"
                    + "".join(f"<{_cell_attrs('td', cell)}>{_inline(cell)}</td>" for cell in cells[: len(headers)])
                    + "</tr>"
                )
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


def _currency(data: dict) -> str:
    return _text(data.get("currency")) or _text(_valuation_output(data).get("currency")) or "USD"


def _currency_symbol(currency: str) -> str:
    return "$" if _text(currency).upper() == "USD" else ""


def _with_currency_symbol(number_text: str, currency: str) -> str:
    symbol = _currency_symbol(currency)
    if symbol:
        if number_text.startswith("-"):
            return f"-{symbol}{number_text[1:]}"
        return f"{symbol}{number_text}"
    return f"{number_text} {currency}".strip()


def _trimmed(number: float, decimals: int) -> str:
    return f"{number:,.{decimals}f}".rstrip("0").rstrip(".")


def _fmt_compact(value, suffix: str = "") -> str:
    number = _number(value)
    if number is None:
        return ""
    sign = "-" if number < 0 else ""
    absolute = abs(number)
    for threshold, label, decimals in (
        (1_000_000_000_000, "T", 2),
        (1_000_000_000, "B", 1),
        (1_000_000, "M", 1),
    ):
        if absolute >= threshold:
            return f"{sign}{_trimmed(absolute / threshold, decimals)}{label}{suffix}"
    return f"{number:,.2f}{suffix}"


def _fmt_money(value, currency: str = "USD", compact: bool = True) -> str:
    number = _number(value)
    if number is None:
        return ""
    formatted = _fmt_compact(number) if compact else f"{number:,.2f}"
    return _with_currency_symbol(formatted, currency)


def _fmt_per_share(value, currency: str = "USD") -> str:
    number = _number(value)
    if number is None:
        return ""
    return _with_currency_symbol(f"{number:,.2f}", currency)


def _fmt_percent(value, decimals: int = 1) -> str:
    number = _number(value)
    if number is None:
        return ""
    return f"{number:,.{decimals}f}%"


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


def _series_points(container: dict, key: str, limit: int = 11) -> list[tuple[str, float]]:
    points: list[tuple[str, float]] = []
    for index, value in enumerate(_list(container.get(key))[:limit]):
        number = _number(value)
        if number is None:
            continue
        label = "Base" if index == 0 else f"Year {index}"
        points.append((label, number))
    return points


def _human_label(value: str) -> str:
    clean = " ".join(_text(value).replace("-", " ").replace("_", " ").split())
    return clean[:1].upper() + clean[1:] if clean else ""


def _assumption_transparency(data: dict) -> dict:
    return _dict(_valuation_output(data).get("assumptionTransparency"))


def _priced_in_expectations(data: dict) -> dict:
    return _dict(_assumption_transparency(data).get("pricedInExpectations"))


def _case_status_label(data: dict) -> str:
    valuation = _dict(data.get("valuation"))
    valuation_output = _valuation_output(data)
    transparency = _assumption_transparency(data)
    audit = _dict(data.get("audit"))
    workflow = _dict(audit.get("workflow_state"))
    for value in (
        data.get("case_status"),
        data.get("caseStatus"),
        data.get("valuation_case_status"),
        data.get("valuationCaseStatus"),
        valuation.get("case_status"),
        valuation.get("caseStatus"),
        valuation_output.get("caseStatus"),
        valuation_output.get("valuationCaseStatus"),
        transparency.get("valuationCaseStatus"),
        audit.get("case_status"),
        audit.get("caseStatus"),
        audit.get("final_case_type"),
        workflow.get("case_status"),
        workflow.get("caseStatus"),
    ):
        label = _human_label(str(value)) if value not in (None, "") else ""
        if label:
            return label
    if isinstance(valuation.get("range"), dict):
        return "Unresolved range"
    gates = _dict(workflow.get("gates"))
    guided = _dict(gates.get("guided_refinement"))
    guided_status = " ".join(
        _text(guided.get(key)).lower()
        for key in ("status", "outcome")
        if _text(guided.get(key))
    )
    if any(token in guided_status for token in ("applied", "complete", "cleared")):
        return "User refined scenario"
    evidence = _dict(gates.get("evidence_review"))
    evidence_status = " ".join(
        _text(evidence.get(key)).lower()
        for key in ("status", "outcome")
        if _text(evidence.get(key))
    )
    if any(token in evidence_status for token in ("approved", "accepted", "cleared", "bypassed")):
        return "Evidence constrained base"
    return "Diagnostic baseline"


def _market_price_value(data: dict) -> float | None:
    valuation = _valuation_output(data)
    company = _dict(valuation.get("companyDTO"))
    priced_in = _priced_in_expectations(data)
    for value in (
        data.get("market_price"),
        data.get("marketPrice"),
        company.get("price"),
        priced_in.get("marketPrice"),
    ):
        number = _number(value)
        if number is not None:
            return number
    return None


def _money_chart_unit(values: list[float], currency: str) -> tuple[str, float, str]:
    maximum = max((abs(value) for value in values), default=0.0)
    label_prefix = _text(currency).upper() or "Currency"
    if maximum >= 1_000_000_000_000:
        return f"{label_prefix} trillions", 1_000_000_000_000.0, "T"
    if maximum >= 1_000_000_000:
        return f"{label_prefix} billions", 1_000_000_000.0, "B"
    if maximum >= 1_000_000:
        return f"{label_prefix} millions", 1_000_000.0, "M"
    return f"{label_prefix} millions", 1.0, "M"


def _format_scaled_money(value: float, currency: str, scale: float, suffix: str) -> str:
    return _with_currency_symbol(f"{_trimmed(value / scale, 1)}{suffix}", currency)


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
        f'<div class="legacy-metric{tone_class}">'
        f'<span class="metric-label">{html.escape(label)}</span>'
        f'<strong>{html.escape(value)}</strong>'
        f"{note_html}</div>"
    )


def _valuation_text(data: dict) -> str:
    currency = _currency(data)
    valuation = _dict(data.get("valuation"))
    point = _dict(valuation.get("point"))
    value_range = _dict(valuation.get("range"))
    point_value = _number(point.get("value_per_share"))
    if point_value is not None:
        return _fmt_per_share(point_value, currency)
    low = _number(value_range.get("low"))
    high = _number(value_range.get("high"))
    if low is not None and high is not None:
        return f"{_fmt_per_share(min(low, high), currency)}-{_fmt_per_share(max(low, high), currency)}"
    company = _dict(_valuation_output(data).get("companyDTO"))
    fallback = _number(company.get("estimatedValuePerShare"))
    return _fmt_per_share(fallback, currency) if fallback is not None else ""


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


def _framing_questions_html(data: dict) -> str:
    prose = _dict(data.get("prose"))
    revealed = _dict(data.get("revealedThesis") or data.get("revealed_thesis"))
    questions = revealed.get("framing_questions") if revealed.get("schema_version") == "revealed_thesis.v1" else None
    if questions in (None, ""):
        questions = prose.get("framing_questions")
    if questions in (None, ""):
        questions = data.get("framing_questions")
    cards: list[str] = []
    if isinstance(questions, str):
        text = _text(questions)
        if text:
            cards.append(
                '<article class="framing-question"><span>Driver question</span>'
                f"<p>{html.escape(text)}</p></article>"
            )
    elif isinstance(questions, list):
        for item in questions[:5]:
            if isinstance(item, dict):
                question = _text(item.get("question"))
                if not question:
                    continue
                driver = _human_label(_text(item.get("driver"))) or "Valuation driver"
                context = _text(item.get("context") or item.get("why_it_matters") or item.get("why"))
                context_html = f"<small>{html.escape(context)}</small>" if context else ""
                cards.append(
                    '<article class="framing-question">'
                    f"<span>{html.escape(driver)}</span><p>{html.escape(question)}</p>{context_html}</article>"
                )
            else:
                text = _text(str(item))
                if text:
                    cards.append(
                        '<article class="framing-question"><span>Driver question</span>'
                        f"<p>{html.escape(text)}</p></article>"
                    )
    if not cards:
        return ""
    return (
        '<div class="framing-block"><p class="eyebrow">Framing questions</p>'
        '<div class="framing-question-grid">'
        + "\n".join(cards)
        + "</div></div>"
    )


def _string_list(value) -> list[str]:
    if isinstance(value, list):
        return [_text(str(item)) for item in value if _text(str(item))]
    text = _text(str(value)) if value not in (None, "") else ""
    return [text] if text else []


def _basis_warning_items(data: dict) -> list[str]:
    warnings: list[str] = []

    def extend(value) -> None:
        warnings.extend(_string_list(value))

    valuation = _valuation_output(data)
    transparency = _assumption_transparency(data)
    audit = _dict(data.get("audit"))
    source_gate = _dict(data.get("sourceQualityGate") or data.get("source_quality_gate"))
    if not source_gate:
        source_gate = _dict(valuation.get("sourceQualityGate") or transparency.get("sourceQualityGate"))
    for key in (
        "weak_basis_warnings",
        "weakBasisWarnings",
        "valuation_basis_warnings",
        "valuationBasisWarnings",
        "basis_warnings",
        "warnings",
    ):
        extend(data.get(key))
        extend(valuation.get(key))
        extend(audit.get(key))
    extend(transparency.get("baselineWarnings"))
    extend(valuation.get("baselineWarnings"))
    extend(source_gate.get("warnings"))
    extend(source_gate.get("dataQualityWarnings") or source_gate.get("data_quality_warnings"))
    gate_status = _text(source_gate.get("status") or source_gate.get("sourceQualityGateStatus"))
    gate_reason = _text(source_gate.get("reason") or source_gate.get("message"))
    if gate_status and gate_status.lower() not in {"pass", "passed", "ok", "clear", "cleared"} and gate_reason:
        warnings.append(gate_reason)
    seen: set[str] = set()
    deduped: list[str] = []
    for warning in warnings:
        clean = " ".join(warning.split())
        key = clean.lower()
        if clean and key not in seen:
            deduped.append(clean)
            seen.add(key)
    return deduped


def _basis_banner_html(data: dict) -> str:
    warnings = _basis_warning_items(data)
    if not warnings:
        return ""
    items = "".join(f"<li>{html.escape(item)}</li>" for item in warnings[:4])
    return (
        '<div class="basis-banner" aria-label="Basis warnings">'
        '<strong>Basis warning</strong><ul>'
        + items
        + "</ul></div>"
    )


def _report_summary_html(markdown: str, data: dict, company: str | None, ticker: str | None, generated_at: str) -> str:
    valuation = _valuation_output(data)
    company_dto = _dict(valuation.get("companyDTO"))
    priced_in = _priced_in_expectations(data)
    base_case = _dict(priced_in.get("baseCase"))
    currency = _currency(data)
    company_name = _text(data.get("company")) or _text(company) or _text(valuation.get("companyName")) or "Valuation"
    ticker_text = _text(data.get("ticker")) or _text(ticker)
    report_label = "StockValuation.io report" + (f" / {ticker_text}" if ticker_text else "")
    market_price = _market_price_value(data)
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
            _metric("Value/share", value_per_share, "returned case", "primary"),
            _metric("Market price", _fmt_per_share(market_price, currency), "returned price"),
            _metric("Price gap", gap_text, gap_note, "negative" if gap_pct and gap_pct > 0 else "positive"),
            _metric("Case status", _case_status_label(data), "valuation basis"),
        )
        if item
    )
    chips = _status_chips(data)
    top_thesis = _section_text(markdown, "Investment Thesis")
    thesis_source = top_thesis or bottom_line
    thesis = _shorten(thesis_source, 330) if thesis_source else "The report connects business story, assumptions, valuation math, and data limits in one local artifact."
    framing_questions = _framing_questions_html(data)
    basis_banner = _basis_banner_html(data)
    return f"""
<section class="report-brief" aria-label="Report summary">
  <div class="brief-copy thesis-panel">
    <p class="eyebrow">{html.escape(report_label)}</p>
    <h2>{html.escape(company_name)}</h2>
    <p class="brief-thesis">{html.escape(thesis)}</p>
    <div class="status-row">{chips}</div>
  </div>
  <div class="value-card">
    <span class="metric-label">Value/share</span>
    <strong>{html.escape(value_per_share or "See report")}</strong>
    <p>{html.escape(_case_status_label(data))}</p>
  </div>
  <div class="legacy-metric-grid">{metrics}</div>
  {framing_questions}
  {basis_banner}
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
    currency = _currency(data)
    model_value = _fmt_per_share(base_case.get("intrinsicValue") or priced_in.get("modelIntrinsicValue"), currency)
    market_price = _fmt_per_share(priced_in.get("marketPrice"), currency)
    gap = _fmt(base_case.get("gapToMarketPct"), "%", decimals=1)
    solved = [row for row in frontier if isinstance(row, dict) and row.get("solved") is True]
    frontier_rows = []
    for row in solved[:3]:
        margin = _fmt(row.get("operatingMargin"), "%", decimals=1)
        growth = _fmt(row.get("impliedRevenueGrowth"), "%", decimals=1)
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


def _svg_line_chart(
    title: str,
    points: list[tuple[str, float]],
    color: str,
    unit_label: str,
    takeaway: str,
    formatter,
) -> str:
    if len(points) < 2:
        return ""
    points = points[:11]
    values = [value for _, value in points]
    width = 680
    height = 260
    left_pad = 54
    right_pad = 26
    top_pad = 26
    bottom_pad = 54
    low = min(values)
    high = max(values)
    spread = high - low or 1.0
    step = (width - left_pad - right_pad) / (len(points) - 1)
    plotted: list[tuple[str, float, float, float]] = []
    for index, (label, value) in enumerate(points):
        x = left_pad + index * step
        y = height - bottom_pad - ((value - low) / spread * (height - top_pad - bottom_pad))
        plotted.append((label, value, x, y))
    polyline = " ".join(f"{x:.1f},{y:.1f}" for _, _, x, y in plotted)
    x_labels = "\n".join(
        f'<text class="axis-label" x="{x:.1f}" y="{height - 18}" text-anchor="middle">{html.escape(label)}</text>'
        for label, _, x, _ in plotted
    )
    y_labels = "\n".join(
        (
            f'<text class="axis-label" x="{left_pad - 10}" y="{top_pad + 4}" text-anchor="end">{html.escape(formatter(high))}</text>',
            f'<text class="axis-label" x="{left_pad - 10}" y="{height - bottom_pad + 4}" text-anchor="end">{html.escape(formatter(low))}</text>',
        )
    )
    end_label, end_value, end_x, end_y = plotted[-1]
    return f"""
<figure class="chart-card" data-chart-kind="line">
  <div class="chart-header">
    <figcaption class="chart-title">{html.escape(title)}</figcaption>
    <span class="chart-unit">{html.escape(unit_label)}</span>
  </div>
  <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
    <line class="axis" x1="{left_pad}" y1="{height - bottom_pad}" x2="{width - right_pad}" y2="{height - bottom_pad}" />
    <line class="axis" x1="{left_pad}" y1="{top_pad}" x2="{left_pad}" y2="{height - bottom_pad}" />
    {y_labels}
    {x_labels}
    <polyline points="{polyline}" style="stroke:{color}" />
    <circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4.5" style="fill:{color}" />
    <text class="point-label" x="{min(width - right_pad, end_x + 8):.1f}" y="{max(18, end_y - 8):.1f}">{html.escape(formatter(end_value))}</text>
  </svg>
  <p class="chart-takeaway">{html.escape(takeaway)}</p>
</figure>
"""


def _bridge_html(data: dict) -> str:
    company = _dict(_valuation_output(data).get("companyDTO"))
    currency = _currency(data)
    rows = [
        ("PV explicit cash flows", _number(company.get("pvCFOverNext10Years")), "positive"),
        ("PV terminal value", _number(company.get("pvTerminalValue")), "positive"),
        ("Operating asset value", _number(company.get("valueOfOperatingAssets")), "positive"),
        ("Cash", _number(company.get("cash")), "positive"),
        ("Debt", _number(company.get("debt")), "negative"),
        ("Equity value", _number(company.get("valueOfEquity")), "positive"),
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
            f'<strong>{html.escape(_fmt_money(value, currency))}</strong></div>'
        )
    return (
        '<figure class="chart-card bridge-chart">'
        '<div class="chart-header"><figcaption class="chart-title">Valuation bridge</figcaption>'
        f'<span class="chart-unit">{html.escape(_text(currency).upper() or "Currency")}</span></div>'
        + "\n".join(rendered)
        + '<p class="chart-takeaway">The bridge shows how explicit cash flows, terminal value, cash, and debt reconcile toward returned equity value.</p>'
        + "</figure>"
    )


def _sensitivity_heatmap_html(data: dict) -> str:
    priced_in = _priced_in_expectations(data)
    grid = [row for row in _list(priced_in.get("grid")) if isinstance(row, dict)]
    if not grid:
        return ""
    margin_values = sorted(
        {
            _number(row.get("operatingMargin"))
            for row in grid
            if _number(row.get("operatingMargin")) is not None
        }
    )
    growth_values = sorted(
        {
            _number(row.get("revenueGrowth"))
            for row in grid
            if _number(row.get("revenueGrowth")) is not None
        }
    )
    values = [
        _number(row.get("intrinsicValue"))
        for row in grid
        if _number(row.get("intrinsicValue")) is not None
    ]
    if not margin_values or not growth_values or not values:
        return ""
    currency = _currency(data)
    minimum = min(values)
    maximum = max(values)
    spread = maximum - minimum or 1.0
    value_by_axis: dict[tuple[float, float], float] = {}
    for row in grid:
        margin = _number(row.get("operatingMargin"))
        growth = _number(row.get("revenueGrowth"))
        intrinsic = _number(row.get("intrinsicValue"))
        if margin is None or growth is None or intrinsic is None:
            continue
        value_by_axis[(round(margin, 4), round(growth, 4))] = intrinsic
    column_labels = "".join(
        f'<span class="heatmap-axis-label">{html.escape(_fmt_percent(growth))}</span>'
        for growth in growth_values
    )
    rows_html: list[str] = []
    for margin in reversed(margin_values):
        cells = []
        for growth in growth_values:
            value = value_by_axis.get((round(margin, 4), round(growth, 4)))
            if value is None:
                cells.append('<span class="heatmap-cell empty"></span>')
                continue
            ratio = (value - minimum) / spread
            hue = 2 + ratio * 140
            cells.append(
                '<span class="heatmap-cell" '
                f'style="background:hsl({hue:.0f} 72% 36%);" '
                f'title="Margin {_fmt_percent(margin)}, growth {_fmt_percent(growth)}">'
                f"{html.escape(_fmt_per_share(value, currency))}</span>"
            )
        rows_html.append(
            '<div class="heatmap-row">'
            f'<span class="heatmap-axis-label y">{html.escape(_fmt_percent(margin))}</span>'
            + "".join(cells)
            + "</div>"
        )
    return f"""
<figure class="sensitivity-heatmap" data-chart-kind="sensitivity">
  <div class="chart-header">
    <figcaption class="chart-title">Sensitivity heatmap</figcaption>
    <span class="chart-unit">Value/share across deterministic grid</span>
  </div>
  <div class="heatmap-shell" style="--heatmap-cols: {len(growth_values)};">
    <div class="heatmap-corner">Revenue growth</div>
    <div class="heatmap-x">{column_labels}</div>
    <div class="heatmap-y-title">Operating margin</div>
    <div class="heatmap-body">{''.join(rows_html)}</div>
  </div>
  <div class="heatmap-legend"><span>Lower value</span><i></i><span>Higher value</span></div>
  <p class="chart-takeaway">The grid is generated from returned deterministic sensitivity output; it is not a scenario story.</p>
</figure>
"""


def _visuals_html(data: dict) -> str:
    valuation = _valuation_output(data)
    financial = _dict(valuation.get("financialDTO"))
    currency = _currency(data)
    revenue_points = _series_points(financial, "revenues")
    revenue_unit, revenue_scale, revenue_suffix = _money_chart_unit([value for _, value in revenue_points], currency)
    fcff_points = _series_points(financial, "fcff")
    fcff_unit, fcff_scale, fcff_suffix = _money_chart_unit([value for _, value in fcff_points], currency)
    charts = [
        _svg_line_chart(
            "Revenue path",
            revenue_points,
            "#20DF7F",
            revenue_unit,
            "The revenue path shows the base year and returned projection years used in the valuation.",
            lambda value: _format_scaled_money(value, currency, revenue_scale, revenue_suffix),
        ),
        _svg_line_chart(
            "Operating margin",
            _series_points(financial, "ebitOperatingMargin"),
            "#F59E0B",
            "Percent",
            "The margin path shows whether the thesis depends on step-change profitability or gradual convergence.",
            lambda value: _fmt_percent(value),
        ),
        _svg_line_chart(
            "Free cash flow path",
            fcff_points,
            "#3B82F6",
            fcff_unit,
            "The free-cash-flow path shows how operating assumptions translate into distributable cash flow.",
            lambda value: _format_scaled_money(value, currency, fcff_scale, fcff_suffix),
        ),
        _bridge_html(data),
        _sensitivity_heatmap_html(data),
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
      --bg: #050605;
      --surface: #111312;
      --surface-2: #181b1a;
      --surface-3: #222624;
      --ink: #FFFFFF;
      --muted: #cfd6d2;
      --faint: #8b9690;
      --line: #2b302d;
      --line-strong: #3a443e;
      --accent: #20DF7F;
      --accent-dark: #15B766;
      --danger: #EF4444;
      --warning: #F59E0B;
      --info: #3B82F6;
      --accent-soft: rgba(32, 223, 127, 0.12);
      --warning-soft: rgba(245, 158, 11, 0.12);
      --danger-soft: rgba(239, 68, 68, 0.13);
      --shadow: 0 10px 26px rgba(0, 0, 0, 0.24);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font-family: Nunito, "Avenir Next", Avenir, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 15px;
      line-height: 1.55;
    }}
    header {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 22px 28px 16px;
      border-bottom: 1px solid var(--line);
    }}
    .kicker,
    .eyebrow,
    .metric-label,
    aside h2,
    .chart-unit {{
      color: var(--faint);
      display: block;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .kicker {{
      color: var(--accent);
      margin: 0 0 6px;
    }}
    h1 {{
      font-size: 38px;
      font-weight: 800;
      line-height: 1.08;
      margin: 0 0 8px;
      letter-spacing: 0;
      overflow-wrap: break-word;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      max-width: 860px;
      font-size: 14px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(170px, 220px) minmax(0, 1fr);
      gap: 22px;
      max-width: 1320px;
      margin: 0 auto;
      padding: 20px 28px 52px;
      align-items: start;
    }}
    aside {{
      position: sticky;
      top: 16px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-left: 3px solid var(--accent);
      border-radius: 8px;
      padding: 12px;
    }}
    aside h2 {{
      margin: 0 0 10px;
    }}
    .toc-link {{
      display: block;
      color: var(--muted);
      text-decoration: none;
      padding: 6px 0;
      border-top: 1px solid var(--line);
      font-size: 12px;
    }}
    .toc-link:hover {{ color: var(--accent); }}
    main {{ min-width: 0; }}
    .report-brief {{
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(250px, 0.48fr);
      gap: 14px;
      align-items: stretch;
      margin-bottom: 16px;
    }}
    .thesis-panel,
    .value-card,
    .legacy-metric,
    .framing-question,
    .basis-banner,
    .driver-card,
    .market-panel,
    .chart-card,
    .report-body {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .thesis-panel {{
      padding: 22px;
      border-left: 3px solid var(--accent);
    }}
    .brief-copy h2 {{
      margin: 3px 0 10px;
      font-size: 27px;
      font-weight: 800;
      line-height: 1.14;
      letter-spacing: 0;
      overflow-wrap: break-word;
    }}
    .brief-thesis {{
      max-width: 74ch;
      color: var(--muted);
      font-size: 15px;
      margin: 0;
    }}
    .status-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-top: 16px;
    }}
    .status-chip {{
      border: 1px solid var(--line-strong);
      border-radius: 5px;
      padding: 3px 7px;
      color: var(--muted);
      background: var(--surface-2);
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .status-chip.source {{
      background: var(--accent-soft);
      border-color: rgba(32, 223, 127, 0.28);
      color: var(--accent);
    }}
    .value-card {{
      padding: 20px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      border-left: 3px solid var(--accent);
      min-height: 136px;
    }}
    .value-card strong {{
      display: block;
      color: var(--accent);
      font-size: 34px;
      line-height: 1;
      margin: 7px 0 9px;
      overflow-wrap: anywhere;
    }}
    .value-card p {{
      color: var(--muted);
      margin: 0;
      font-weight: 800;
    }}
    .legacy-metric-grid {{
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }}
    .legacy-metric {{
      padding: 13px;
      min-width: 0;
      transition: transform 0.2s ease, border-color 0.2s ease;
    }}
    .legacy-metric:hover {{
      transform: translateY(-1px);
      border-color: var(--line-strong);
    }}
    .legacy-metric.primary {{ border-left: 3px solid var(--accent); }}
    .legacy-metric.negative {{ border-left: 3px solid var(--danger); }}
    .legacy-metric.positive {{ border-left: 3px solid var(--accent); }}
    .legacy-metric strong {{
      display: block;
      margin-top: 5px;
      font-size: 19px;
      line-height: 1.15;
      overflow-wrap: anywhere;
    }}
    .metric-note {{
      display: block;
      color: var(--faint);
      font-size: 12px;
      margin-top: 6px;
    }}
    .framing-block {{
      grid-column: 1 / -1;
    }}
    .framing-question-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 7px;
    }}
    .framing-question {{
      border-left: 3px solid var(--accent);
      padding: 13px;
      min-height: 118px;
    }}
    .framing-question span,
    .driver-card span {{
      color: var(--accent);
      display: block;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .framing-question p {{
      color: var(--ink);
      font-weight: 700;
      margin: 7px 0 5px;
      line-height: 1.35;
    }}
    .framing-question small {{
      color: var(--muted);
      display: block;
      line-height: 1.45;
    }}
    .basis-banner {{
      grid-column: 1 / -1;
      border-left: 3px solid var(--warning);
      padding: 12px 14px;
      background: var(--surface-2);
    }}
    .basis-banner strong {{
      color: var(--warning);
      display: block;
      margin-bottom: 6px;
    }}
    .basis-banner ul {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
    }}
    .generated-line {{
      grid-column: 1 / -1;
      color: var(--faint);
      font-size: 13px;
      margin: 0;
      padding-top: 6px;
    }}
    .driver-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 16px 0 0;
    }}
    .driver-card {{
      border-left: 3px solid var(--accent);
      padding: 14px;
      min-width: 0;
    }}
    .driver-card h3 {{
      margin: 5px 0 7px;
      font-size: 16px;
      font-weight: 800;
    }}
    .driver-card p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .visual-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin: 16px 0 0;
    }}
    .chart-card,
    .sensitivity-heatmap {{
      margin: 0;
      min-width: 0;
      padding: 0;
      overflow: hidden;
    }}
    .chart-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px 9px;
      border-bottom: 1px solid var(--line);
      background: var(--surface-2);
    }}
    .chart-title {{
      color: var(--ink);
      font-size: 14px;
      font-weight: 800;
      margin: 0;
      text-transform: none;
    }}
    .chart-unit {{
      color: var(--accent);
      text-align: right;
      white-space: nowrap;
    }}
    .chart-card svg {{
      width: 100%;
      min-height: 220px;
      display: block;
      padding: 8px 10px 0;
    }}
    .chart-card .axis {{
      stroke: var(--line-strong);
      stroke-width: 1;
    }}
    .chart-card polyline {{
      fill: none;
      stroke-width: 3.25;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    .chart-card text {{
      fill: var(--muted);
      font-size: 11px;
      font-weight: 800;
    }}
    .chart-card .point-label {{
      fill: var(--ink);
    }}
    .chart-takeaway {{
      color: var(--muted);
      border-top: 1px solid var(--line);
      margin: 0;
      padding: 10px 14px 12px;
      font-size: 12px;
    }}
    .bridge-row {{
      display: grid;
      grid-template-columns: minmax(140px, 0.9fr) minmax(150px, 1.2fr) minmax(82px, 0.42fr);
      gap: 10px;
      align-items: center;
      margin: 9px 14px;
      font-size: 12px;
    }}
    .bridge-track {{
      height: 10px;
      background: var(--surface-3);
      border-radius: 999px;
      overflow: hidden;
    }}
    .bridge-track i {{ display: block; height: 100%; border-radius: inherit; }}
    .bridge-track i.positive {{ background: var(--accent); }}
    .bridge-track i.negative {{ background: var(--danger); }}
    .bridge-row strong {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    .sensitivity-heatmap {{
      grid-column: 1 / -1;
    }}
    .heatmap-shell {{
      display: grid;
      grid-template-columns: 108px minmax(400px, 1fr);
      grid-template-rows: auto 1fr;
      gap: 7px;
      overflow-x: auto;
      padding: 14px;
    }}
    .heatmap-corner,
    .heatmap-y-title,
    .heatmap-axis-label {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
    }}
    .heatmap-corner {{ text-align: right; padding-right: 8px; }}
    .heatmap-x {{
      display: grid;
      grid-template-columns: repeat(var(--heatmap-cols), minmax(78px, 1fr));
      gap: 4px;
      min-width: calc(var(--heatmap-cols) * 78px);
    }}
    .heatmap-x .heatmap-axis-label {{ text-align: center; }}
    .heatmap-y-title {{
      writing-mode: vertical-rl;
      transform: rotate(180deg);
      align-self: center;
      justify-self: center;
      min-height: 120px;
    }}
    .heatmap-body {{
      min-width: calc(var(--heatmap-cols) * 78px);
    }}
    .heatmap-row {{
      display: grid;
      grid-template-columns: 66px repeat(var(--heatmap-cols), minmax(78px, 1fr));
      gap: 4px;
      margin-bottom: 4px;
      align-items: stretch;
    }}
    .heatmap-axis-label.y {{
      display: flex;
      align-items: center;
      justify-content: flex-end;
      padding-right: 8px;
    }}
    .heatmap-cell {{
      min-height: 40px;
      border-radius: 5px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #FFFFFF;
      font-size: 11px;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
      white-space: nowrap;
    }}
    .heatmap-cell.empty {{
      background: var(--surface-3);
    }}
    .heatmap-legend {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      color: var(--faint);
      font-size: 12px;
      padding: 0 16px 12px;
    }}
    .heatmap-legend i {{
      display: block;
      width: 180px;
      height: 10px;
      border-radius: 999px;
      background: linear-gradient(90deg, hsl(2 72% 36%), hsl(70 72% 36%), hsl(142 72% 36%));
    }}
    .market-panel {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 0.6fr);
      gap: 16px;
      margin-top: 16px;
      padding: 16px;
      border-left: 3px solid var(--accent);
    }}
    .market-panel h3 {{
      margin: 3px 0 7px;
      font-size: 20px;
      font-weight: 800;
      line-height: 1.18;
    }}
    .market-panel p {{ margin: 0; color: var(--muted); }}
    .market-facts {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 0;
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .market-facts div {{
      border-bottom: 1px solid var(--line);
      padding: 10px 11px;
      background: var(--surface-2);
    }}
    .market-facts div:last-child {{ border-bottom: 0; }}
    .market-facts dt,
    .market-facts dd {{ margin: 0; }}
    .market-facts dt {{
      color: var(--faint);
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .market-facts dd {{
      margin-top: 5px;
      font-size: 16px;
      font-weight: 800;
    }}
    .market-detail {{
      grid-column: 1 / -1;
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }}
    .market-detail ul {{ margin-bottom: 0; columns: 2; column-gap: 24px; }}
    .report-body {{
      margin-top: 16px;
      padding: 22px;
    }}
    .report-body h1 {{
      color: var(--ink);
      font-size: 25px;
      font-weight: 800;
      margin-top: 0;
    }}
    .report-body h2 {{
      color: var(--ink);
      font-size: 20px;
      font-weight: 800;
      margin: 28px 0 10px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
    }}
    .report-body h3 {{ color: var(--accent); font-size: 16px; margin-top: 22px; }}
    .report-body h4 {{ color: var(--warning); font-size: 15px; margin-top: 20px; }}
    p {{ margin: 0 0 12px; }}
    ul, ol {{ padding-left: 22px; margin: 0 0 14px; }}
    li {{ margin: 4px 0; }}
    code {{
      background: var(--surface-2);
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 1px 4px;
      font-size: 0.92em;
    }}
    pre {{
      overflow: auto;
      background: var(--surface-2);
      border: 1px solid var(--line);
      color: var(--ink);
      border-radius: 8px;
      padding: 14px;
    }}
    pre code {{ background: transparent; border: 0; color: inherit; padding: 0; }}
    .table-wrap {{
      overflow-x: auto;
      margin: 14px 0 20px;
      border: 1px solid var(--line);
      border-radius: 8px;
      -webkit-overflow-scrolling: touch;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      min-width: 680px;
      background: var(--surface);
    }}
    th, td {{
      padding: 8px 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      text-align: left;
    }}
    th {{
      background: var(--surface-2);
      color: var(--ink);
      font-size: 10px;
      font-weight: 900;
      position: sticky;
      top: 0;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    td {{
      color: var(--muted);
    }}
    td:first-child {{
      color: var(--ink);
      font-weight: 700;
    }}
    th.num,
    td.num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    a {{ color: var(--accent); }}
    .muted {{ color: var(--faint); }}
    footer {{
      color: var(--faint);
      font-size: 12px;
      padding: 0 32px 30px;
      max-width: 1320px;
      margin: 0 auto;
    }}
    @media (max-width: 980px) {{
      header {{ padding: 20px 16px 16px; }}
      h1 {{ font-size: 28px; line-height: 1.08; }}
      .layout {{
        grid-template-columns: 1fr;
        padding: 16px 14px 44px;
      }}
      aside {{ display: none; }}
      .market-panel,
      .visual-grid {{
        grid-template-columns: 1fr;
      }}
      .report-brief {{
        display: flex;
        flex-direction: column;
      }}
      .thesis-panel {{ order: 1; }}
      .value-card {{ order: 2; }}
      .framing-block {{ order: 3; }}
      .legacy-metric-grid {{ order: 4; }}
      .basis-banner {{ order: 5; }}
      .generated-line {{ order: 6; }}
      .thesis-panel,
      .value-card,
      .report-body {{
        padding: 16px;
      }}
      .brief-copy h2 {{ font-size: 23px; line-height: 1.12; }}
      .brief-thesis {{ font-size: 14.5px; }}
      .value-card {{
        min-height: auto;
      }}
      .value-card strong {{
        font-size: 31px;
      }}
      .legacy-metric-grid,
      .framing-question-grid,
      .driver-grid {{
        grid-template-columns: 1fr;
      }}
      .market-detail ul {{ columns: 1; }}
      .chart-header {{
        display: block;
      }}
      .chart-unit {{
        text-align: left;
        margin-top: 4px;
      }}
      .chart-card svg {{
        min-height: 200px;
      }}
      table {{ min-width: 560px; }}
      .bridge-row {{
        grid-template-columns: 1fr;
        align-items: start;
      }}
      .bridge-row strong {{ text-align: left; }}
      .heatmap-shell {{
        grid-template-columns: 96px minmax(360px, 1fr);
        padding: 12px;
      }}
      .heatmap-x,
      .heatmap-body {{
        min-width: calc(var(--heatmap-cols) * 76px);
      }}
      .heatmap-row {{
        grid-template-columns: 62px repeat(var(--heatmap-cols), minmax(76px, 1fr));
      }}
      .heatmap-cell {{
        min-height: 40px;
        font-size: 11px;
      }}
      .heatmap-legend i {{
        width: 150px;
      }}
    }}
    @media print {{
      body {{ background: #fff; color: #000; }}
      header, aside, footer {{ display: none; }}
      .layout {{ display: block; padding: 0; }}
      .report-body,
      .thesis-panel,
      .value-card,
      .legacy-metric,
      .framing-question,
      .driver-card,
      .chart-card,
      .sensitivity-heatmap,
      .market-panel {{
        box-shadow: none;
        border-color: #999;
      }}
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
