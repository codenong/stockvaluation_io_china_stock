"""M4: code-assembled report builder and deterministic prose linter."""

import io
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
            "investment_thesis": "The sample thesis is that launch demand can fund the satellite network without losing capital discipline.",
            "framing_questions": [
                "Can the launch business keep utilization high as satellite investment rises?",
                "Will recurring connectivity revenue improve mature margins?",
                "Does reinvestment efficiency improve enough to support the valuation?",
            ],
            "valuation_thesis": "The valuation thesis connects launch cadence, recurring connectivity revenue, reinvestment needs, and execution risk into one driver-led story.",
            "business_story": "The company sells launch services and satellite connectivity, with launch revenue funding the satellite build-out.",
            "growth": "Filing history shows revenue rising during the sample period; the base case assumes that pace fades as the company scales.",
            "profitability": "Only one filing year was operationally profitable; the target margin stays near that best reported year.",
            "reinvestment": "Capital spending exceeded revenue gains in the latest year, so each dollar of growth remains expensive.",
            "risk": "Launch cadence and satellite capacity pricing are the dominant company-specific risks.",
            "sensitivity_takeaway": "The grid should show whether value is driven more by growth, margins, or capital efficiency.",
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

    advice_like = "\n".join(
        [
            "# Report",
            "The gap to price makes this look like a buy.",
            "| Driver | Value | Source |",
            "| --- | --- | --- |",
            "| revenue growth | 34.08 percent | anchor:base |",
        ]
    )
    advice_findings = prose_lint.lint_markdown(advice_like)
    advice_rules = {finding["rule"] for finding in prose_lint.error_findings(advice_findings)}
    assert "prohibited_recommendation_language" in advice_rules

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
    assert "| revenue growth | 34.1% | anchor:base |" in markdown
    assert "| sales to capital | 0.22x | user_input |" in markdown
    assert "| terminal growth | 2.5% | service |" in markdown


def test_report_builder_renders_dcf_walk_bridge_and_terminal_without_scenario_cases():
    build_report = _load("build_report")
    markdown = build_report.build_report_markdown(
        _report_data(
            valuation_output={
                "projectionYears": 3,
                "companyDTO": {
                    "pvCFOverNext10Years": 1200.0,
                    "pvTerminalValue": 2800.0,
                    "valueOfOperatingAssets": 4000.0,
                    "cash": 500.0,
                    "debt": 800.0,
                    "valueOfEquity": 3700.0,
                    "numberOfShares": 100.0,
                    "estimatedValuePerShare": 37.0,
                    "price": 30.0,
                    "terminalCashFlow": 250.0,
                    "terminalValue": 3500.0,
                },
                "financialDTO": {
                    "revenues": [1000.0, 1100.0, 1210.0, 1331.0, 1364.0],
                    "revenueGrowthRate": [None, 10.0, 10.0, 10.0, 2.5],
                    "ebitOperatingMargin": [20.0, 22.0, 24.0, 25.0, 25.0],
                    "ebitOperatingIncome": [200.0, 242.0, 290.4, 332.75, 341.0],
                    "fcff": [None, 150.0, 180.0, 220.0, 230.0],
                    "pvFcff": [0.0, 140.0, 155.0, 175.0, 0.0],
                },
                "terminalValueDTO": {
                    "growthRate": 2.5,
                    "costOfCapital": 8.0,
                    "returnOnCapital": 12.0,
                    "reinvestmentRate": 20.0,
                },
            },
            scenario_book={
                "scenarios": [
                    {
                        "scenario_id": "base",
                        "label": "Base case",
                        "type": "user_refined_scenario",
                        "status": "completed",
                        "source": "guided_user_judgment",
                        "value_per_share": 37.0,
                    }
                ]
            },
        )
    )

    assert "## Projection Walk" in markdown
    assert "| Year 3 | $1,331.00 | 10.0% | 25.0% | $332.75 | $220.00 | $175.00 |" in markdown
    assert "## Valuation Bridge" in markdown
    assert "| PV terminal value | $2,800.00 |" in markdown
    assert "| Estimated value per share | $37.00 |" in markdown
    assert "## Terminal Value" in markdown
    assert "| Terminal return on capital | 12.0% |" in markdown
    assert "| PV terminal share of operating assets | 70.0% |" in markdown
    assert "## Scenario Cases" not in markdown
    assert "Unavailable" not in markdown


def test_report_builder_renders_service_driver_and_priced_in_expectation_tables():
    build_report = _load("build_report")
    markdown = build_report.build_report_markdown(
        _report_data(
            key_assumptions=[],
            valuation_output={
                "terminalValueDTO": {
                    "growthRate": 2.5,
                    "costOfCapital": 9.09,
                    "returnOnCapital": 9.09,
                },
                "assumptionTransparency": {
                    "operatingAssumptions": {
                        "revenueGrowthRateYears2To5": 17.33,
                        "operatingMarginNextYear": 33.0,
                        "targetOperatingMargin": 30.43,
                        "convergenceYearMargin": 10.0,
                        "salesToCapitalYears1To5": 3.55,
                        "salesToCapitalYears6To10": 1.77,
                        "revenueGrowthSource": "Valuation input baseline/override",
                        "operatingMarginSource": "Single-industry mechanical fallback",
                        "operatingMarginRationale": "Anchored to normalized company margin.",
                        "salesToCapitalSource": "Valuation input baseline/override",
                    },
                    "discountRate": {
                        "initialCostOfCapital": 10.05,
                        "initialCostOfCapitalSource": "Final FCFF output",
                        "equityRiskPremiumSource": "Configured ERP",
                        "costOfCapitalFormula": "Terminal WACC = risk-free rate + country ERP.",
                    },
                    "marketImpliedExpectations": {
                        "metrics": [
                            {
                                "label": "Operating Margin",
                                "unit": "percent",
                                "modelValue": 30.43,
                                "impliedValue": 36.37,
                                "gap": 5.94,
                                "note": "Solved to current market price.",
                            }
                        ]
                    },
                    "pricedInExpectations": {
                        "marketPrice": 358.16,
                        "method": "Deterministic market expectations grid.",
                        "baseCase": {
                            "intrinsicValue": 304.85,
                            "gapToMarket": -53.31,
                            "gapToMarketPct": -14.88,
                        },
                        "grid": [
                            {
                                "revenueGrowth": 12.33,
                                "operatingMargin": 30.43,
                                "intrinsicValue": 250.0,
                            },
                            {
                                "revenueGrowth": 17.33,
                                "operatingMargin": 30.43,
                                "intrinsicValue": 304.85,
                            },
                            {
                                "revenueGrowth": 12.33,
                                "operatingMargin": 35.43,
                                "intrinsicValue": 310.0,
                            },
                            {
                                "revenueGrowth": 17.33,
                                "operatingMargin": 35.43,
                                "intrinsicValue": 358.16,
                            },
                        ],
                        "frontier": [
                            {
                                "operatingMargin": 35.43,
                                "impliedRevenueGrowth": 17.38,
                                "intrinsicValue": 358.16,
                                "solved": True,
                                "note": "Interpolated.",
                            }
                        ],
                    },
                },
            },
        )
    )

    assert "## Model Driver Snapshot" in markdown
    assert "| Target operating margin | 30.4% | Single-industry mechanical fallback | Anchored to normalized company margin. |" in markdown
    assert "## What The Price Would Need" in markdown
    assert "| Operating Margin | 30.4% | 36.4% | 5.9% | Solved to current market price. |" in markdown
    assert "## Priced-In Expectations" in markdown
    assert "Base case value is $304.85 versus market price $358.16. Gap to market is -$53.31 (-14.9%)." in markdown
    assert "| 35.4% | 17.4% | $358.16 | Solved | Interpolated. |" in markdown
    assert "## Sensitivity Analysis" in markdown
    assert "| Operating margin \\ Revenue growth | 12.3% | 17.3% |" in markdown
    assert "| 30.4% | $250.00 | $304.85 |" in markdown
    assert "| 35.4% | $310.00 | $358.16 |" in markdown
    assert "Unavailable" not in markdown


def test_html_renderer_builds_report_packet_from_structured_data():
    build_report = _load("build_report")
    renderer = _load("render_report_html")
    data = _report_data(
        valuation={"point": {"value_per_share": 37.0}},
        valuation_output={
            "companyDTO": {
                "price": 30.0,
                "priceAsPercentageOfValue": -18.92,
                "valueOfEquity": 3700.0,
                "pvCFOverNext10Years": 1200.0,
                "pvTerminalValue": 2800.0,
                "cash": 500.0,
                "debt": 800.0,
            },
            "financialDTO": {
                "revenues": [1000.0, 1100.0, 1210.0, 1331.0],
                "ebitOperatingMargin": [20.0, 22.0, 24.0, 25.0],
                "fcff": [None, 150.0, 180.0, 220.0],
            },
            "assumptionTransparency": {
                "pricedInExpectations": {
                    "marketPrice": 30.0,
                    "baseCase": {"intrinsicValue": 37.0, "gapToMarketPct": -18.92},
                    "frontier": [
                        {
                            "operatingMargin": 25.0,
                            "impliedRevenueGrowth": 9.0,
                            "solved": True,
                        }
                    ],
                }
            },
        }
    )
    markdown = build_report.build_report_markdown(data)
    html_text = renderer.build_html(
        markdown,
        "Space Exploration Technologies Valuation Report",
        "Space Exploration Technologies",
        "SPCX",
        "2026-06-13 12:00 UTC",
        report_data=data,
    )

    assert 'class="report-brief"' in html_text
    assert 'class="market-panel"' in html_text
    assert 'class="driver-grid"' in html_text
    assert 'class="visual-grid"' in html_text
    assert "$37.00" in html_text
    assert "25.0%" in html_text
    assert "margin needs about" in html_text
    assert "Valuation bridge" in html_text


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
    assert "$4.08-$12.74" in markdown
    assert "sales to capital" in markdown
    headings = [line for line in markdown.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Valuation View",
        "## Investment Thesis",
        "## Framing Questions",
        "## Valuation Thesis",
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


def test_report_builder_refuses_model_prose_numbers_not_in_structured_data(tmp_path):
    data = _report_data()
    data["prose"]["investment_thesis"] = "The thesis requires 99.9% growth, which is not in the structured data."
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build_report.py"), "--out-dir", str(tmp_path / "out")],
        input=json.dumps(data),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    output = json.loads(result.stdout)
    assert output["ok"] is False
    assert output["reason"] == "prose_number_errors"
    assert output["findings"] == [{"field": "prose.investment_thesis", "number": "99.9%"}]
    assert not (tmp_path / "out" / "index.html").exists()
    assert not (tmp_path / "out" / "report.md").exists()


def test_report_builder_refuses_segment_economics_prose_when_segment_basis_is_insufficient(tmp_path):
    data = _report_data(
        valuation_output={
            "assumptionTransparency": {
                "baselineUseStatus": "segment_evidence_insufficient",
                "segmentAware": False,
                "segmentCount": 0,
                "unsupportedBaselineDrivers": [
                    {
                        "field": "segments",
                        "status": "segment_evidence_insufficient",
                        "reason": "Researched baseline mode did not receive a validated segment package.",
                    }
                ],
            }
        },
    )
    data["prose"]["profitability"] = "AWS economics can carry the consolidated profit story."

    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build_report.py"), "--out-dir", str(tmp_path / "out")],
        input=json.dumps(data),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    output = json.loads(result.stdout)
    assert output["ok"] is False
    assert output["reason"] == "prose_basis_errors"
    assert output["findings"] == [
        {
            "field": "prose.profitability",
            "claim": "amazon_business_line",
            "basis": "segment_evidence_insufficient",
        }
    ]
    assert not (tmp_path / "out" / "index.html").exists()
    assert not (tmp_path / "out" / "report.md").exists()


def test_report_builder_refuses_to_render_advice_like_language(tmp_path):
    data = _report_data()
    data["prose"]["bottom_line"] = "The discount to price makes this look like a buy."
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
    rules = {finding["rule"] for finding in output["findings"]}
    assert "prohibited_recommendation_language" in rules
    assert not (tmp_path / "out" / "index.html").exists()
    assert not (tmp_path / "out" / "report.md").exists()


def test_report_builder_writes_markdown_and_faithful_html(tmp_path):
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build_report.py"), "--out-dir", str(out_dir), "--no-open"],
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
    assert output["browser_opened"] is False
    for heading in ("Valuation View", "Investment Thesis", "Framing Questions", "Business Story", "Guided Judgment", "Bottom Line", "Audit"):
        assert f"## {heading}" in markdown or heading in markdown
        assert heading in html_text
    assert 'class="report-brief"' in html_text
    assert 'class="driver-grid"' in html_text
    assert "anchor:base" in html_text
    assert "<table>" in html_text
    assert "$4.07" in html_text


def test_report_builder_opens_html_report_by_default(monkeypatch, tmp_path, capsys):
    build_report = _load("build_report")
    opened_urls = []
    monkeypatch.setattr(build_report.webbrowser, "open_new_tab", lambda url: opened_urls.append(url) or True)
    monkeypatch.setattr(sys, "argv", ["build_report.py", "--out-dir", str(tmp_path / "out")])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_report_data())))

    assert build_report.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["browser_opened"] is True
    assert opened_urls == [output["browser_link"]]


def test_swatma_report_spine_has_case_status_weak_basis_and_monitor_list():
    build_report = _load("build_report")
    data = _report_data(
        case_status="evidence_constrained_base",
        valuation={"point": {"value_per_share": 304.85}},
        market_price=358.16,
        prose={
            **_report_data()["prose"],
            "investment_thesis": "The thesis works only if cloud mix lifts margin while retail reinvestment remains disciplined.",
            "framing_questions": [
                {
                    "question": "Can cloud growth lift consolidated margin without hiding retail capital intensity?",
                    "driver": "margin",
                    "context": "This maps the story directly to the target margin and sales-to-capital assumptions.",
                },
                {
                    "question": "Can advertising and marketplace fees grow without requiring the same asset base as first-party retail?",
                    "driver": "growth",
                    "context": "This frames the revenue path against business mix.",
                },
                {
                    "question": "Does cash conversion improve enough to fund growth after lease and fulfillment spending?",
                    "driver": "reinvestment",
                    "context": "This maps the thesis to capital efficiency.",
                },
            ],
            "valuation_thesis": "The valuation thesis connects business mix, price pressure, growth, margin, reinvestment, risk, and terminal value into one owner-style memo.",
            "terminal_value": "Terminal value depends on mature reinvestment discipline and a stable spread between return on capital and cost of capital.",
            "what_would_change_the_view": [
                "Cloud revenue growth slowing while consolidated margin stops improving.",
                "Fulfillment capital spending rising faster than revenue for several reporting periods.",
                "A higher cost of capital that compresses terminal value despite better operating margins.",
            ],
        },
        weak_basis_warnings=[
            "Segment mapping is directional, so the value should be read as an evidence-constrained base case."
        ],
        valuation_output={
            "companyDTO": {
                "price": 358.16,
                "estimatedValuePerShare": 304.85,
                "priceAsPercentageOfValue": 117.49,
            },
            "assumptionTransparency": {
                "pricedInExpectations": {
                    "marketPrice": 358.16,
                    "method": "Deterministic market expectations grid.",
                    "baseCase": {
                        "intrinsicValue": 304.85,
                        "gapToMarket": -53.31,
                        "gapToMarketPct": -14.88,
                    },
                    "grid": [
                        {"revenueGrowth": 12.33, "operatingMargin": 30.43, "intrinsicValue": 250.0},
                        {"revenueGrowth": 17.33, "operatingMargin": 30.43, "intrinsicValue": 304.85},
                    ],
                }
            },
        },
    )

    markdown = build_report.build_report_markdown(data)

    for heading in (
        "## Valuation View",
        "## Investment Thesis",
        "## Framing Questions",
        "## Valuation Thesis",
        "## Terminal Value",
        "## What The Price Would Need",
        "## Priced-In Expectations",
        "## Sensitivity Analysis",
        "## Basis Warnings",
        "## Data Limits",
        "## What Would Change The View",
        "## Sources",
        "## Audit",
    ):
        assert heading in markdown
    assert "Case status: **Evidence constrained base**." in markdown
    assert "Market price: **$358.16**." in markdown
    assert "Can cloud growth lift consolidated margin" in markdown
    assert "(margin)" in markdown
    assert "Segment mapping is directional" in markdown
    assert markdown.index("## Basis Warnings") < markdown.index("## Audit")
    assert "## Peer Comparison" not in markdown
    assert "## Scenario Cases" not in markdown
    assert "target price" not in markdown.lower()


def test_swatma_number_formatting_and_report_data_artifact(tmp_path):
    build_report = _load("build_report")
    out_dir = tmp_path / "out"
    data = _report_data(
        valuation={"point": {"value_per_share": 12.345}},
        market_price=9.1,
        key_assumptions=[
            {"driver": "large_money", "value": 1_920_000_000_000, "unit": "money", "source": "service"},
            {"driver": "negative_money", "value": -422_500_000_000, "unit": "money", "source": "service"},
            {"driver": "target_margin", "value": 30.43, "unit": "percent", "source": "anchor:base"},
            {"driver": "sales_to_capital", "value": 3.55, "unit": "multiple", "source": "anchor:base"},
        ],
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build_report.py"), "--out-dir", str(out_dir), "--no-open"],
        input=json.dumps(data),
        text=True,
        capture_output=True,
        check=True,
    )

    output = json.loads(result.stdout)
    markdown = (out_dir / "report.md").read_text(encoding="utf-8")
    assert output["report_data"] == str(out_dir / "report_data.json")
    assert (out_dir / "report_data.json").stat().st_size > 0
    assert "$12.35" in markdown
    assert "$9.10" in markdown
    assert "$1.92T" in markdown
    assert "-$422.5B" in markdown
    assert "30.4%" in markdown
    assert "3.55x" in markdown


def test_html_renderer_swatma_structure_chart_labels_and_heatmap():
    build_report = _load("build_report")
    renderer = _load("render_report_html")
    data = _report_data(
        case_status="user_refined_scenario",
        valuation={"point": {"value_per_share": 37.0}},
        valuation_output={
            "projectionYears": 3,
            "companyDTO": {
                "price": 30.0,
                "priceAsPercentageOfValue": -18.92,
                "valueOfEquity": 3700.0,
                "pvCFOverNext10Years": 1200.0,
                "pvTerminalValue": 2800.0,
                "valueOfOperatingAssets": 4000.0,
                "cash": 500.0,
                "debt": 800.0,
                "estimatedValuePerShare": 37.0,
            },
            "financialDTO": {
                "revenues": [1000.0, 1100.0, 1210.0, 1331.0],
                "revenueGrowthRate": [None, 10.0, 10.0, 10.0],
                "ebitOperatingMargin": [20.0, 22.0, 24.0, 25.0],
                "fcff": [None, 150.0, 180.0, 220.0],
            },
            "assumptionTransparency": {
                "pricedInExpectations": {
                    "marketPrice": 30.0,
                    "method": "Deterministic market expectations grid.",
                    "baseCase": {"intrinsicValue": 37.0, "gapToMarketPct": -18.92},
                    "grid": [
                        {"revenueGrowth": 8.0, "operatingMargin": 20.0, "intrinsicValue": 24.0},
                        {"revenueGrowth": 10.0, "operatingMargin": 20.0, "intrinsicValue": 29.0},
                        {"revenueGrowth": 8.0, "operatingMargin": 25.0, "intrinsicValue": 32.0},
                        {"revenueGrowth": 10.0, "operatingMargin": 25.0, "intrinsicValue": 37.0},
                    ],
                    "frontier": [
                        {
                            "operatingMargin": 25.0,
                            "impliedRevenueGrowth": 9.0,
                            "intrinsicValue": 30.0,
                            "solved": True,
                        }
                    ],
                }
            },
        },
    )
    markdown = build_report.build_report_markdown(data)
    html_text = renderer.build_html(
        markdown,
        "Space Exploration Technologies Valuation Report",
        "Space Exploration Technologies",
        "SPCX",
        "2026-06-13 12:00 UTC",
        report_data=data,
    )

    for expected in (
        'class="value-card',
        'class="framing-question-grid"',
        'class="legacy-metric-grid"',
        'class="chart-card"',
        'class="chart-title">Revenue path',
        'class="chart-unit">USD millions',
        'class="chart-title">Operating margin',
        'class="chart-unit">Percent',
        'class="chart-takeaway"',
        'class="sensitivity-heatmap"',
        "Year 1",
        "Operating margin",
        "Revenue growth",
        "#20DF7F",
        "font-family: Nunito",
        "Educational analysis only",
    ):
        assert expected in html_text
    assert 'class="num"' in html_text
    assert "Peer Comparison" not in html_text
    assert "Scenario Cases" not in html_text


def test_no_stop_slop_reference_remains_in_skill_bundle():
    hits = [
        str(path)
        for path in bundled_skill_dir().rglob("*")
        if path.is_file()
        and path.suffix in {".md", ".py", ".json"}
        and "stop-slop" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert hits == []
