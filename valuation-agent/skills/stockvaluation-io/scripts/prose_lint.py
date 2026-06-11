#!/usr/bin/env python3
"""Prose linter for StockValuation.io reports.

Pure function over markdown: returns structured findings for banned
generic-AI phrases (maintained in prose_lint_rules.json), process-narration
heuristics, and tables whose data cells are entirely filler. This linter is
the report prose-cleanup gate; the report builder refuses to render on
error-level findings.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent / "prose_lint_rules.json"


def load_rules(path: Path | str | None = None) -> dict:
    return json.loads(Path(path or RULES_PATH).read_text(encoding="utf-8"))


def _table_blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    blocks: list[tuple[int, list[str]]] = []
    current: list[str] = []
    start = 0
    for index, line in enumerate(lines):
        if line.strip().startswith("|"):
            if not current:
                start = index
            current.append(line)
        elif current:
            blocks.append((start, current))
            current = []
    if current:
        blocks.append((start, current))
    return blocks


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    cells = _cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def lint_markdown(markdown: str, rules: dict | None = None) -> list[dict]:
    rules = rules or load_rules()
    findings: list[dict] = []
    lines = markdown.splitlines()

    for entry in rules.get("banned_phrases", []):
        phrase = str(entry.get("phrase") or "").lower()
        if not phrase:
            continue
        for index, line in enumerate(lines, start=1):
            if phrase in line.lower():
                findings.append(
                    {
                        "rule": "banned_phrase",
                        "level": entry.get("level", "error"),
                        "line": index,
                        "phrase": entry.get("phrase"),
                        "excerpt": line.strip()[:160],
                    }
                )

    for entry in rules.get("narration_patterns", []):
        pattern = entry.get("pattern")
        if not pattern:
            continue
        compiled = re.compile(pattern)
        for index, line in enumerate(lines, start=1):
            if compiled.search(line):
                findings.append(
                    {
                        "rule": entry.get("label", "process_narration"),
                        "level": entry.get("level", "error"),
                        "line": index,
                        "excerpt": line.strip()[:160],
                    }
                )

    filler = {str(value).lower() for value in rules.get("filler_cell_values", [])}
    for start, block in _table_blocks(lines):
        data_cells: list[str] = []
        for line in block[1:]:
            if _is_separator(line):
                continue
            data_cells.extend(_cells(line)[1:] or _cells(line))
        if data_cells and all(cell.lower() in filler for cell in data_cells):
            findings.append(
                {
                    "rule": "empty_table",
                    "level": "error",
                    "line": start + 1,
                    "excerpt": block[0].strip()[:160],
                }
            )

    return sorted(findings, key=lambda item: (item["line"], item["rule"]))


def error_findings(findings: list[dict]) -> list[dict]:
    return [finding for finding in findings if finding.get("level") == "error"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint StockValuation report markdown for prose fluff.")
    parser.add_argument("--file", type=Path, default=None, help="Markdown file; defaults to stdin.")
    parser.add_argument("--rules", type=Path, default=None, help="Rules JSON; defaults to bundled rules.")
    args = parser.parse_args()
    markdown = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read()
    findings = lint_markdown(markdown, load_rules(args.rules))
    print(json.dumps({"findings": findings, "errors": len(error_findings(findings))}, indent=2))
    return 1 if error_findings(findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
