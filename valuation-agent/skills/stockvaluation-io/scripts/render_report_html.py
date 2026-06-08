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


def build_html(markdown: str, title: str, company: str | None, ticker: str | None, generated_at: str) -> str:
    body, headings = render_markdown(markdown)
    toc_items = [
        f'<a class="toc-link level-{level}" href="#{heading_id}">{html.escape(text)}</a>'
        for level, text, heading_id in headings
        if level <= 2
    ]
    identity = " / ".join(part for part in [company, ticker] if part)
    subtitle = identity or "Educational valuation report"
    toc = "\n".join(toc_items) if toc_items else '<span class="muted">No sections found</span>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --paper: #ffffff;
      --ink: #171717;
      --muted: #5f6673;
      --line: #d9dde4;
      --accent: #0f766e;
      --accent-2: #a16207;
      --header: #10202a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      background: var(--header);
      color: #fff;
      padding: 28px min(5vw, 52px);
      border-bottom: 4px solid var(--accent);
    }}
    .kicker {{
      color: #b8c7d0;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0;
      margin: 0 0 8px;
    }}
    h1 {{
      font-size: clamp(28px, 4vw, 44px);
      line-height: 1.1;
      margin: 0 0 10px;
      letter-spacing: 0;
    }}
    .subtitle {{
      margin: 0;
      color: #d9e2e7;
      max-width: 760px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(180px, 260px) minmax(0, 1fr);
      gap: 24px;
      padding: 24px min(5vw, 52px) 52px;
      align-items: start;
    }}
    aside {{
      position: sticky;
      top: 16px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    aside h2 {{
      font-size: 13px;
      margin: 0 0 10px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .toc-link {{
      display: block;
      color: var(--ink);
      text-decoration: none;
      padding: 7px 0;
      border-top: 1px solid #edf0f4;
    }}
    .toc-link:hover {{ color: var(--accent); }}
    main {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: clamp(20px, 4vw, 42px);
      min-width: 0;
    }}
    main h1 {{ color: var(--header); font-size: 34px; margin-top: 0; }}
    main h2 {{
      color: var(--header);
      font-size: 24px;
      margin: 34px 0 12px;
      padding-top: 22px;
      border-top: 1px solid var(--line);
    }}
    main h3 {{ color: var(--accent); font-size: 18px; margin-top: 26px; }}
    main h4 {{ color: var(--accent-2); font-size: 16px; margin-top: 22px; }}
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
    th {{ background: #eef7f6; color: #123936; font-weight: 650; }}
    tr:last-child td {{ border-bottom: 0; }}
    a {{ color: var(--accent); }}
    .muted {{ color: var(--muted); }}
    footer {{
      color: var(--muted);
      font-size: 13px;
      padding: 0 min(5vw, 52px) 30px;
    }}
    @media (max-width: 860px) {{
      .layout {{ grid-template-columns: 1fr; padding-top: 16px; }}
      aside {{ position: static; }}
      main {{ padding: 18px; }}
      table {{ min-width: 560px; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      header, aside, footer {{ display: none; }}
      .layout {{ display: block; padding: 0; }}
      main {{ border: 0; padding: 0; }}
      a {{ color: inherit; text-decoration: none; }}
    }}
  </style>
</head>
<body>
  <header>
    <p class="kicker">StockValuation.io</p>
    <h1>{html.escape(title)}</h1>
    <p class="subtitle">{html.escape(subtitle)}. Generated {html.escape(generated_at)}.</p>
  </header>
  <div class="layout">
    <aside>
      <h2>Sections</h2>
      <nav>{toc}</nav>
    </aside>
    <main>
{body}
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
