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


def test_guided_refinement_reference_defines_bounded_user_judgment_flow():
    reference = _reference("guided-valuation-refinement.md")
    lower = reference.lower()

    for phrase in [
        "default full researched valuation: use guided refinement",
        "ask 4-6 questions",
        "user answers are user judgment, not external evidence",
        "request_policy.mode = \"user_refined_scenario\"",
        "send only supported mapped assumptions",
        "not financial advice",
    ]:
        assert phrase in lower

    for field in [
        '"company_specific_rationale"',
        '"business_tension"',
        '"why_this_matters"',
        '"bounded_choices"',
        '"recommended_answer"',
        '"mapping_notes"',
        '"priority_reason"',
    ]:
        assert field in reference


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
