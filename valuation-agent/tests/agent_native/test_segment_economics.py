import json
from pathlib import Path

from valuation_agent.segment_economics import validate_segment_economics

FIXTURES = Path(__file__).parent / "fixtures"


def _evidence_packet(driver="operating_margin", **overrides):
    evidence_item = {
        "driver": driver,
        "source_title": "FY 2025 Form 10-K segment note",
        "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
        "source_date": "2026-02-05",
        "evidence_summary": "Google Cloud operating income increased and segment operating margin expanded.",
        "direction": "supports higher assumption",
        "confidence": "high",
        "assumption_implication": "Supports a governed Cloud operating margin override.",
        "allowed_to_affect_autonomous_recalculation": True,
        "model_action": "governed assumption change",
    }
    evidence_item.update(overrides)
    return {
        "ticker": "GOOGL",
        "company": "Alphabet Inc.",
        "run_mode": "full_researched",
        "source_families": [
            {
                "family": "segment_disclosure",
                "status": "checked",
                "source_title": "FY 2025 Form 10-K segment note",
                "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
                "source_date": "2026-02-05",
            }
        ],
        "sources_checked": [
            {
                "source_title": "FY 2025 Form 10-K segment note",
                "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
                "source_date": "2026-02-05",
                "status": "checked",
                "source_type": "segment",
                "used": True,
            }
        ],
        "evidence_items": [evidence_item],
        "conflicts_or_uncertainties": [],
        "data_gaps": [],
    }


def _segment(**overrides):
    segment = {
        "segment_name": "Google Cloud",
        "sector_key": "software-infrastructure",
        "mapped_industry": "Software (System & Application)",
        "mapping_confidence": "high",
        "revenue_share": 0.12,
        "source_name": "FY 2025 Form 10-K segment note",
        "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
        "source_date": "2026-02-05",
        "source_class": "primary_filing",
        "provider": "sec-filing",
        "retrieval_status": "retrieved",
        "disclosure_level": "reportable_segment",
    }
    segment.update(overrides)
    return segment


def test_validate_segment_economics_preserves_revenue_only_segments_without_driver_overrides():
    result = validate_segment_economics(
        {
            "ticker": "GOOGL",
            "company": "Alphabet Inc.",
            "run_mode": "full_researched",
            "segments": [
                {
                    "segment_name": "Google Services",
                    "sector_key": "advertising-agencies",
                    "mapped_industry": "Advertising",
                    "mapping_confidence": "high",
                    "revenue_share": 0.86,
                    "source_name": "FY 2025 Form 10-K segment note",
                    "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
                    "source_date": "2026-02-05",
                    "source_class": "primary_filing",
                    "provider": "sec-filing",
                    "retrieval_status": "retrieved",
                    "disclosure_level": "reportable_segment",
                },
                {
                    "segment_name": "Google Cloud",
                    "sector_key": "software-infrastructure",
                    "mapped_industry": "Software (System & Application)",
                    "mapping_confidence": "high",
                    "revenue_share": 0.12,
                    "source_name": "FY 2025 Form 10-K segment note",
                    "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
                    "source_date": "2026-02-05",
                    "source_class": "primary_filing",
                    "provider": "sec-filing",
                    "retrieval_status": "retrieved",
                    "disclosure_level": "reportable_segment",
                },
            ],
        }
    )

    assert result["ok"] is True
    assert result["status"] == "revenue_only_segments"
    assert result["accepted_mcp_inputs"]["segments"]["segments"][0]["segment_name"] == "Google Services"
    assert result["accepted_mcp_inputs"]["segments"]["segments"][0]["sector"] == "advertising-agencies"
    assert result["accepted_mcp_inputs"]["segments"]["segments"][0]["mapped_industry"] == "Advertising"
    assert result["accepted_mcp_inputs"]["sector_overrides"] == []
    services = result["segment_decisions"][0]
    assert services["drivers"]["revenue_mix"]["status"] == "model_supported"
    assert services["drivers"]["growth"]["status"] == "unavailable"
    assert services["drivers"]["margin"]["status"] == "unavailable"
    assert services["drivers"]["reinvestment_intensity"]["status"] == "unavailable"
    assert any("Revenue-only" in limitation for limitation in result["limitations"])


def test_validate_segment_economics_accepts_margin_override_with_evidence_packet_and_provenance():
    result = validate_segment_economics(
        {
            "ticker": "GOOGL",
            "company": "Alphabet Inc.",
            "run_mode": "full_researched",
            "segments": [
                _segment(
                    revenue_share=1.0,
                    drivers={
                        "margin": {
                            "evidence_ref": {
                                "driver": "operating_margin",
                                "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
                                "source_date": "2026-02-05",
                            },
                            "source_class": "primary_filing",
                            "provider": "sec-filing",
                            "retrieval_status": "retrieved",
                            "disclosure_level": "reportable_segment",
                            "model_action": "governed_sector_override",
                            "sector_override": {
                                "sector_key": "software-infrastructure",
                                "parameter": "operating_margin",
                                "value": 32.0,
                                "unit": "percent",
                                "adjustment_type": "absolute",
                                "timeframe": "both",
                            },
                        }
                    },
                )
            ],
            "evidence_packet": _evidence_packet(),
        }
    )

    assert result["ok"] is True
    assert result["status"] == "partial_economics"
    assert result["accepted_mcp_inputs"]["sector_overrides"] == [
        {
            "sector": "software-infrastructure",
            "parameter": "operating_margin",
            "value": 32.0,
            "unit": "percent",
            "adjustment_type": "absolute",
            "timeframe": "both",
        }
    ]
    cloud = result["segment_decisions"][0]
    assert cloud["drivers"]["margin"]["status"] == "model_supported"
    assert cloud["drivers"]["margin"]["evidence_driver"] == "operating_margin"


def test_validate_segment_economics_requires_service_sector_key_for_mcp_baseline():
    result = validate_segment_economics(
        {
            "ticker": "GOOGL",
            "company": "Alphabet Inc.",
            "run_mode": "full_researched",
            "segments": [
                _segment(
                    revenue_share=1.0,
                    sector_key="",
                    mapped_industry="Software (System & Application)",
                )
            ],
        }
    )

    assert result["ok"] is False
    assert result["status"] == "segment_mapping_blocked"
    assert result["accepted_mcp_inputs"]["segments"] is None
    assert any("sector_key" in limitation for limitation in result["limitations"])


def test_validate_segment_economics_rejects_margin_override_without_driver_provenance():
    result = validate_segment_economics(
        {
            "ticker": "GOOGL",
            "company": "Alphabet Inc.",
            "run_mode": "full_researched",
            "segments": [
                _segment(
                    revenue_share=1.0,
                    drivers={
                        "margin": {
                            "evidence_ref": {
                                "driver": "operating_margin",
                                "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
                                "source_date": "2026-02-05",
                            },
                            "provider": "sec-filing",
                            "retrieval_status": "retrieved",
                            "disclosure_level": "reportable_segment",
                            "model_action": "governed_sector_override",
                            "sector_override": {
                                "sector_key": "software-infrastructure",
                                "parameter": "operating_margin",
                                "value": 32.0,
                                "unit": "percent",
                                "adjustment_type": "absolute",
                                "timeframe": "both",
                            },
                        }
                    },
                )
            ],
            "evidence_packet": _evidence_packet(),
        }
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_by_rejected_segment_economics"
    assert result["accepted_mcp_inputs"]["sector_overrides"] == []
    assert result["rejected_economics"][0]["status"] == "missing_driver_provenance"
    assert "source_class" in result["rejected_economics"][0]["reason"]


def test_validate_segment_economics_rejects_driver_evidence_ref_without_exact_source_url_and_date():
    result = validate_segment_economics(
        {
            "ticker": "GOOGL",
            "company": "Alphabet Inc.",
            "run_mode": "full_researched",
            "segments": [
                _segment(
                    revenue_share=1.0,
                    drivers={
                        "margin": {
                            "evidence_ref": {
                                "driver": "operating_margin",
                            },
                            "source_class": "primary_filing",
                            "provider": "sec-filing",
                            "retrieval_status": "retrieved",
                            "disclosure_level": "reportable_segment",
                            "model_action": "governed_sector_override",
                            "sector_override": {
                                "sector_key": "software-infrastructure",
                                "parameter": "operating_margin",
                                "value": 32.0,
                                "unit": "percent",
                                "adjustment_type": "absolute",
                                "timeframe": "both",
                            },
                        }
                    },
                )
            ],
            "evidence_packet": _evidence_packet(),
        }
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_by_rejected_segment_economics"
    assert result["accepted_mcp_inputs"]["sector_overrides"] == []
    assert result["rejected_economics"][0]["status"] == "missing_governed_evidence"
    assert "source_url" in result["rejected_economics"][0]["reason"]
    assert "source_date" in result["rejected_economics"][0]["reason"]


def test_validate_segment_economics_rejects_growth_from_generic_source_presence():
    result = validate_segment_economics(
        {
            "ticker": "GOOGL",
            "company": "Alphabet Inc.",
            "run_mode": "full_researched",
            "segments": [
                _segment(
                    revenue_share=1.0,
                    drivers={
                        "growth": {
                            "evidence_ref": {
                                "driver": "revenue_growth",
                                "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
                                "source_date": "2026-02-05",
                            },
                            "source_class": "primary_filing",
                            "provider": "sec-filing",
                            "retrieval_status": "retrieved",
                            "disclosure_level": "reportable_segment",
                            "model_action": "governed_sector_override",
                            "sector_override": {
                                "sector_key": "software-infrastructure",
                                "parameter": "revenue_growth",
                                "value": 16.0,
                                "unit": "percent",
                                "adjustment_type": "absolute",
                                "timeframe": "years_1_to_5",
                            },
                        }
                    },
                )
            ],
            "evidence_packet": _evidence_packet(
                driver="revenue_growth",
                evidence_summary="10-K found",
                assumption_implication="No driver-specific segment growth fact was extracted.",
            ),
        }
    )

    assert result["ok"] is False
    assert result["accepted_mcp_inputs"]["sector_overrides"] == []
    assert result["metadata"]["evidence_packet"]["status"] == "invalid_packet"
    assert result["metadata"]["evidence_packet"]["rejected_evidence"][0]["status"] == "generic_source_presence"
    assert result["rejected_economics"][0]["status"] == "missing_governed_evidence"


def test_validate_segment_economics_accepts_reinvestment_only_with_explicit_economic_basis():
    result = validate_segment_economics(
        {
            "ticker": "GOOGL",
            "company": "Alphabet Inc.",
            "run_mode": "full_researched",
            "segments": [
                _segment(
                    revenue_share=1.0,
                    drivers={
                        "reinvestment_intensity": {
                            "evidence_ref": {
                                "driver": "reinvestment_sales_to_capital",
                                "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
                                "source_date": "2026-02-05",
                            },
                            "source_class": "primary_filing",
                            "provider": "sec-filing",
                            "retrieval_status": "retrieved",
                            "disclosure_level": "reportable_segment",
                            "reinvestment_basis": "capex_intensity",
                            "model_action": "governed_sector_override",
                            "sector_override": {
                                "sector_key": "software-infrastructure",
                                "parameter": "sales_to_capital",
                                "value": 2.1,
                                "unit": "x",
                                "adjustment_type": "absolute",
                                "timeframe": "both",
                            },
                        }
                    },
                )
            ],
            "evidence_packet": _evidence_packet(
                driver="reinvestment_sales_to_capital",
                evidence_summary="Cloud capex intensity increased with data-center investment.",
                assumption_implication="Supports lower sales-to-capital for Cloud than the mechanical baseline.",
            ),
        }
    )

    assert result["ok"] is True
    assert result["status"] == "partial_economics"
    assert result["accepted_mcp_inputs"]["sector_overrides"][0]["parameter"] == "sales_to_capital"
    cloud = result["segment_decisions"][0]
    assert cloud["drivers"]["reinvestment_intensity"]["status"] == "model_supported"
    assert cloud["drivers"]["reinvestment_intensity"]["reinvestment_basis"] == "capex_intensity"


def test_validate_segment_economics_rejects_reinvestment_inferred_from_revenue_share():
    result = validate_segment_economics(
        {
            "ticker": "GOOGL",
            "company": "Alphabet Inc.",
            "run_mode": "full_researched",
            "segments": [
                _segment(
                    revenue_share=1.0,
                    drivers={
                        "reinvestment_intensity": {
                            "evidence_ref": {
                                "driver": "reinvestment_sales_to_capital",
                                "source_url": "https://abc.xyz/investor/static/pdf/2025_alphabet_10k.pdf",
                                "source_date": "2026-02-05",
                            },
                            "source_class": "primary_filing",
                            "provider": "sec-filing",
                            "retrieval_status": "retrieved",
                            "disclosure_level": "reportable_segment",
                            "model_action": "governed_sector_override",
                            "sector_override": {
                                "sector_key": "software-infrastructure",
                                "parameter": "sales_to_capital",
                                "value": 2.1,
                                "unit": "x",
                                "adjustment_type": "absolute",
                                "timeframe": "both",
                            },
                        }
                    },
                )
            ],
            "evidence_packet": _evidence_packet(
                driver="reinvestment_sales_to_capital",
                evidence_summary="Cloud revenue share increased.",
                assumption_implication="Revenue share alone does not support sales-to-capital.",
            ),
        }
    )

    assert result["ok"] is False
    assert result["accepted_mcp_inputs"]["sector_overrides"] == []
    assert result["rejected_economics"][0]["status"] == "missing_reinvestment_basis"
    assert "capex" in result["rejected_economics"][0]["reason"].lower()


def test_validate_segment_economics_blocks_low_confidence_segment_mapping():
    result = validate_segment_economics(
        {
            "ticker": "COST",
            "company": "Costco Wholesale Corporation",
            "run_mode": "full_researched",
            "segments": [
                _segment(
                    segment_name="United States",
                    mapped_industry="Retail (Grocery and Food)",
                    mapping_confidence="low",
                    revenue_share=1.0,
                    disclosure_level="geography",
                )
            ],
        }
    )

    assert result["ok"] is False
    assert result["status"] == "segment_mapping_blocked"
    assert result["quality"] == "segment_mapping_blocked"
    assert result["accepted_mcp_inputs"]["segments"] is None
    assert any("mapping confidence" in warning for warning in result["limitations"])


def test_validate_segment_economics_blocks_geography_disclosure_without_operating_segment_rationale():
    result = validate_segment_economics(
        {
            "ticker": "COST",
            "company": "Costco Wholesale Corporation",
            "run_mode": "full_researched",
            "segments": [
                _segment(
                    segment_name="United States",
                    sector_key="discount-stores",
                    mapped_industry="Retail (Grocery and Food)",
                    mapping_confidence="high",
                    revenue_share=1.0,
                    disclosure_level="geography",
                )
            ],
        }
    )

    assert result["ok"] is False
    assert result["status"] == "segment_mapping_blocked"
    assert result["accepted_mcp_inputs"]["segments"] is None
    assert any("Geographic disclosure" in limitation for limitation in result["limitations"])


def test_segment_economics_acceptance_fixture_cases_match_phase_4_policy():
    cases = json.loads((FIXTURES / "segment_economics_acceptance_cases.json").read_text())["cases"]

    for case in cases:
        result = validate_segment_economics(case["artifact"])
        expected = case["expected"]
        assert result["status"] == expected["status"], case["name"]
        assert result["quality"] == expected["quality"], case["name"]
        assert len(result["accepted_mcp_inputs"]["sector_overrides"]) == expected["sector_override_count"], case["name"]
        assert len(result["report_only_facts"]) == expected["report_only_fact_count"], case["name"]
        if "limitations_include" in expected:
            assert any(expected["limitations_include"] in limitation for limitation in result["limitations"]), case["name"]
