import json
from pathlib import Path

from valuation_agent.accounting_and_claims import validate_accounting_override


REPO_ROOT = Path(__file__).resolve().parents[3]
PHASE_5_CASES = (
    REPO_ROOT
    / "valuation-agent"
    / "tests"
    / "agent_native"
    / "fixtures"
    / "phase_5_accounting_claims_cases.json"
)


def _valid_rd_payload(**overrides):
    payload = {
        "enabled": True,
        "rd_history": [
            {
                "fiscal_year": 2026,
                "amount": 12000.0,
                "source_url": "https://example.com/2026-10k",
                "source_date": "2026-02-26",
            },
            {
                "fiscal_year": 2025,
                "amount": 9000.0,
                "source_url": "https://example.com/2025-10k",
                "source_date": "2025-02-27",
            },
            {
                "fiscal_year": 2024,
                "amount": 7000.0,
                "source_url": "https://example.com/2024-10k",
                "source_date": "2024-02-28",
            },
        ],
        "amortization_policy": {
            "method": "straight_line",
            "amortization_period_years": 4,
        },
        "source_provenance": {
            "source_class": "primary_filing",
            "provider": "sec-filing",
            "source_date": "2026-02-26",
            "retrieval_status": "retrieved",
        },
    }
    payload.update(overrides)
    return payload


def test_rd_capitalization_governed_scenario_requires_history_policy_and_provenance():
    result = validate_accounting_override(
        "rd_capitalization",
        _valid_rd_payload(),
        "explicit_scenario",
    )

    assert result["ok"] is True
    assert result["accepted_mcp_inputs"] == {
        "isExpensesCapitalize": True,
        "rdAmortizationMethod": "straight_line",
        "rdAmortizationPeriodYears": 4,
    }
    scenario = result["governed_scenarios"][0]
    assert scenario["topic"] == "rd_capitalization"
    assert scenario["status"] == "governed_scenario_supported"
    assert scenario["history_years"] == 3
    assert scenario["amortization_policy"]["amortization_period_years"] == 4
    assert scenario["source_provenance"]["source_class"] == "primary_filing"


def test_lease_schedule_remains_report_only_even_in_explicit_scenario():
    result = validate_accounting_override(
        "leases",
        {
            "enabled": True,
            "lease_expense_current_year": 100.0,
            "commitments": [90.0, 80.0, 70.0, 60.0, 50.0],
            "future_commitment": 120.0,
            "source_provenance": {
                "source_class": "primary_filing",
                "provider": "sec-filing",
                "source_date": "2026-02-26",
                "retrieval_status": "retrieved",
            },
        },
        "explicit_scenario",
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_report_only"
    assert result["accepted_mcp_inputs"] == {}
    assert result["governed_scenarios"] == []
    assert result["unsupported"][0]["topic"] == "leases"


def test_lease_schedule_with_yahoo_normalized_provenance_still_cannot_authorize_modeling():
    result = validate_accounting_override(
        "leases",
        {
            "enabled": True,
            "lease_expense_current_year": 100.0,
            "commitments": [90.0, 80.0],
            "future_commitment": 120.0,
            "source_provenance": {
                "source_class": "yahoo_normalized",
                "provider": "Yahoo Finance",
                "source_date": "2026-02-26",
                "retrieval_status": "retrieved",
            },
        },
        "explicit_scenario",
    )

    assert result["ok"] is False
    assert result["unsupported"][0]["status"] == "blocked_report_only"
    assert result["accepted_mcp_inputs"] == {}


def test_rd_capitalization_rejects_single_year_history_as_source_required():
    result = validate_accounting_override(
        "rd_capitalization",
        _valid_rd_payload(rd_history=[_valid_rd_payload()["rd_history"][0]]),
        "explicit_scenario",
    )

    assert result["ok"] is False
    assert result["unsupported"][0]["status"] == "source_required"
    assert "at least three" in result["validation_warnings"][0]
    assert result["accepted_mcp_inputs"] == {}


def test_rd_capitalization_rejects_yahoo_normalized_provenance_for_governed_support():
    result = validate_accounting_override(
        "rd_capitalization",
        _valid_rd_payload(
            source_provenance={
                "source_class": "yahoo_normalized",
                "provider": "Yahoo Finance",
                "source_date": "2026-02-26",
                "retrieval_status": "retrieved",
            }
        ),
        "explicit_scenario",
    )

    assert result["ok"] is False
    assert result["unsupported"][0]["status"] == "source_required"
    assert "source_provenance" in result["validation_warnings"][0]


def test_accounting_topics_without_governed_path_remain_report_only():
    topics = [
        "sbc_dilution",
        "leases",
        "operating_leases",
        "options",
        "warrants",
        "options_warrants",
        "nols",
        "nol_tax",
        "cash",
        "debt",
        "share_count",
        "accounting_adjustments",
    ]

    for topic in topics:
        result = validate_accounting_override(topic, {"value": 1}, "explicit_scenario")
        assert result["ok"] is False
        assert result["status"] == "blocked_report_only"
        assert result["unsupported"][0]["topic"] == topic
        assert result["accepted_mcp_inputs"] == {}


def test_rd_capitalization_is_blocked_outside_explicit_scenario_mode():
    result = validate_accounting_override(
        "rd_capitalization",
        _valid_rd_payload(),
        "autonomous_researched",
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_report_only"
    assert result["accepted_mcp_inputs"] == {}


def test_phase_5_accounting_claims_acceptance_fixture_covers_required_topics():
    cases = json.loads(PHASE_5_CASES.read_text())

    topics = {
        topic
        for case in cases
        for topic in case["expected_statuses"]
    }

    assert {case["case_id"] for case in cases} == {
        "tech_rd_sbc",
        "lease_heavy",
        "options_warrants_claims",
        "nol_tax_sensitive",
        "cash_debt_share_count",
    }
    assert topics == {
        "rdCapitalization",
        "sbcDilution",
        "leases",
        "optionsWarrants",
        "nolTax",
        "cash",
        "debt",
        "shareCount",
    }
    assert all(case["expected_rejection_behavior"] for case in cases)
