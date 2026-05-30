from valuation_agent.installer import bundled_skill_dir
from valuation_agent.mcp_tools import MCPToolRegistry


def _reference(name: str) -> str:
    return (bundled_skill_dir() / "references" / name).read_text(encoding="utf-8")


def test_segment_aware_workflow_docs_define_public_acceptance_contract():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    segment_discovery = _reference("segment-discovery.md").lower()
    segment_quality = _reference("segment-quality.md").lower()
    mcp = _reference("mcp-tools.md").lower()
    report = _reference("report-template.md").lower()

    assert "segment-aware mechanical baseline" in skill
    assert skill.index("segment discovery") < skill.index("researched mechanical baseline")

    for status in [
        "segment_weighted_baseline",
        "single_industry_fallback",
        "segment_evidence_insufficient",
        "segment_mapping_blocked",
    ]:
        assert status in segment_discovery
        assert status in mcp
        assert status in report

    for required_field in [
        "segment name",
        "revenue weight",
        "source name",
        "source date",
        "source url",
        "mapped industry",
        "mapping confidence",
        "validation warnings",
    ]:
        assert required_field in segment_discovery
        assert required_field in mcp

    assert "80%" in segment_quality
    assert "generic source presence is not segment evidence" in segment_quality
    assert "segment names without revenue weights" in segment_quality
    assert "market-implied diagnostics" in report


def test_report_references_require_segment_economics_quality_and_no_overclaiming():
    segment_quality = _reference("segment-quality.md").lower()
    mcp = _reference("mcp-tools.md").lower()
    report = _reference("report-template.md").lower()

    for phrase in [
        "segment_economics_quality",
        "validated_full_economics",
        "partial_economics",
        "revenue_only_segments",
        "per-driver segment status",
    ]:
        assert phrase in segment_quality
        assert phrase in report

    for driver in ["revenue mix", "growth", "margin", "reinvestment intensity"]:
        assert driver in segment_quality
        assert driver in report

    assert "revenue-only segment evidence cannot support growth, margin, or reinvestment changes" in segment_quality
    assert "sector_key" in segment_quality
    assert "baselineusestatus" in segment_quality
    assert "blank url/date references are rejected" in segment_quality
    assert "baseline.segmentaware" in report
    assert "validated_segment_weighted" in report
    assert "do not describe a revenue-only segment package as fully segment-modeled" in report
    assert "`segment_economics`" in mcp
    assert "yahoo_industry_key" in mcp


def test_guided_refinement_reference_defines_bounded_user_judgment_flow():
    reference = _reference("guided-valuation-refinement.md")
    lower = reference.lower()

    for phrase in [
        "default full researched valuation: use guided refinement",
        "materiality-driven guided refinement",
        "ask every material company-specific question",
        "hard cap of 15 visible guided questions",
        "no forced minimum",
        "one question at a time",
        "hidden guided question plan",
        "batch mode only when explicitly requested",
        "do not ask a batch of 4-6 questions",
        "do not invent filler questions",
        "use defaults",
        "user answers are user judgment, not external evidence",
        "one final user-refined recalculation",
        "request_policy.mode = \"user_refined_scenario\"",
        "send only supported mapped assumptions",
        "not financial advice",
    ]:
        assert phrase in lower

    for stale_rule in ["at most 8 in deep mode", "8 questions", "fixed 3-question", "ask three questions"]:
        assert stale_rule not in lower

    for field in [
        '"id"',
        '"driver"',
        '"evidence_basis"',
        '"evidence_used"',
        '"default_answer"',
        '"company_specific_rationale"',
        '"business_tension"',
        '"why_default_selected"',
        '"business_impact"',
        '"model_impact"',
        '"bounded_choices"',
        '"recommended_answer"',
        '"hidden_model_mapping"',
        '"confidence"',
        '"status"',
        '"mapping_notes"',
        '"priority_reason"',
    ]:
        assert field in reference

    for phrase in [
        "my analysis",
        "why this default",
        "evidence used",
        "business impact",
        "model impact",
        "confidence",
        "markdown question card",
        "question number",
        "choices table",
        "default marker",
        "reply options",
    ]:
        assert phrase in lower


def test_evidence_review_gate_is_required_before_guided_refinement():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    gate = _reference("evidence-review-gate.md").lower()

    assert "evidence-review-gate.md" in skill
    assert skill.index("driver-specific-evidence.md") < skill.index("evidence-review-gate.md")
    assert skill.index("evidence-review-gate.md") < skill.index("baseline-plausibility.md")
    assert skill.index("evidence-review-gate.md") < skill.index("guided-valuation-refinement.md")

    for phrase in [
        "default interactive researched valuation must stop at this gate",
        "do not ask guided valuation refinement questions before the gate is cleared",
        "approve and continue to guided questions",
        "provide corrections",
        "provide additional sources",
        "continue with caveats",
        "approval is not financial advice",
        "user corrections are not external evidence unless source-backed",
    ]:
        assert phrase in gate


def test_evidence_review_gate_documents_required_visible_fields():
    gate = _reference("evidence-review-gate.md").lower()

    for phrase in [
        "source quality summary",
        "sources checked",
        "source dates",
        "driver-specific evidence",
        "segment evidence and segment limitations",
        "latest news or material business context",
        "data gaps",
        "conflicts",
        "supported model changes",
        "report-only",
        "unsupported topics",
        "workflow treatment",
    ]:
        assert phrase in gate


def test_guided_refinement_documents_supported_and_report_only_fields():
    reference = _reference("guided-valuation-refinement.md").lower()

    for supported in [
        "revenue_growth",
        "operating_margin_next_year",
        "target_operating_margin",
        "margin_convergence_year",
        "sales_to_capital_years_1_to_5",
        "sales_to_capital_years_6_to_10",
        "sector_overrides",
    ]:
        assert supported in reference

    for report_only in [
        "market-implied diagnostics are report-only",
        "wacc",
        "terminal growth",
        "tax",
        "accounting adjustments",
        "cash",
        "debt",
        "share count",
        "direct valuation outputs",
    ]:
        assert report_only in reference


def test_user_refined_scenario_mcp_rejects_explicit_only_fields():
    class FakeClient:
        calls = []

        def value_ticker(self, ticker, overrides=None):
            self.calls.append((ticker, overrides or {}))
            return {}

    client = FakeClient()
    result = MCPToolRegistry(client).call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "user_refined_scenario"},
                "wacc": 8.5,
                "terminal_growth": 3.0,
                "tax_rate": 21.0,
                "growth_pattern_override": "THREE_STAGE",
            },
        },
    )

    assert result["isError"] is True
    unsupported = result["structuredContent"]["assumptions"]["unsupported"]
    assert set(unsupported) == {"wacc", "terminal_growth", "tax_rate", "growth_pattern_override"}
    assert all(
        item["reason"] == "explicit_scenario_only_in_user_refined_scenario_mode"
        for item in unsupported.values()
    )
    assert client.calls == []
