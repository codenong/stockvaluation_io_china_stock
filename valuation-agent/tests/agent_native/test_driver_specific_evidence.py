from valuation_agent.installer import bundled_skill_dir


REQUIRED_DRIVERS = {
    "revenue_growth",
    "operating_margin",
    "reinvestment_sales_to_capital",
    "risk_wacc",
    "terminal_value_mature_state",
    "accounting_adjustments",
}

REQUIRED_EVIDENCE_FIELDS = {
    "driver",
    "source_name",
    "source_url",
    "source_date",
    "evidence_summary",
    "direction",
    "confidence",
    "assumption_implication",
    "allowed_to_affect_autonomous_recalculation",
    "model_action",
}


def _reference(name: str) -> str:
    return (bundled_skill_dir() / "references" / name).read_text(encoding="utf-8")


def test_skill_references_driver_specific_evidence_workflow():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    lower = skill.lower()

    assert "driver-specific-evidence.md" in skill
    assert "using driver-specific evidence rather than generic source presence" in lower
    assert "generic source presence as evidence" in lower


def test_driver_specific_reference_defines_all_required_drivers_and_fields():
    text = _reference("driver-specific-evidence.md")
    lower = text.lower()

    for driver in REQUIRED_DRIVERS:
        assert f"`{driver}`" in text
    for field in REQUIRED_EVIDENCE_FIELDS:
        assert f"`{field}`" in text
    for required_value in [
        "supports higher assumption",
        "supports lower assumption",
        "neutral/mixed",
        "high",
        "medium",
        "low",
        "governed assumption change",
        "report explanation only",
        "explain/flag only unsupported",
    ]:
        assert required_value in lower


def test_generic_source_presence_is_explicitly_rejected_as_sufficient_evidence():
    evidence = _reference("driver-specific-evidence.md").lower()
    search = _reference("search-and-evidence.md").lower()
    judgment = _reference("assumption-judgment.md").lower()
    report_template = _reference("report-template.md").lower()

    for text in [evidence, search, judgment, report_template]:
        assert "generic source presence" in text
    for rejected_phrase in [
        "10-k found",
        "earnings release found",
        "sec filing source captured",
    ]:
        assert rejected_phrase in evidence
        assert rejected_phrase in search or rejected_phrase in report_template


def test_evidence_direction_confidence_and_implication_feed_assumption_judgment():
    judgment = _reference("assumption-judgment.md")
    lower = judgment.lower()

    assert '"direction"' in judgment
    assert '"confidence"' in judgment
    assert '"assumption_implication"' in judgment
    assert "evidence strength gate" in lower
    assert "`direction`, `confidence`, and `assumption_implication` are populated" in lower
    assert "keep the relevant assumption baseline/conservative" in lower


def test_only_governed_drivers_may_affect_autonomous_recalculation():
    evidence = _reference("driver-specific-evidence.md").lower()
    judgment = _reference("assumption-judgment.md").lower()
    mcp_reference = _reference("mcp-tools.md").lower()

    for governed in ["revenue growth", "operating margin", "sales-to-capital"]:
        assert governed in evidence
    assert "sector-level" in evidence
    for unsupported in [
        "do not autonomously change wacc",
        "do not autonomously change terminal growth",
        "do not autonomously change r&d capitalization",
        "do not autonomously change wacc, terminal growth, tax rate",
    ]:
        assert unsupported in evidence or unsupported in judgment or unsupported in mcp_reference
    assert "accounting adjustments" in mcp_reference
    assert "generic source presence is not evidence" in mcp_reference


def test_accounting_adjustments_are_explain_flag_only_unless_supported():
    evidence = _reference("driver-specific-evidence.md").lower()
    accounting = _reference("accounting-cleanup.md").lower()
    report_template = _reference("report-template.md").lower()

    assert "`accounting_adjustments`" in evidence
    assert "accounting evidence can improve interpretation" in evidence
    assert "explain/flag only" in evidence
    assert "r&d capitalization" in evidence
    assert "operating lease obligations" in evidence
    assert "stock-based compensation" in evidence
    assert "do not toggle r&d capitalization" in accounting
    assert "explain/flag only unless service-returned support exists" in report_template


def test_report_template_includes_driver_specific_evidence_handling():
    template = _reference("report-template.md")
    lower = template.lower()

    assert "driver-specific evidence" in lower
    assert "source date" in lower
    assert "| driver | evidence summary | source | source date | direction | confidence | assumption implication | model action |" in lower
    for report_label in [
        "revenue growth",
        "operating margin",
        "reinvestment / sales-to-capital",
        "risk / wacc",
        "terminal value / mature state",
        "accounting adjustments",
    ]:
        assert report_label in lower
    assert "do not count \"10-k found\"" in lower


def test_no_invention_rules_remain_intact_with_driver_evidence():
    search = _reference("search-and-evidence.md").lower()
    evidence = _reference("driver-specific-evidence.md").lower()
    template = _reference("report-template.md").lower()

    assert "do not cite search snippets as evidence" in search
    assert "do not invent facts, numbers, or quotes" in evidence
    assert "do not invent missing values" in template
    assert "if evidence is weak or missing" in template
