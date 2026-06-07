import json
from pathlib import Path

from valuation_agent.installer import AgentInstaller, bundled_skill_dir


REQUIRED_GUIDES = {
    "damodaran-coverage-map.md",
    "damodaran-source-map.md",
    "driver-specific-evidence.md",
    "evidence-review-gate.md",
    "baseline-plausibility.md",
    "scenario-book.md",
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
    "financial-field-definitions.md",
    "prospectus-mode.md",
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


def test_financial_field_definition_reference_mirrors_service_contract():
    repo_root = Path(__file__).parents[3]
    service_contract = json.loads(
        (repo_root / "valuation-service/src/main/resources/data/financial_field_definitions.json")
        .read_text(encoding="utf-8")
    )
    reference = _read_reference("financial-field-definitions.md")

    assert "valuation-service/src/main/resources/data/financial_field_definitions.json" in reference
    assert "SEC and Yahoo are adapters into the same StockValuation financial schema" in reference
    for field in service_contract["fields"]:
        assert f"`{field['fieldName']}`" in reference


def test_skill_docs_describe_researched_baseline_source_gate_and_field_contract():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    mcp = _read_reference("mcp-tools.md")
    template = _read_reference("report-template.md")

    for text in [skill, mcp, template]:
        assert "stockvaluation.researched_baseline" in text
        assert "sourceQualityGate" in text
        assert "sec_http_error_yahoo_fallback" in text
        assert "primary_adapter_not_supported_yahoo_normalized" in text
        assert "financial-field-definitions.md" in text
    assert "Keep `stockvaluation.value_ticker` mechanical" in skill
    assert "Do not look for or request a high-level researched valuation tool." not in skill


def test_source_quality_gate_docs_force_explicit_user_choice():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    gate = _read_reference("evidence-review-gate.md")
    mcp = _read_reference("mcp-tools.md")
    combined = "\n".join([skill, gate, mcp]).lower()

    assert "sec primary source was expected but unavailable" in combined
    assert "continue with yahoo-normalized fallback" in combined
    assert "retry the primary source" in combined
    assert "no supported deterministic primary-filing adapter covers this listing" in combined
    assert "continue after company-report cross-check" in combined
    assert "do not present a generic `approve` prompt as sufficient" in combined


def test_skill_docs_describe_prospectus_mode_review_gate_and_price_basis():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    mcp = _read_reference("mcp-tools.md")
    template = _read_reference("report-template.md")
    prospectus = _read_reference("prospectus-mode.md")

    for text in [skill, mcp, template, prospectus]:
        assert "stockvaluation.extract_prospectus" in text
        assert "stockvaluation.value_prospectus" in text
        assert "prospectus_extraction_review_required" in text
        assert "offering_price" in text
        assert "sec-edgar-prospectus" in text
        assert "primary_filing" in text
        assert "not financial advice" in text.lower()
    assert "raw HTML" in mcp
    assert "reviewStatus" in prospectus
    assert "reviewed" in prospectus


def test_prospectus_mode_review_gate_is_contextual_and_does_not_skip_guided_flow():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    mcp = _read_reference("mcp-tools.md").lower()
    prospectus = _read_reference("prospectus-mode.md").lower()
    combined = "\n".join([skill, mcp, prospectus])

    for phrase in [
        "do not show the user only a bare list of allowed actions",
        "show a compact review card",
        "recommended next action",
        "numbered human choices",
        "1. approve and continue",
        "2. correct the packet",
        "3. add sources",
        "4. stop",
        "map the user's number to the internal action",
        "do not ask humans to type internal action names",
        "choose `approve_extracted_packet` only when",
        "empty packet",
        "prospectus extraction review is not the evidence review gate",
        "does not replace guided valuation refinement",
        "continue into the normal researched workflow",
        "evidence-review-gate.md",
        "guided-valuation-refinement.md",
    ]:
        assert phrase in combined

    assert skill.index("prospectus-mode.md") < skill.index("evidence-review-gate.md")
    assert skill.index("stockvaluation.value_prospectus") < skill.index("report-template.md")


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


def test_narrative_style_is_subordinate_to_canonical_report_template():
    narrative = _read_reference("narrative-report-style.md").lower()

    assert "combine story and numbers" in narrative
    assert "subordinate to `report-template.md`" in narrative
    assert "report-template.md controls the final report structure" in narrative
    assert "does not control section order" in narrative
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
        "canonical controlling structure",
        "narrative-report-style.md is subordinate",
        "do not use the older loose story-and-numbers shape",
        "final report rendering contract",
        "must render the required report-template headings in order",
        "a final answer that starts with a sentence such as \"using stockvaluation.io",
        "\"key assumptions\", \"main caveats\", and \"sources used\" is not template-compliant",
        "investor-reader",
        "one concise no-advice line",
        "do not use visible default headings",
        "do not show the internal mechanical model value",
        "diagnostic scenarios stay diagnostic",
        "do not blend the main scenario with a diagnostic no-segment run",
        "business story",
        "valuation view",
        "user-refined scenario is the main scenario",
        "evidence review status",
        "internal baseline audit",
        "explicit audit/debug",
        "guided judgment",
        "user answers define a scenario; they are not independent evidence",
        "what the price would need",
        "break-even / priced-in frontier",
        "scenario headline table",
        "scenario book",
        "sensitivity analysis",
        "terminal value and cash-flow composition",
        "evidence and segment detail",
        "source confidence",
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
        "## How To Read This",
        "## Internal Valuation Metadata (Debug Only)",
        "## Scenario Metadata (Debug Only)",
        "## Valuation View",
        "## What Was Reviewed",
        "## Source Confidence",
        "## Business Story",
        "## Growth",
        "## Profitability",
        "## Reinvestment Needs",
        "## Risk",
        "## What The Price Would Need",
        "## Key Assumptions",
        "## Data Limits",
        "## Bottom Line",
        "## Sources",
        "## Break-Even / Priced-In Frontier",
        "## Scenario Headline Table",
        "## Sensitivity Analysis",
        "## Guided Judgment",
        "## Evidence And Segment Detail",
        "## Assumption Support",
        "## Internal Baseline Audit",
        "## Terminal Value And Cash-Flow Composition",
        "## Tax And Accounting Adjustments",
        "## Effective Assumptions",
    ]

    positions = [template.index(heading) for heading in ordered_headings]
    assert positions == sorted(positions)


def test_skill_report_rules_reject_compressed_memo_and_diagnostic_ranges():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()

    for phrase in [
        "render the final report with the report-template headings",
        "do not replace the template with a compressed memo",
        "using stockvaluation.io",
        "key assumptions",
        "main caveats",
        "sources used",
        "keep diagnostic scenarios diagnostic",
        "do not blend a user-refined scenario with a diagnostic no-segment",
    ]:
        assert phrase in skill


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


def test_report_template_requires_accounting_and_claims_status_labels():
    template = _read_reference("report-template.md").lower()
    accounting = _read_reference("accounting-cleanup.md").lower()
    rd = _read_reference("rd-capitalization-decision.md").lower()
    claims = _read_reference("options-leases-other-claims.md").lower()

    for phrase in [
        "accountingandclaims",
        "supported versus report-only accounting labels",
        "zero_by_default",
        "source_required",
        "stale",
        "reconciled",
        "conflict",
        "governed_scenario_supported",
        "do not infer accounting support from a numeric zero",
        "do not invent accounting adjustments",
        "sbc percent of revenue",
        "diluted share-count trend",
    ]:
        assert phrase in template

    assert "accountingandclaims" in accounting
    assert "sbc percent of revenue" in accounting
    assert "returned, missing, stale, reconciled, conflict, or source_required" in accounting
    assert "governed accounting scenario" in rd
    assert "multi-year r&d history" in rd
    assert "service boundary must also receive the amortization method" in rd
    assert "source provenance" in rd
    assert "zero_by_default" in claims
    assert "leases are report-only in phase 5" in claims
    assert "direct claim value overrides remain blocked" in claims


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
    assert "evidence-review-gate.md" in skill
    assert "unless the user explicitly requested quick valuation, no questions, skip questions, one-shot report, automation, or smoke-test" in skill
    assert "do not treat a plain \"value company using stockvaluation.io\" request as a one-shot path" in skill
    assert "build a hidden guided question plan" in skill
    assert "treat the returned guided-question plan as the source of truth" in skill
    assert "stockvaluation.apply_guided_answers" in skill
    assert "do not finish with a report-only final report" in skill
    assert "candidate_values_required" in skill
    assert "materiality-driven" in skill
    assert "hard cap of 15" in skill
    assert "ask one question at a time" in skill
    assert "do not ask a batch of 4-6 questions" in skill
    assert "at most 8 in deep mode" not in skill
    assert "fixed 3-question" not in skill
    assert skill.index("evidence-review-gate.md") < skill.index("guided-valuation-refinement.md")
    assert "quick valuation, no-questions, automation, smoke-test" in guide
    assert "bypass guided refinement" in guide
    assert "hard cap of 15 visible guided questions" in guide
    assert "no forced minimum" in guide
    assert "at most 8 in deep mode" not in guide


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
    assert "modeling default" in lower
    assert "my analysis" in lower
    assert "why this default" in lower
    assert "evidence used" in lower
    assert "business impact" in lower
    assert "model impact" in lower
    assert "not financial advice" in lower
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


def test_prospectus_guided_defaults_do_not_claim_recalculated_user_refined_value():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    prospectus = _read_reference("prospectus-mode.md").lower()
    guide = _read_reference("guided-valuation-refinement.md").lower()
    report = _read_reference("report-template.md").lower()
    combined = "\n".join([skill, prospectus, guide, report])

    for phrase in [
        "deterministic explicit scenarios",
        "service extracts raw prospectus segment candidate tables and rows",
        "does not choose segment rows",
        "segment candidate tables",
        "hard-code segment-to-industry mapping",
        "use the agent's search tools",
        "scenario.segments",
        "do not ask the user to provide vague \"segment mappings\"",
        "ask the actual story-to-numbers question",
        "show source-backed default choices",
        "do not leave the business-definition or segment-mix story as report-only by default",
        "stockvaluation.apply_guided_answers",
        "supported `prospectusscenariocandidate`",
        "candidate_values_required",
        "all remaining default answers must be summarized",
        "do not skip hidden questions silently",
        "sec filing facts are primary",
        "external news is report-only",
        "external news must not override filing facts",
    ]:
        assert phrase in combined


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
    assert (installed_references / "evidence-review-gate.md").exists()
