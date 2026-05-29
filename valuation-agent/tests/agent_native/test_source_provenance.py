import json
from pathlib import Path

from valuation_agent.source_provenance import validate_source_provenance_packet

FIXTURES = Path(__file__).parent / "fixtures"


def test_us_researched_yahoo_financials_surface_missing_primary_fallback():
    result = validate_source_provenance_packet(
        {
            "ticker": "MSFT",
            "company": "Microsoft Corporation",
            "country": "United States",
            "run_mode": "full_researched",
            "as_of_date": "2026-05-29",
            "core_financials": {
                "source_class": "yahoo_normalized",
                "provider": "Yahoo Finance via local yfinance service",
                "source_date": "2025-06-30",
                "period_end": "2025-06-30",
                "retrieval_status": "retrieved",
                "primary_source_expected": True,
                "primary_source_available": False,
                "cross_check_status": "not_checked",
            },
        }
    )

    assert result["ok"] is True
    assert result["status"] == "primary_source_missing_fallback"
    assert result["core_financials"]["source_class"] == "yahoo_normalized"
    assert result["core_financials"]["source_policy_status"] == "primary_source_missing_fallback"
    assert result["policy_warnings"] == [
        "US researched valuation is using Yahoo-normalized financials because primary filing data is missing or unavailable."
    ]


def test_source_provenance_rejects_unknown_source_class_and_missing_dates():
    result = validate_source_provenance_packet(
        {
            "ticker": "MSFT",
            "company": "Microsoft Corporation",
            "country": "United States",
            "run_mode": "full_researched",
            "as_of_date": "2026-05-29",
            "core_financials": {
                "source_class": "market_implied",
                "provider": "Market price diagnostics",
                "retrieval_status": "retrieved",
                "primary_source_expected": True,
                "primary_source_available": False,
                "cross_check_status": "not_applicable",
            },
        }
    )

    assert result["ok"] is False
    assert result["status"] == "invalid_packet"
    assert result["validation_warnings"] == [
        "core_financials.source_class must be primary_filing, yahoo_normalized, company_ir, or agent_researched.",
        "core_financials.source_date must be YYYY-MM-DD for retrieved sources.",
        "core_financials.period_end must be YYYY-MM-DD for retrieved sources.",
    ]


def test_source_provenance_marks_stale_source_dates_visible():
    result = validate_source_provenance_packet(
        {
            "ticker": "MSFT",
            "company": "Microsoft Corporation",
            "country": "United States",
            "run_mode": "full_researched",
            "as_of_date": "2026-05-29",
            "core_financials": {
                "source_class": "primary_filing",
                "provider": "SEC company facts fixture",
                "source_date": "2023-12-31",
                "period_end": "2023-12-31",
                "retrieval_status": "retrieved",
                "primary_source_expected": True,
                "primary_source_available": True,
                "cross_check_status": "not_applicable",
            },
        }
    )

    assert result["ok"] is True
    assert result["status"] == "stale_source_date"
    assert result["core_financials"]["source_policy_status"] == "stale_source_date"
    assert result["policy_warnings"] == [
        "Core financial source date is stale relative to the valuation as-of date."
    ]


def test_non_us_yahoo_normalized_financials_are_allowed_with_cross_check_status():
    result = validate_source_provenance_packet(
        {
            "ticker": "SAP.DE",
            "company": "SAP SE",
            "country": "Germany",
            "run_mode": "full_researched",
            "as_of_date": "2026-05-29",
            "core_financials": {
                "source_class": "yahoo_normalized",
                "provider": "Yahoo Finance via local yfinance service",
                "source_date": "2025-12-31",
                "period_end": "2025-12-31",
                "retrieval_status": "retrieved",
                "primary_source_expected": False,
                "primary_source_available": False,
                "cross_check_status": "company_report_check_pending",
            },
        }
    )

    assert result["ok"] is True
    assert result["status"] == "yahoo_normalized_with_cross_check_status"
    assert result["core_financials"]["source_policy_status"] == "yahoo_normalized_with_cross_check_status"
    assert result["core_financials"]["cross_check_status"] == "company_report_check_pending"
    assert result["policy_warnings"] == [
        "Non-US researched valuation may use Yahoo-normalized financials when company-report cross-check status is explicit."
    ]


def test_material_yahoo_vs_company_report_difference_emits_reconciliation_warning():
    result = validate_source_provenance_packet(
        {
            "ticker": "SAP.DE",
            "company": "SAP SE",
            "country": "Germany",
            "run_mode": "full_researched",
            "as_of_date": "2026-05-29",
            "core_financials": {
                "source_class": "yahoo_normalized",
                "provider": "Yahoo Finance via local yfinance service",
                "source_date": "2025-12-31",
                "period_end": "2025-12-31",
                "retrieval_status": "retrieved",
                "primary_source_expected": False,
                "primary_source_available": False,
                "cross_check_status": "company_report_cross_checked",
            },
            "material_cross_checks": [
                {
                    "field": "revenue",
                    "normalized_value": 100.0,
                    "filing_value": 112.0,
                    "source_class": "company_ir",
                    "source_date": "2025-12-31",
                    "threshold_pct": 0.05,
                }
            ],
        }
    )

    assert result["ok"] is True
    assert result["data_quality_warnings"] == [
        {
            "field": "revenue",
            "status": "material_mismatch",
            "normalized_value": 100.0,
            "filing_value": 112.0,
            "difference_pct": 0.1071,
            "threshold_pct": 0.05,
            "source_class": "company_ir",
            "source_date": "2025-12-31",
        }
    ]


def test_us_researched_run_rejects_yahoo_when_primary_source_is_available():
    result = validate_source_provenance_packet(
        {
            "ticker": "MSFT",
            "company": "Microsoft Corporation",
            "country": "United States",
            "run_mode": "full_researched",
            "as_of_date": "2026-05-29",
            "core_financials": {
                "source_class": "yahoo_normalized",
                "provider": "Yahoo Finance via local yfinance service",
                "source_date": "2025-06-30",
                "period_end": "2025-06-30",
                "retrieval_status": "retrieved",
                "primary_source_expected": True,
                "primary_source_available": True,
                "cross_check_status": "not_checked",
            },
        }
    )

    assert result["ok"] is False
    assert result["status"] == "primary_source_available_not_used"
    assert result["core_financials"]["source_policy_status"] == "primary_source_available_not_used"
    assert result["policy_warnings"] == [
        "US researched valuation has primary filing data available; Yahoo-normalized data cannot be treated as the preferred source."
    ]


def test_source_provenance_acceptance_fixture_cases_match_phase_3_policy():
    cases = json.loads((FIXTURES / "source_provenance_acceptance_cases.json").read_text())["cases"]

    results = {case["name"]: validate_source_provenance_packet(case["packet"]) for case in cases}

    assert results["us_missing_primary_fallback"]["status"] == "primary_source_missing_fallback"
    assert results["non_us_yahoo_with_cross_check_status"]["status"] == "yahoo_normalized_with_cross_check_status"
    assert results["material_reconciliation_mismatch"]["data_quality_warnings"][0]["status"] == "material_mismatch"
