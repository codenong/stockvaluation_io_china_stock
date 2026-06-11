from valuation_agent.installer import bundled_skill_dir
from valuation_agent.mcp_tools import MCPToolRegistry


def _reference(name: str) -> str:
    return (bundled_skill_dir() / "references" / name).read_text(encoding="utf-8")


def test_segment_aware_workflow_docs_define_public_acceptance_contract():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    segments = _reference("segments.md").lower()
    mcp = _reference("mcp-tools.md").lower()

    assert "segment-aware mechanical baseline" in skill
    assert skill.index("segment discovery") < skill.index("researched mechanical baseline")

    for status in [
        "segment_weighted_baseline",
        "single_industry_fallback",
        "segment_evidence_insufficient",
        "segment_mapping_blocked",
    ]:
        assert status in segments
        assert status in mcp

    for required_field in [
        "revenue weight or amount",
        "source name/url/date",
        "mapped industry",
        "mapping confidence",
        "validation warnings",
    ]:
        assert required_field in segments

    assert "80%" in segments
    assert "generic source presence is not segment evidence" in segments
    assert "segment names without revenue weights" in segments


def test_report_references_require_segment_economics_quality_and_no_overclaiming():
    segments = _reference("segments.md").lower()
    mcp = _reference("mcp-tools.md").lower()

    for phrase in [
        "segment_economics_quality",
        "validated_full_economics",
        "partial_economics",
        "revenue_only_segments",
        "per-driver",
    ]:
        assert phrase in segments

    for driver in ["revenue mix", "growth", "margin", "reinvestment intensity"]:
        assert driver in segments

    assert "revenue-only evidence cannot support growth, margin, or reinvestment changes" in segments
    assert "sector_key" in segments
    assert "baselineusestatus" in segments
    assert "blank references are rejected" in segments
    assert "do not describe a revenue-only segment package as fully segment-modeled" in segments
    assert "`segment_economics`" in mcp
    assert "yahoo_industry_key" in mcp


def test_guided_refinement_reference_defines_bounded_user_judgment_flow():
    workflow = _reference("workflow.md").lower()

    for phrase in [
        "run guided refinement in every default flow",
        "hard cap 15, no forced minimum, no filler",
        "one question at a time",
        "batch mode only when explicitly requested",
        "use defaults",
        "the returned plan is the source of truth",
        "never downgrade a `user scenario override`",
        "stockvaluation.apply_guided_answers",
        "request_policy.mode = \"user_refined_scenario\"",
        "exactly one final deterministic call",
    ]:
        assert phrase in workflow

    for stale_rule in ["at most 8 in deep mode", "fixed 3-question", "ask three questions"]:
        assert stale_rule not in workflow


def test_evidence_review_gate_is_required_before_guided_refinement():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    workflow = _reference("workflow.md").lower()

    assert "workflow.md" in skill
    assert skill.index("evidence review gate") < skill.index("guided refinement:")

    for phrase in [
        "stop and show a compact human review before any guided question or report",
        "approve, correct, add sources, or continue with caveats",
        "not a recommendation and not financial advice",
        "user corrections are not external evidence unless source-backed",
    ]:
        assert phrase in workflow


def test_evidence_review_gate_documents_required_visible_fields():
    workflow = _reference("workflow.md").lower()

    for phrase in [
        "core financial source",
        "sources checked with dates",
        "driver-specific evidence",
        "segment evidence and limitations",
        "data gaps",
        "conflicts",
        "supported model changes vs report-only vs unsupported",
    ]:
        assert phrase in workflow


def test_guided_refinement_documents_supported_and_report_only_fields():
    mcp = _reference("mcp-tools.md").lower()
    evidence = _reference("evidence-and-judgment.md").lower()

    for supported in [
        "revenue_growth",
        "operating_margin_next_year",
        "target_operating_margin",
        "margin_convergence_year",
        "sales_to_capital",
        "sector_overrides",
    ]:
        assert supported in mcp

    for report_only in ["market-implied diagnostics", "wacc", "terminal growth", "tax", "cash", "debt", "share count"]:
        assert report_only in evidence
    assert "report-only" in evidence


def test_valuation_method_consistency_statuses_are_documented_for_reports():
    workflow = _reference("workflow.md").lower()
    mcp = _reference("mcp-tools.md").lower()
    evidence = _reference("evidence-and-judgment.md").lower()
    segments = _reference("segments.md").lower()

    for status in [
        "valuationbasisstatus",
        "valuationcasestatus",
        "clean_pro_forma_basis",
        "pro_forma_cash_missing",
        "gross_proceeds_estimate_only",
        "challenged_valuation_case",
        "clean_valuation_case",
    ]:
        assert status in mcp

    for phrase in [
        "no clean user-facing valuation was produced",
        "post-offering shares require pro-forma cash",
        "do not show the diagnostic value before evidence review",
        "continues with caveats",
        "challenged diagnostic value",
        "dcf.estimatedvaluepershare",
    ]:
        assert phrase in workflow

    assert "market_calibrated_diagnostic" in evidence
    assert "segment_mapping_material_gap" in segments


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
