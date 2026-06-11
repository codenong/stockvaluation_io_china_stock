from valuation_agent.installer import bundled_skill_dir
from valuation_agent.mcp_tools import MCPToolRegistry


def _reference(name: str) -> str:
    return (bundled_skill_dir() / "references" / name).read_text(encoding="utf-8")


def test_skill_orders_evidence_before_gate_before_judgment():
    skill = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()

    assert "evidence-and-judgment.md" in skill
    assert "mechanical baseline" in skill
    assert skill.index("classify driver-specific evidence") < skill.index("evidence review gate")
    assert skill.index("evidence review gate") < skill.index("baseline plausibility")
    assert skill.index("baseline plausibility") < skill.index("assumption_judgment")


def test_plausibility_rules_define_required_workflow_terms():
    reference = _reference("evidence-and-judgment.md").lower()

    for term in [
        "price/value gap",
        "optimistic stack",
        "unsupported blocker",
        "mechanical baseline",
        "evidence-constrained base",
        "market-implied diagnostics",
    ]:
        assert term in reference
    assert "exceeds 50%" in reference
    assert "trailing growth alone is not a runway" in reference
    assert "market_calibrated_diagnostic" in reference
    assert "no-change case" in reference


def test_assumption_judgment_contract_carries_plausibility_and_blockers():
    reference = _reference("evidence-and-judgment.md")
    lower = reference.lower()

    assert "`assumption_judgment`" in reference
    assert "`baseline_plausibility`" in reference
    assert "`evidence_used`" in reference
    assert "`no_change_reason`" in reference
    assert "`assumptions_left_unchanged`" in reference
    assert "keep requested, mapped, unsupported, and effective assumptions separate" in lower
    assert "never evidence" in lower


def test_report_reference_distinguishes_mechanical_evidence_constrained_and_market_implied():
    report = _reference("report.md").lower()

    assert "audit/debug" in report
    assert "do not show the internal mechanical model value" in report
    assert "diagnostic scenarios stay diagnostic" in report
    assert "market-implied or sensitivity runs belong in `market_implied_diagnostics`" in report


def test_market_implied_values_remain_report_only_not_autonomous_evidence():
    evidence = _reference("evidence-and-judgment.md").lower()
    method = _reference("valuation-method.md").lower()
    mcp = _reference("mcp-tools.md").lower()

    for text in [evidence, method, mcp]:
        assert "market-implied" in text
        assert "not evidence" in text or "not autonomous model changes" in text or "report-only" in text


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
    assert "`operating_margin_next_year` is scenario-only" in _reference("evidence-and-judgment.md")
