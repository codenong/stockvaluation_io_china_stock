"""Driver-specific evidence discipline (now in evidence-and-judgment.md)."""

from valuation_agent.installer import bundled_skill_dir


def _reference(name: str) -> str:
    return (bundled_skill_dir() / "references" / name).read_text(encoding="utf-8")


def test_skill_references_driver_specific_evidence_workflow():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "evidence-and-judgment.md" in skill
    assert "classify driver-specific evidence" in skill


def test_evidence_reference_defines_all_required_drivers_and_fields():
    evidence = _reference("evidence-and-judgment.md")
    for driver in [
        "`revenue_growth`",
        "`operating_margin`",
        "`reinvestment_sales_to_capital`",
        "`risk_wacc`",
        "`terminal_value_mature_state`",
        "`accounting_adjustments`",
    ]:
        assert driver in evidence
    for field in [
        "`source_url`",
        "`source_date`",
        "`evidence_summary`",
        "`direction`",
        "`confidence`",
        "`assumption_implication`",
        "`allowed_to_affect_autonomous_recalculation`",
        "`model_action`",
    ]:
        assert field in evidence


def test_generic_source_presence_is_explicitly_rejected_as_sufficient_evidence():
    evidence = _reference("evidence-and-judgment.md").lower()
    assert "generic source presence is not evidence" in evidence
    for rejected_phrase in ["10-k found", "earnings release found", "sec filing source captured"]:
        assert rejected_phrase in evidence
    assert "names the driver and the relevant fact" in evidence


def test_only_governed_drivers_may_affect_autonomous_recalculation():
    evidence = _reference("evidence-and-judgment.md").lower()
    assert "`revenue_cagr` (→ `revenue_growth`)" in evidence
    assert "`operating_margin` (target margin only)" in evidence
    assert "`sales_to_capital`" in evidence
    assert "sector-level versions" in evidence
    assert "source-backed r&d capitalization" in evidence
    for blocked in ["wacc", "terminal growth", "tax", "leases", "share count"]:
        assert blocked in evidence
    assert "explain/flag only" in evidence
    assert "`operating_margin_next_year` is scenario-only" in evidence


def test_accounting_adjustments_are_explain_flag_only_unless_supported():
    accounting = _reference("accounting-and-claims.md").lower()
    assert "automatic in the normal autonomous researched flow" in accounting
    assert "retrieved non-yahoo source provenance" in accounting
    assert "never infer a research asset from one expense line" in accounting
    assert "report-only" in accounting


def test_fail_closed_rules_remain_intact():
    evidence = _reference("evidence-and-judgment.md").lower()
    assert "weak, mixed, stale, generic, or uncited evidence ⇒ no change" in evidence
    assert "no-change reason" in evidence
    assert "do not cite search snippets as evidence" in evidence
