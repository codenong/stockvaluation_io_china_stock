from pathlib import Path

from valuation_agent.installer import AgentInstaller, bundled_skill_dir


REQUIRED_GUIDES = {
    "damodaran-coverage-map.md",
    "damodaran-source-map.md",
    "driver-specific-evidence.md",
    "baseline-plausibility.md",
    "guided-valuation-refinement.md",
    "rd-capitalization-decision.md",
    "growth-reinvestment-discipline.md",
    "terminal-value-discipline.md",
    "model-selection-and-lifecycle.md",
    "narrative-report-style.md",
    "risk-currency-country.md",
    "accounting-cleanup.md",
    "options-leases-other-claims.md",
    "segment-quality.md",
    "special-company-stop-rules.md",
}

REQUIRED_COVERAGE_TOPICS = [
    "Model choice",
    "Business lifecycle",
    "Revenue growth",
    "Margins",
    "Reinvestment",
    "Terminal value",
    "Risk and discount rates",
    "Accounting cleanup",
    "Taxes and NOLs",
    "Options and other claims",
    "Segment valuation",
    "Special companies",
    "Relative valuation",
    "Acquisitions and value enhancement",
    "Real options",
    "Story-to-numbers discipline",
]

SUPPORT_STATES = {
    "supported_adjustment",
    "supported_explanation",
    "explain_only",
    "future_support",
    "unsupported_stop",
    "out_of_scope",
}


def _read_reference(name: str) -> str:
    return (bundled_skill_dir() / "references" / name).read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.index(marker)
    next_start = text.find("\n## ", start + len(marker))
    return text[start:] if next_start == -1 else text[start:next_start]


def test_damodaran_reference_set_exists():
    references = bundled_skill_dir() / "references"

    assert REQUIRED_GUIDES.issubset({path.name for path in references.iterdir()})


def test_coverage_map_has_required_topics_support_states_and_qa_fields():
    text = _read_reference("damodaran-coverage-map.md")

    for topic in REQUIRED_COVERAGE_TOPICS:
        assert f"## {topic}" in text
        section = _section(text, topic)
        section_lower = section.lower()
        for required_field in [
            "Damodaran source:",
            "Current product support state:",
            "User-agent allowed action:",
            "Evidence required:",
            "Report guidance:",
            "QA expectation:",
        ]:
            assert required_field in section
        assert any(state in section_lower for state in SUPPORT_STATES)
    for state in SUPPORT_STATES:
        assert state in text


def test_source_map_links_damodaran_sources_and_product_contracts():
    source_map = _read_reference("damodaran-source-map.md")

    assert "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html" in source_map
    assert "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm" in source_map
    assert "valuation-agent/mcp_tools.py" in source_map
    assert "FinancialDataInput.java" in source_map
    for state in SUPPORT_STATES:
        assert state in source_map


def test_decision_guides_have_allowed_action_and_do_not_sections():
    for name in REQUIRED_GUIDES - {
        "damodaran-coverage-map.md",
        "damodaran-source-map.md",
        "narrative-report-style.md",
        "baseline-plausibility.md",
    }:
        text = _read_reference(name).lower()
        assert "## allowed action" in text
        assert "## do not" in text
        assert "hand-compute dcf" not in text


def test_guides_preserve_current_autonomous_adjustment_boundary():
    rd = _read_reference("rd-capitalization-decision.md").lower()
    terminal = _read_reference("terminal-value-discipline.md").lower()
    risk = _read_reference("risk-currency-country.md").lower()
    model = _read_reference("model-selection-and-lifecycle.md").lower()
    accounting = _read_reference("accounting-cleanup.md").lower()

    assert "explain/flag only" in rd
    assert "do not send r&d" in rd
    assert "do not autonomously change terminal growth" in terminal
    assert "do not autonomously change wacc" in risk
    assert "financial firms" in model and "stop" in model
    assert "do not autonomously normalize one-time charges" in accounting


def test_narrative_style_preserves_story_and_numbers_shape():
    narrative = _read_reference("narrative-report-style.md").lower()

    assert "combine story and numbers" in narrative
    for section in ["growth", "margins", "investment_efficiency", "risks", "key_takeaways"]:
        assert f'"{section}"' in narrative
    for phrase in [
        "setup -> tension -> insight -> resolution",
        "market-implied",
        "priced-in",
        "publication-quality",
        "never hype",
    ]:
        assert phrase in narrative


def test_report_template_requires_rich_damodaran_data_displays_without_invention():
    template = _read_reference("report-template.md")
    lower = template.lower()

    for phrase in [
        "central narrative tension",
        "valuation snapshot",
        "mechanical baseline vs evidence-constrained base vs market-implied",
        "guided user judgment and user-refined scenario",
        "user answers define a scenario; they are not independent evidence",
        "market-implied expectations",
        "break-even / priced-in frontier",
        "scenario headline table",
        "sensitivity analysis",
        "terminal value and cash-flow composition",
        "evidence and segment summary",
        "supported vs explain-only",
        "do not invent",
        "marketimpliedexpectations",
        "pricedinexpectations.frontier",
        "pricedinexpectations.scenarios",
    ]:
        assert phrase in lower


def test_report_template_preserves_required_section_order():
    template = _read_reference("report-template.md")
    ordered_headings = [
        "## Educational-Use Framing",
        "## Valuation Snapshot",
        "## Central Narrative Tension",
        "## Growth",
        "## Margins",
        "## Investment Efficiency",
        "## Risk",
        "## Market-Implied Expectations",
        "## Break-Even / Priced-In Frontier",
        "## Scenario Headline Table",
        "## Sensitivity Analysis",
        "## Mechanical Baseline Vs Evidence-Constrained Base Vs Market-Implied",
        "## Guided User Judgment And User-Refined Scenario",
        "## Evidence And Segment Summary",
        "## Assumption Judgment Summary",
        "## Terminal Value And Cash-Flow Composition",
        "## Tax And Accounting Adjustments",
        "## Effective Assumptions",
        "## Data Quality And Limitations",
        "## Key Takeaways",
    ]

    positions = [template.index(heading) for heading in ordered_headings]
    assert positions == sorted(positions)


def test_report_template_has_explicit_no_invention_rules_for_absent_service_fields():
    template = _read_reference("report-template.md")

    required_rules = [
        "If `marketImpliedExpectations` is absent, say it is unavailable rather than recreating it.",
        "Do not hand-create a break-even table if `pricedInExpectations.frontier` is absent.",
        "If sensitivity data is absent, explain the most sensitive assumptions qualitatively instead of inventing values.",
        "If these fields are absent, say the composition is unavailable.",
    ]
    for rule in required_rules:
        assert rule in template


def test_market_expectation_guidance_stays_report_only_not_model_changes():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    checks = _read_reference("assumption-checks.md")
    mcp_reference = _read_reference("mcp-tools.md")

    assert "Treat `marketImpliedExpectations`, `pricedInExpectations`, frontier, grid, and scenario data as report inputs, not autonomous model changes." in skill
    assert "Use `marketImpliedExpectations` and `pricedInExpectations` as report inputs when returned." in checks
    assert "Use these fields as report inputs, not autonomous model changes." in mcp_reference


def test_guided_refinement_is_default_with_quick_bypass_and_bounded_questions():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    guide = _read_reference("guided-valuation-refinement.md").lower()

    assert "guided-valuation-refinement.md" in skill
    assert "unless the user explicitly requested quick valuation, no questions, skip questions, one-shot report, automation, or smoke-test" in skill
    assert "do not treat a plain \"value company using stockvaluation.io\" request as a one-shot path" in skill
    assert "generate 4-6 bounded company-specific valuation questions by default" in skill
    assert "at most 8 in deep mode" in skill
    assert skill.index("baseline-plausibility.md") < skill.index("guided-valuation-refinement.md")
    assert "quick valuation, no-questions, automation, smoke-test" in guide
    assert "bypass guided refinement" in guide


def test_guided_question_reference_requires_company_specific_auditable_shape():
    guide = _read_reference("guided-valuation-refinement.md")
    lower = guide.lower()

    for field in [
        '"driver"',
        '"company_specific_rationale"',
        '"baseline_assumption"',
        '"evidence_summary"',
        '"bounded_choices"',
        '"recommended_answer"',
        '"choice_label"',
        '"model_action"',
        '"override_candidate"',
        '"mapping_notes"',
    ]:
        assert field in guide
    assert "reject generic checklist questions" in lower
    assert "recommended bounded answer" in lower
    assert "not financial advice" in lower
    assert "recommended:" in lower
    assert "user answers are user judgment, not external evidence" in lower
    assert '"source_type": "user_judgment"' in guide
    assert "not independent evidence" in guide


def test_guided_refinement_preserves_market_implied_report_only_boundary():
    guide = _read_reference("guided-valuation-refinement.md").lower()
    report = _read_reference("report-template.md").lower()

    assert "market-implied diagnostics are report-only and never evidence" in guide
    assert "do not ask what value the user wants" in guide
    assert "direct valuation outputs" in guide
    assert "user-refined scenario" in report
    assert "market-implied diagnostics" in report
    assert "do not call user answers evidence" in report


def test_mcp_reference_documents_reportable_market_expectation_fields():
    mcp_reference = _read_reference("mcp-tools.md")

    assert "marketImpliedExpectations" in mcp_reference
    assert "pricedInExpectations" in mcp_reference
    assert "pricedInExpectations.frontier" in mcp_reference
    assert "pricedInExpectations.scenarios" in mcp_reference
    assert "report inputs, not autonomous model changes" in mcp_reference


def test_installer_copies_damodaran_references(tmp_path: Path):
    home = tmp_path / "home"
    installer = AgentInstaller(home=home)

    installer.install_skills(["codex"])

    installed_references = home / ".codex" / "skills" / "stockvaluation-io" / "references"
    assert (installed_references / "damodaran-coverage-map.md").exists()
    assert (installed_references / "narrative-report-style.md").exists()
