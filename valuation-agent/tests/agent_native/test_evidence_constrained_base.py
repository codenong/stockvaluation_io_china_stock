from valuation_agent.installer import bundled_skill_dir
from valuation_agent.mcp_tools import MCPToolRegistry


def _reference(name: str) -> str:
    return (bundled_skill_dir() / "references" / name).read_text(encoding="utf-8")


def test_skill_references_baseline_plausibility_after_driver_evidence_before_judgment():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    lower = skill.lower()

    assert "baseline-plausibility.md" in skill
    assert "mechanical baseline" in lower
    assert "evidence-constrained base" in lower
    assert "market-implied diagnostics" in lower
    assert lower.index("driver-specific-evidence.md") < lower.index("baseline-plausibility.md")
    assert lower.index("baseline-plausibility.md") < lower.index("assumption-judgment.md")


def test_baseline_plausibility_reference_defines_required_workflow_terms():
    reference = _reference("baseline-plausibility.md")
    lower = reference.lower()

    for term in [
        "mechanical_baseline",
        "evidence_constrained_base",
        "market_implied_diagnostics",
        "optimistic_assumption_stack",
        "unsupported_blockers",
        "fail-closed",
    ]:
        assert term in lower
    for check in ["price / value gap", "growth", "margin path", "reinvestment / sales-to-capital"]:
        assert check in lower
    assert "greater than 50%" in lower
    assert "trailing growth alone is not enough" in lower


def test_assumption_judgment_contract_carries_plausibility_and_blockers():
    judgment = _reference("assumption-judgment.md")
    lower = judgment.lower()

    for field in [
        '"baseline_plausibility"',
        '"baseline_quality"',
        '"price_value_gap_flag"',
        '"optimistic_assumption_stack"',
        '"market_implied_diagnostics_status"',
        '"researched_case_status"',
        '"unsupported_blockers"',
        '"assumptions_left_unchanged"',
    ]:
        assert field in judgment
    assert "market-implied diagnostics are report-only" in lower
    assert "`operating_margin_next_year` does not map to an autonomous override" in lower


def test_report_template_distinguishes_mechanical_evidence_constrained_and_market_implied():
    template = _reference("report-template.md")
    lower = template.lower()

    assert "## Mechanical Baseline Vs Evidence-Constrained Base Vs Market-Implied" in template
    assert "mechanical baseline" in lower
    assert "evidence-constrained base" in lower
    assert "market-implied diagnostics" in lower
    assert "do not use market-implied values as the researched base" in lower
    assert "unsupported blockers" in lower
    assert "| operating margin next year |  | unsupported or explicit scenario only |" in lower


def test_market_implied_values_remain_report_only_not_autonomous_evidence():
    plausibility = _reference("baseline-plausibility.md").lower()
    judgment = _reference("assumption-judgment.md").lower()
    report = _reference("report-template.md").lower()
    mcp = _reference("mcp-tools.md").lower()

    for text in [plausibility, judgment, report, mcp]:
        assert "market-implied" in text
        assert "not evidence" in text or "not autonomous model changes" in text
    assert "market_implied_diagnostics_status" in judgment


def test_operating_margin_next_year_is_rejected_in_autonomous_researched_mode():
    class FakeClient:
        calls = []

        def value_ticker(self, ticker, overrides=None):
            self.calls.append((ticker, overrides or {}))
            return {}

    client = FakeClient()
    result = MCPToolRegistry(client).call(
        "stockvaluation.recalculate",
        {
            "ticker": "NVDA",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "operating_margin_next_year": 60.0,
            },
        },
    )

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "UNSUPPORTED_OVERRIDES"
    assert "operating_margin_next_year" in result["structuredContent"]["assumptions"]["unsupported"]
    assert (
        result["structuredContent"]["assumptions"]["unsupported"]["operating_margin_next_year"]["reason"]
        == "scenario_only_in_autonomous_researched_mode"
    )
    assert client.calls == []
    assert "`operating_margin_next_year` is scenario-only in autonomous researched mode" in _reference("mcp-tools.md")
