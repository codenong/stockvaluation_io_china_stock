"""M4: code-assembled report builder and deterministic prose linter."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from valuation_agent.installer import bundled_skill_dir

SCRIPTS_DIR = bundled_skill_dir() / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report_data(**overrides):
    data = {
        "company": "Space Exploration Technologies",
        "ticker": "SPCX",
        "currency": "USD",
        "valuation": {"point": {"value_per_share": 4.07}},
        "prose": {
            "business_story": "The company sells launch services and satellite connectivity, with launch revenue funding the satellite build-out.",
            "growth": "Filing history shows revenue rising from 10.4B to 18.7B over two years; the base case assumes that pace fades by half.",
            "profitability": "Only one filing year was operationally profitable; the target margin stays near that best reported year.",
            "reinvestment": "Capital spending exceeded revenue gains in the latest year, so each dollar of growth remains expensive.",
            "risk": "Launch cadence and satellite capacity pricing are the dominant company-specific risks.",
            "bottom_line": "The value rides on whether reinvestment efficiency improves; the margin driver remains the weakest evidence.",
        },
        "key_assumptions": [
            {"driver": "revenue_growth", "value": 34.08, "unit": "percent", "source": "anchor:base"},
            {"driver": "target_operating_margin", "value": 3.33, "unit": "percent", "source": "anchor:base"},
            {"driver": "sales_to_capital", "value": 0.22, "unit": "ratio", "source": "user_input"},
            {"driver": "terminal_growth", "value": 2.5, "unit": "percent", "source": "service"},
        ],
        "guided_judgment": [
            {
                "question": "Should growth follow the filing CAGR?",
                "driver": "revenue_growth",
                "answer": "Accepted default",
                "source": "anchor:base",
            }
        ],
        "data_limits": ["Segment-level margins come from a single filing year."],
        "sources": [
            {
                "title": "SpaceX S-1/A",
                "url": "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
                "date": "2026-06-03",
            }
        ],
        "audit": {
            "workflow_state": {
                "run_id": "run-abc123",
                "gates": {
                    "evidence_review": {"status": "cleared", "outcome": "approved"},
                    "guided_refinement": {"status": "cleared", "outcome": "applied"},
                },
            },
            "source_class": "primary_filing",
            "skill_version": "2.0.0-agent-native",
            "service_version": "1.4.2",
            "mcp_version": "0.1.0",
        },
    }
    data.update(overrides)
    return data


def test_prose_lint_flags_seeded_fluffy_sample_and_passes_clean_sample():
    prose_lint = _load("prose_lint")
    fluffy = "\n".join(
        [
            "# Report",
            "It's important to note that this is a comprehensive overview of the company.",
            "I called the valuation tool and then I ran the workflow again.",
            "| Field | Value |",
            "| --- | --- |",
            "| Implied growth | Unavailable |",
            "| Implied margin | Unavailable |",
        ]
    )
    findings = prose_lint.lint_markdown(fluffy)
    rules = {finding["rule"] for finding in prose_lint.error_findings(findings)}
    assert "banned_phrase" in rules
    assert "process_narration" in rules
    assert "empty_table" in rules

    clean = "\n".join(
        [
            "# Report",
            "Launch revenue grew 33% in the latest filing year.",
            "| Driver | Value | Source |",
            "| --- | --- | --- |",
            "| revenue growth | 34.08 percent | anchor:base |",
        ]
    )
    assert prose_lint.error_findings(prose_lint.lint_markdown(clean)) == []


def test_report_builder_omits_market_implied_section_instead_of_unavailable_table(tmp_path):
    build_report = _load("build_report")
    # Data equivalent to the 2026-06-08 run: the service returned no
    # market-implied diagnostics.
    markdown = build_report.build_report_markdown(_report_data())

    assert "What The Price Would Need" not in markdown
    assert "Unavailable" not in markdown
    assert "## Valuation View" in markdown

    with_diagnostics = _report_data(
        market_implied_diagnostics={
            "rows": [{"assumption": "Implied revenue growth", "required_value": "41 percent", "note": "vs 34.08 base"}]
        }
    )
    markdown = build_report.build_report_markdown(with_diagnostics)
    assert "## What The Price Would Need" in markdown
    assert "Implied revenue growth" in markdown


def test_report_builder_audit_block_carries_gates_and_assumption_sources():
    build_report = _load("build_report")
    markdown = build_report.build_report_markdown(_report_data())

    assert "## Audit" in markdown
    assert "| Gate: evidence review | cleared approved |" in markdown
    assert "| Gate: guided refinement | cleared applied |" in markdown
    assert "| Source class | primary_filing |" in markdown
    assert "| Skill version | 2.0.0-agent-native |" in markdown
    assert "| Service version | 1.4.2 |" in markdown

    assert "## Key Assumptions" in markdown
    assert "| revenue growth | 34.08 percent | anchor:base |" in markdown
    assert "| sales to capital | 0.22 ratio | user_input |" in markdown
    assert "| terminal growth | 2.5 percent | service |" in markdown


def test_report_builder_renders_selected_anchor_explanation():
    build_report = _load("build_report")
    data = _report_data(
        key_assumptions=[
            {
                "driver": "target_operating_margin",
                "value": 8.95,
                "unit": "percent",
                "source": "anchor:base",
                "anchor_explanation": {
                    "summary": "These anchors use filing-based segment mix plus Damodaran industry quantiles.",
                    "weighted_anchors": {"low": -0.32, "base": 8.95, "high": 18.48},
                    "segment_rows": [
                        {
                            "segment": "Space",
                            "industry_group": "Aerospace/Defense",
                            "filing_weight_pct": 26.4,
                            "effective_anchor_weight_pct": 26.4,
                            "low": -4.44,
                            "base": 6.68,
                            "high": 13.39,
                        },
                        {
                            "segment": "Connectivity",
                            "industry_group": "Telecom. Services",
                            "filing_weight_pct": 73.6,
                            "effective_anchor_weight_pct": 73.6,
                            "low": 1.16,
                            "base": 9.76,
                            "high": 20.31,
                        },
                    ],
                },
            }
        ]
    )

    markdown = build_report.build_report_markdown(data)

    assert "filing-based segment mix plus Damodaran industry quantiles" in markdown
    assert "Space -> Aerospace/Defense" in markdown
    assert "Weighted anchors: low -0.32, base 8.95, high 18.48" in markdown


def test_report_builder_emits_single_no_advice_line_and_range_view():
    build_report = _load("build_report")
    data = _report_data(
        valuation={"range": {"low": 4.08, "high": 12.74, "unresolved_drivers": ["sales_to_capital"]}}
    )
    markdown = build_report.build_report_markdown(data)

    assert markdown.lower().count("not financial advice") == 1
    assert "4.08-12.74 USD" in markdown
    assert "sales to capital" in markdown
    headings = [line for line in markdown.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Valuation View",
        "## Business Story",
        "## Growth",
        "## Profitability",
        "## Reinvestment",
        "## Risk",
        "## Key Assumptions",
        "## Guided Judgment",
        "## Data Limits",
        "## Bottom Line",
        "## Sources",
        "## Audit",
    ]


def test_report_builder_refuses_to_render_on_prose_lint_errors(tmp_path):
    data = _report_data()
    data["prose"]["growth"] = "It is important to note that growth will delve into new markets."
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build_report.py"), "--out-dir", str(tmp_path / "out")],
        input=json.dumps(data),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    output = json.loads(result.stdout)
    assert output["ok"] is False
    assert output["reason"] == "prose_lint_errors"
    assert not (tmp_path / "out" / "index.html").exists()
    assert not (tmp_path / "out" / "report.md").exists()


def test_report_builder_writes_markdown_and_faithful_html(tmp_path):
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build_report.py"), "--out-dir", str(out_dir)],
        input=json.dumps(_report_data()),
        text=True,
        capture_output=True,
        check=True,
    )

    output = json.loads(result.stdout)
    assert output["ok"] is True
    markdown = (out_dir / "report.md").read_text(encoding="utf-8")
    html_text = (out_dir / "index.html").read_text(encoding="utf-8")
    assert output["browser_link"].startswith("file://")
    for heading in ("Valuation View", "Business Story", "Guided Judgment", "Bottom Line", "Audit"):
        assert f"## {heading}" in markdown or heading in markdown
        assert heading in html_text
    assert "anchor:base" in html_text
    assert "<table>" in html_text
    assert "4.07" in html_text


def test_no_stop_slop_reference_remains_in_skill_bundle():
    hits = [
        str(path)
        for path in bundled_skill_dir().rglob("*")
        if path.is_file()
        and path.suffix in {".md", ".py", ".json"}
        and "stop-slop" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert hits == []
