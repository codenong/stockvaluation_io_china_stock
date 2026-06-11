"""Skill corpus contract tests (post workflow-consistency M5 rewrite).

The corpus is budgeted and judgment-only; deterministic control flow lives in
code (see docs/internal/rule-triage.md). These tests assert the budget, the
file set, and the load-bearing judgment boundaries — not rule wording at
large.
"""

from pathlib import Path

from valuation_agent.installer import bundled_skill_dir

EXPECTED_REFERENCES = {
    "mcp-tools.md",
    "workflow.md",
    "evidence-and-judgment.md",
    "valuation-method.md",
    "segments.md",
    "accounting-and-claims.md",
    "report.md",
    "no-advice-policy.md",
}


def _read_reference(name: str) -> str:
    return (bundled_skill_dir() / "references" / name).read_text(encoding="utf-8")


def _skill_text() -> str:
    return (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")


def test_reference_set_is_exactly_the_eight_thematic_files():
    found = {path.name for path in (bundled_skill_dir() / "references").glob("*.md")}
    assert found == EXPECTED_REFERENCES


def test_corpus_word_budgets_hold():
    skill_words = len(_skill_text().split())
    assert skill_words <= 800
    total = skill_words + sum(len(_read_reference(name).split()) for name in EXPECTED_REFERENCES)
    assert total <= 8000


def test_skill_references_only_existing_files():
    import re

    text = _skill_text() + "".join(_read_reference(name) for name in EXPECTED_REFERENCES)
    for match in re.findall(r"references/([a-z-]+\.md)", text):
        assert match in EXPECTED_REFERENCES, f"dangling reference: {match}"


def test_no_advice_policy_kept_verbatim():
    policy = _read_reference("no-advice-policy.md")
    assert "StockValuation.io output must remain educational." in policy
    assert "Do not present reports as financial, investment, tax, legal, or personalized advice." in policy
    assert "Personalized recommendations." in policy
    assert "Direct trading instructions." in policy
    assert '"This is not financial advice."' in policy


def test_method_reference_keeps_autonomous_boundary_and_stop_rules():
    method = _read_reference("valuation-method.md").lower()
    assert "never do the valuation math yourself" in method
    assert "revenue growth, target operating margin, sales-to-capital, sector-level versions" in method
    assert "never change wacc autonomously" in method
    assert "never change terminal growth autonomously" in method
    assert "financial firms" in method and "no synthetic fcff report" in method
    assert "never invent break-even, frontier, sensitivity, or composition values" in method


def test_evidence_reference_keeps_evidence_discipline():
    evidence = _read_reference("evidence-and-judgment.md").lower()
    assert "generic source presence is not evidence" in evidence
    assert '"10-k found"' in evidence
    assert "do not cite search snippets as evidence" in evidence
    assert "do not invent facts, numbers, or quotes" in evidence
    assert "trailing growth alone is not a runway" in evidence
    assert "user answers define a scenario; they are not independent evidence" in evidence
    assert "market-implied diagnostics" in evidence and "report-only" in evidence


def test_workflow_reference_keeps_gate_and_guided_judgment():
    workflow = _read_reference("workflow.md").lower()
    assert "stop and show a compact human review" in workflow
    assert "sec primary source was expected but unavailable" in workflow
    assert "no supported deterministic primary-filing adapter covers this listing" in workflow
    assert "do not present a generic `approve` prompt as sufficient" in workflow
    assert "one question at a time" in workflow
    assert "hard cap 15, no forced minimum, no filler" in workflow
    assert "never downgrade a `user scenario override`" in workflow
    assert "review_status=reviewed" in workflow
    assert "offering price is a price basis, not a recommendation" in workflow
    assert "not financial advice" in workflow


def test_skill_md_names_server_enforced_gates_and_default_flow():
    skill = _skill_text().lower()
    assert "full researched valuation flow" in skill
    assert "gate_not_cleared" in skill
    assert "unanchored_scenario_value" in skill
    assert "valuationrange" in skill
    assert "never infer an evidence-review or guided-refinement bypass" in skill
    assert "ask one question at a time" in skill
    assert "stockvaluation.value_ticker" in skill
    assert "not financial advice" in skill
    assert skill.index("segment discovery") < skill.index("researched mechanical baseline")
