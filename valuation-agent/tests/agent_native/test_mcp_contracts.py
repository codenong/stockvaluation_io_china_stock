import copy
import json
from pathlib import Path

import pytest

from valuation_agent.mcp_tools import MCPToolRegistry, prospectus_segment_review
from valuation_agent.mcp_server import MCPJSONRPCServer
from valuation_agent.service_client import (
    NonJsonServiceResponse,
    ServiceHTTPError,
    ServiceUnavailable,
    ValuationServiceClient,
)


def _valuation_payload():
    return {
        "companyName": "Microsoft Corporation",
        "currency": "USD",
        "stockCurrency": "USD",
        "primaryModel": "FCFF",
        "growthPattern": "TWO_STAGE",
        "projectionYears": 10,
        "companyDTO": {
            "estimatedValuePerShare": 412.34,
            "price": 390.0,
            "valueOfEquity": 3_000_000_000_000.0,
            "numberOfShares": 7_300_000_000.0,
        },
        "financialDTO": {
            "intrinsicValue": 412.34,
            "revenueGrowthRate": [None, 10.0, 8.0, 7.0, 6.0],
            "ebitOperatingMargin": [42.0, 43.0, 44.0, 45.0, 45.0],
            "salesToCapitalRatio": [None, 2.4, 2.4, 2.2],
            "costOfCapital": [8.5, 8.4, 8.3],
        },
        "terminalValueDTO": {
            "growthRate": 3.0,
            "costOfCapital": 8.0,
        },
        "assumptionTransparency": {
            "accountingAndClaims": {
                "schemaVersion": "accounting_and_claims.v1",
                "rdCapitalization": {
                    "status": "source_required",
                    "modelTreatment": "report_only",
                    "reason": "Multi-year R&D history and amortization policy were not source-backed.",
                },
                "sbcDilution": {
                    "status": "blocked_report_only",
                    "modelTreatment": "report_only",
                },
                "leases": {
                    "status": "zero_by_default",
                    "modelTreatment": "report_only",
                },
                "optionsWarrants": {
                    "status": "zero_by_default",
                    "modelTreatment": "service_calculated_when_inputs_available",
                },
                "nolTax": {
                    "status": "source_required",
                    "modelTreatment": "scenario_only",
                },
                "cash": {
                    "status": "returned",
                    "modelTreatment": "service_returned",
                },
                "debt": {
                    "status": "returned",
                    "modelTreatment": "service_returned",
                },
                "shareCount": {
                    "status": "returned",
                    "modelTreatment": "service_returned",
                },
            },
            "discountRate": {
                "riskFreeRate": 4.5,
                "initialCostOfCapital": 8.5,
                "terminalCostOfCapital": 8.0,
                "riskFreeRateSource": "valuation-service",
            },
            "operatingAssumptions": {
                "revenueGrowthRateYears2To5": 7.0,
                "operatingMarginNextYear": 41.0,
                "targetOperatingMargin": 45.0,
                "convergenceYearMargin": 5.0,
                "salesToCapitalYears1To5": 2.4,
                "salesToCapitalYears6To10": 2.1,
                "revenueGrowthRationale": "Historical growth and industry anchor.",
            },
            "growthAnchor": {
                "entity": "software",
                "entityDisplay": "Software",
                "region": "United States",
                "year": 2026,
                "confidenceScore": 0.82,
                "p25": 0.04,
                "p50": 0.08,
                "p75": 0.12,
                "source": "Damodaran historical growth",
            },
            "notes": ["Yahoo Finance coverage is limited."],
        },
    }


PROSPECTUS_URL = "https://www.sec.gov/Archives/edgar/data/1819994/000119312526123456/d123456ds1a.htm"


def _prospectus_packet(review_status="review_required"):
    return {
        "schemaVersion": "prospectus_financial_packet.v1",
        "company": {
            "legalName": "Space Exploration Technologies Corp.",
            "tickerOrExpectedSymbol": "SPACE",
        },
        "filing": {
            "formType": "S-1/A",
            "cik": "1819994",
            "accessionNumber": "0001193125-26-123456",
            "filingDate": "2026-05-15",
        },
        "sourceUrl": PROSPECTUS_URL,
        "financials": {
            "revenue": [
                {
                    "metric": "revenue",
                    "label": "Revenue",
                    "periodEnd": "2025-12-31",
                    "value": 8_700_000_000.0,
                    "unit": "USD",
                    "scale": "actual",
                    "statement": "income_statement",
                    "sourceTableTitle": "Consolidated Statements of Operations",
                    "sourceRowLabel": "Revenue",
                }
            ],
            "operatingIncome": [
                {
                    "metric": "operating_income",
                    "label": "Income from operations",
                    "periodEnd": "2025-12-31",
                    "value": 970_000_000.0,
                    "unit": "USD",
                    "scale": "actual",
                    "statement": "income_statement",
                    "sourceTableTitle": "Consolidated Statements of Operations",
                    "sourceRowLabel": "Income from operations",
                }
            ],
        },
        "offering": {
            "offeringPrice": {
                "metric": "offering_price",
                "label": "Initial public offering price",
                "value": 97.0,
                "unit": "USD/share",
                "sourceTableTitle": "Prospectus summary",
                "sourceRowLabel": "Initial public offering price",
            }
        },
        "shareCounts": [
            {
                "basis": "pro_forma_as_adjusted",
                "label": "Shares outstanding after this offering",
                "shares": 2_120_000_000.0,
                "sourceTableTitle": "Capitalization",
                "sourceRowLabel": "Shares outstanding after this offering",
            }
        ],
        "segments": [],
        "segmentCandidateTables": [
            {
                "title": "Segment revenue",
                "currency": "USD",
                "scale": "actual",
                "columns": ["Year Ended December 31, 2025"],
                "rows": [
                    {
                        "label": "Launch and space services",
                        "cells": [{"rawValue": "$ 4,900", "normalizedValue": 4_900_000_000.0}],
                    },
                    {
                        "label": "Connectivity",
                        "cells": [{"rawValue": "$ 3,700", "normalizedValue": 3_700_000_000.0}],
                    },
                ],
                "sourceAnchor": "table-segment-revenue",
            }
        ],
        "sourceProvenance": {
            "sourceClass": "primary_filing",
            "provider": "sec-edgar-prospectus",
            "sourceDate": "2026-05-15",
            "periodEnd": "2025-12-31",
            "retrievalStatus": "retrieved",
            "crossCheckStatus": "not_applicable",
            "sourcePolicyStatus": "prospectus_extracted",
            "warnings": [],
            "dataQualityWarnings": [],
        },
        "reviewStatus": review_status,
    }


def _prospectus_extraction_payload():
    return {
        "status": "requires_review",
        "packet": _prospectus_packet(),
        "sourceQualityGate": {
            "status": "requires_user_decision",
            "reason": "prospectus_extraction_review_required",
            "primarySourceExpected": True,
            "fallbackSourceAvailable": False,
            "crossCheckRequired": True,
            "allowedActions": ["approve_extracted_packet", "correct_packet", "add_sources", "stop"],
        },
    }


def _prospectus_valuation_payload():
    return {
        "status": "valued",
        "priceBasis": "offering_price",
        "valuationBasisStatus": "clean_pro_forma_basis",
        "valuationCaseStatus": "clean_valuation_case",
        "proceedsBasis": "net_proceeds_disclosed",
        "valuationBasisWarnings": [],
        "packet": _prospectus_packet("reviewed"),
        "sourceProvenance": _prospectus_packet()["sourceProvenance"],
        "sourceQualityGate": {
            "status": "not_required",
            "reason": "prospectus_packet_reviewed",
            "primarySourceExpected": True,
            "fallbackSourceAvailable": False,
            "crossCheckRequired": False,
            "allowedActions": [],
        },
        "valuation": _valuation_payload(),
    }


def _segment_mapping_proposal_payload():
    return {
        "proposals": [
            {
                "name": "Pharmaceuticals",
                "revenueAmount": 600.0,
                "revenueWeight": 0.6,
                "sectorKey": "drug-manufacturers-general",
                "mappedIndustry": "Drugs (Pharmaceutical)",
                "mappingConfidence": "high",
                "mappingScore": 0.82,
                "mappingScoreMargin": 0.32,
                "rationale": "Matched pharmaceutical synonyms for drug-manufacturers-general.",
                "components": ["Prescription drugs"],
                "rowRole": "reportable_segment",
                "warnings": [],
            },
            {
                "name": "Other",
                "revenueAmount": 120.0,
                "revenueWeight": 0.12,
                "sectorKey": None,
                "mappedIndustry": None,
                "mappingConfidence": "unmapped",
                "mappingScore": 0.0,
                "mappingScoreMargin": 0.0,
                "rationale": "Residual bucket left unmapped for review.",
                "components": [],
                "rowRole": "residual",
                "warnings": ["residual bucket; materiality review required"],
            },
        ],
        "revenueCoveragePct": 72.0,
        "materialGap": True,
        "warnings": ["residual bucket; materiality review required"],
    }


class FakeClient:
    def __init__(self, payload=None, prospectus_extraction=None, prospectus_valuation=None, segment_mapping_proposal=None):
        self.payload = payload or _valuation_payload()
        self.prospectus_extraction = prospectus_extraction or _prospectus_extraction_payload()
        self.prospectus_valuation = prospectus_valuation or _prospectus_valuation_payload()
        self.segment_mapping_proposal = segment_mapping_proposal or _segment_mapping_proposal_payload()
        self.calls = []

    def health(self):
        return {"status": "UP"}

    def value_ticker(self, ticker, overrides=None):
        self.calls.append((ticker, overrides or {}))
        return self.payload

    def extract_prospectus(self, filing_url, expected_company=None, expected_symbol=None):
        self.calls.append(("extract_prospectus", filing_url, expected_company, expected_symbol))
        return self.prospectus_extraction

    def value_prospectus(self, packet, scenario=None):
        self.calls.append(("value_prospectus", packet, scenario))
        return self.prospectus_valuation

    def propose_segment_mappings(self, segments, consolidated_revenue=None):
        self.calls.append(("propose_segment_mappings", segments, consolidated_revenue))
        return self.segment_mapping_proposal


def _valid_evidence_packet(**item_overrides):
    evidence_item = {
        "driver": "revenue_growth",
        "source_title": "FY annual report",
        "source_url": "https://example.com/msft-annual-report",
        "source_date": "2026-06-30",
        "evidence_summary": "Commercial cloud revenue increased 21% year over year.",
        "direction": "supports higher assumption",
        "confidence": "high",
        "assumption_implication": "Supports a modestly higher revenue CAGR than the mechanical baseline.",
        "allowed_to_affect_autonomous_recalculation": True,
        "model_action": "governed assumption change",
    }
    evidence_item.update(item_overrides)
    return {
        "ticker": "MSFT",
        "company": "Microsoft Corporation",
        "run_mode": "full_researched",
        "source_families": [
            {
                "family": "annual_report",
                "status": "checked",
                "source_title": "FY annual report",
                "source_url": "https://example.com/msft-annual-report",
                "source_date": "2026-06-30",
            }
        ],
        "sources_checked": [
            {
                "source_title": "FY annual report",
                "source_url": "https://example.com/msft-annual-report",
                "source_date": "2026-06-30",
                "status": "checked",
                "source_type": "annual_report",
                "used": True,
            }
        ],
        "evidence_items": [evidence_item],
        "conflicts_or_uncertainties": [],
        "data_gaps": [],
    }


def _valid_segment_economics_artifact():
    return {
        "schema_version": "segment_economics.v1",
        "ticker": "MSFT",
        "company": "Microsoft Corporation",
        "run_mode": "full_researched",
        "segments": [
            {
                "segment_name": "Cloud software",
                "sector_key": "software-infrastructure",
                "mapped_industry": "Software (System & Application)",
                "mapping_confidence": "high",
                "revenue_share": 1.0,
                "source_name": "FY annual report segment note",
                "source_url": "https://example.com/msft-annual-report",
                "source_date": "2026-06-30",
                "source_class": "primary_filing",
                "provider": "sec-filing",
                "retrieval_status": "retrieved",
                "disclosure_level": "reportable_segment",
                "drivers": {
                    "margin": {
                        "evidence_ref": {
                            "driver": "operating_margin",
                            "source_url": "https://example.com/msft-annual-report",
                            "source_date": "2026-06-30",
                        },
                        "source_class": "primary_filing",
                        "provider": "sec-filing",
                        "retrieval_status": "retrieved",
                        "disclosure_level": "reportable_segment",
                        "model_action": "governed_sector_override",
                        "sector_override": {
                            "sector_key": "software-infrastructure",
                            "parameter": "operating_margin",
                            "value": 36.0,
                            "unit": "percent",
                            "adjustment_type": "absolute",
                            "timeframe": "both",
                        },
                    }
                },
            }
        ],
        "evidence_packet": _valid_evidence_packet(
            driver="operating_margin",
            evidence_summary="Cloud segment operating income expanded year over year.",
            assumption_implication="Supports a governed Cloud margin override.",
        ),
    }


def test_health_includes_skill_metadata_without_removing_existing_fields(tmp_path):
    from valuation_agent.installer import AgentInstaller, skill_bundle_version

    home = tmp_path / "home"
    AgentInstaller(home=home).install_skills(["claude"])
    registry = MCPToolRegistry(FakeClient(), home=home)

    result = registry.call("stockvaluation.health", {})
    payload = result["structuredContent"]

    assert payload["ok"] is True
    assert payload["service"]["status"] == "UP"
    assert payload["mcp"]["name"] == "valuation-agent"
    assert payload["policy"]["educationalUseOnly"] is True
    skill = payload["skill"]
    assert skill["installedVersion"] == skill_bundle_version()
    assert skill["syncStatus"] == "in_sync"
    assert skill["installs"]["claude"]["status"] == "in_sync"
    assert skill["installs"]["codex"]["status"] == "not_installed"


def test_health_skill_metadata_reports_drift_and_not_installed(tmp_path):
    from valuation_agent.installer import AgentInstaller

    home = tmp_path / "home"
    registry = MCPToolRegistry(FakeClient(), home=home)
    payload = registry.call("stockvaluation.health", {})["structuredContent"]
    assert payload["skill"]["syncStatus"] == "not_installed"
    assert payload["skill"]["installedVersion"] == "unknown"

    AgentInstaller(home=home).install_skills(["claude"])
    skill_md = home / ".claude" / "skills" / "stockvaluation-io" / "SKILL.md"
    skill_md.write_text(skill_md.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
    payload = registry.call("stockvaluation.health", {})["structuredContent"]
    assert payload["skill"]["syncStatus"] == "drifted"


def test_mcp_tools_list_has_required_stockvaluation_contracts():
    registry = MCPToolRegistry(FakeClient())

    tools = registry.list_tools()
    names = {tool["name"] for tool in tools}

    assert names == {
        "stockvaluation.health",
        "stockvaluation.value_ticker",
        "stockvaluation.researched_baseline",
        "stockvaluation.propose_segment_mappings",
        "stockvaluation.extract_prospectus",
        "stockvaluation.value_prospectus",
        "stockvaluation.plan_guided_questions",
        "stockvaluation.apply_guided_answers",
        "stockvaluation.recalculate",
        "stockvaluation.get_assumptions",
        "stockvaluation.get_growth_anchor",
        "stockvaluation.get_reference_data_status",
        "stockvaluation.explain_failure",
    }
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert tool["outputSchema"]["type"] == "object"


def test_prospectus_tools_are_read_only_and_schema_bounded():
    tools = {tool["name"]: tool for tool in MCPToolRegistry(FakeClient()).list_tools()}

    extract = tools["stockvaluation.extract_prospectus"]
    assert extract["annotations"]["readOnlyHint"] is True
    assert extract["inputSchema"]["required"] == ["filing_url"]
    assert extract["inputSchema"]["properties"]["filing_url"]["pattern"].startswith("^https://www\\.sec\\.gov/Archives/")
    assert extract["inputSchema"]["properties"]["expected_company"]["type"] == "string"

    value = tools["stockvaluation.value_prospectus"]
    assert value["annotations"]["readOnlyHint"] is True
    assert "required" not in value["inputSchema"]
    assert "anyOf" not in value["inputSchema"]
    assert value["inputSchema"]["properties"]["packet"]["type"] == "object"
    assert value["inputSchema"]["properties"]["packet"]["additionalProperties"] is True
    assert value["inputSchema"]["properties"]["review_reference"]["type"] == "string"
    assert value["inputSchema"]["properties"]["scenario"]["type"] == "object"
    assert value["inputSchema"]["properties"]["scenario"]["additionalProperties"] is True


def test_propose_segment_mappings_calls_java_service_and_returns_review_payload():
    client = FakeClient()
    registry = MCPToolRegistry(client)
    segments = [
        {
            "name": "Pharmaceuticals",
            "revenueAmount": 600.0,
            "components": ["Prescription drugs"],
            "rowRole": "reportable_segment",
        },
        {
            "name": "Other",
            "revenueAmount": 120.0,
            "rowRole": "residual",
        },
    ]

    result = registry.call(
        "stockvaluation.propose_segment_mappings",
        {"segments": segments, "consolidated_revenue": 1_000.0},
    )

    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["tool"] == "stockvaluation.propose_segment_mappings"
    assert client.calls == [("propose_segment_mappings", segments, 1_000.0)]
    review = structured["segmentReview"]
    assert review["status"] == "proposed_mapping_ready"
    assert review["revenueCoveragePct"] == 72.0
    assert review["materialGap"] is True
    assert review["proposedMappings"][0]["sectorKey"] == "drug-manufacturers-general"
    assert review["proposedMappings"][0]["rationale"].startswith("Matched")
    assert review["unmappedRows"][0]["name"] == "Other"
    assert review["allowedActions"] == ["approve_mappings", "correct_mapping", "reject_mapping", "leave_unmapped"]


@pytest.mark.parametrize(
    "filing_url",
    [
        "https://example.com/Archives/edgar/data/1819994/000119312526123456/d123456ds1a.htm",
        "<html><body><table><tr><td>Revenue</td></tr></table></body></html>",
    ],
)
def test_extract_prospectus_rejects_non_sec_urls_and_raw_html_without_service_call(filing_url):
    client = FakeClient()
    result = MCPToolRegistry(client).call("stockvaluation.extract_prospectus", {"filing_url": filing_url})

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "INVALID_PROSPECTUS_URL"
    assert result["structuredContent"]["failureCategory"] == "invalid_prospectus_source"
    assert "SEC EDGAR Archives HTML URL" in result["structuredContent"]["error"]["message"]
    assert client.calls == []


def test_extract_prospectus_returns_review_required_packet_with_source_gate():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.extract_prospectus",
        {
            "filing_url": PROSPECTUS_URL,
            "expected_company": "Space Exploration Technologies Corp.",
            "expected_symbol": "SPACE",
        },
    )

    assert result["isError"] is False
    assert client.calls == [
        (
            "extract_prospectus",
            PROSPECTUS_URL,
            "Space Exploration Technologies Corp.",
            "SPACE",
        )
    ]
    structured = result["structuredContent"]
    assert structured["prospectus"]["status"] == "requires_review"
    assert structured["prospectus"]["reviewStatus"] == "review_required"
    assert structured["prospectus"]["reviewReference"].startswith("prospectus_")
    assert structured["prospectus"]["packet"]["reviewStatus"] == "review_required"
    candidate_tables = structured["prospectus"]["packet"]["segmentCandidateTables"]
    assert candidate_tables[0]["rows"][0]["label"] == "Launch and space services"
    assert candidate_tables[0]["rows"][1]["cells"][0]["normalizedValue"] == 3_700_000_000.0
    assert structured["sourceQualityGate"]["reason"] == "prospectus_extraction_review_required"
    assert structured["provenance"]["sourceClass"] == "primary_filing"
    assert structured["provenance"]["provider"] == "sec-edgar-prospectus"
    visible_text = result["content"][0]["text"]
    assert "requires review" in visible_text.lower()
    assert "structuredContent" in visible_text
    assert '"packet"' not in visible_text
    assert "financials" not in visible_text
    assert len(visible_text) < 600


def test_prospectus_segment_review_summarizes_proposed_mappings():
    packet = {
        "segments": [
            {
                "segmentName": "Pharmaceuticals",
                "revenueAmount": 600.0,
                "revenueWeight": 0.6,
                "sectorKey": "drug-manufacturers-general",
                "mappedIndustry": "Drugs (Pharmaceutical)",
                "mappingConfidence": "high",
                "mappingScore": 0.82,
                "rationale": "Matched pharmaceutical synonyms for drug-manufacturers-general.",
                "components": ["Prescription drugs"],
                "rowRole": "reportable_segment",
                "warnings": [],
            },
            {
                "segmentName": "Other",
                "revenueAmount": 120.0,
                "revenueWeight": 0.12,
                "mappingConfidence": "unmapped",
                "mappingScore": 0.0,
                "rationale": "Residual bucket left unmapped for review.",
                "rowRole": "residual",
                "warnings": ["residual bucket; materiality review required"],
            }
        ],
        "segmentCandidateTables": [{"title": "Segment revenue"}],
    }

    review = prospectus_segment_review(packet)

    assert review["status"] == "proposed_mapping_ready"
    assert review["candidateTableCount"] == 1
    assert review["revenueCoveragePct"] == 72.0
    assert review["materialGap"] is True
    assert review["allowedActions"] == ["approve_mappings", "correct_mapping", "reject_mapping", "leave_unmapped"]
    assert review["warnings"] == ["residual bucket; materiality review required"]
    assert review["proposedMappings"] == [
        {
            "name": "Pharmaceuticals",
            "revenueAmount": 600.0,
            "revenueWeight": 0.6,
            "sectorKey": "drug-manufacturers-general",
            "mappedIndustry": "Drugs (Pharmaceutical)",
            "mappingConfidence": "high",
            "mappingScore": 0.82,
            "rationale": "Matched pharmaceutical synonyms for drug-manufacturers-general.",
            "components": ["Prescription drugs"],
            "rowRole": "reportable_segment",
            "warnings": [],
        }
    ]
    assert review["unmappedRows"] == [
        {
            "name": "Other",
            "revenueAmount": 120.0,
            "revenueWeight": 0.12,
            "rowRole": "residual",
            "mappingConfidence": "unmapped",
            "mappingScore": 0.0,
            "rationale": "Residual bucket left unmapped for review.",
            "warnings": ["residual bucket; materiality review required"],
        }
    ]


def test_plan_guided_questions_prioritizes_low_confidence_material_segments():
    result = MCPToolRegistry(FakeClient()).call(
        "stockvaluation.plan_guided_questions",
        {
            "company": "Example Therapeutics",
            "workflow_type": "prospectus",
            "prospectus_recalculate_supported": True,
            "segments": [
                {
                    "segmentName": "Platform",
                    "revenueAmount": 300.0,
                    "revenueWeight": 0.3,
                    "sectorKey": "software-infrastructure",
                    "mappedIndustry": "Software (System & Application)",
                    "mappingConfidence": "low",
                    "mappingScore": 0.35,
                },
                {
                    "segmentName": "Pharmaceuticals",
                    "revenueAmount": 700.0,
                    "revenueWeight": 0.7,
                    "sectorKey": "drug-manufacturers-general",
                    "mappedIndustry": "Drugs (Pharmaceutical)",
                    "mappingConfidence": "high",
                    "mappingScore": 0.86,
                },
            ],
        },
    )

    assert result["isError"] is False
    questions = result["structuredContent"]["guidedQuestionPlan"]["questions"]
    assert questions[0]["driver"] == "business_definition"
    assert questions[0]["priority"] == "P1"
    assert "Platform" in questions[0]["evidence_basis"]
    mapping = questions[0]["hidden_model_mapping"]
    assert mapping["supported_override_field"] == "segments"
    assert mapping["candidate_value"][0]["name"] == "Platform"


def test_value_prospectus_can_use_review_reference_without_copying_large_packet():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    extract = registry.call("stockvaluation.extract_prospectus", {"filing_url": PROSPECTUS_URL})
    review_reference = extract["structuredContent"]["prospectus"]["reviewReference"]
    result = registry.call(
        "stockvaluation.value_prospectus",
        {"review_reference": review_reference, "review_status": "reviewed"},
    )

    assert result["isError"] is False
    assert len(client.calls) == 2
    name, packet, scenario = client.calls[1]
    assert name == "value_prospectus"
    assert scenario is None
    assert packet["reviewStatus"] == "reviewed"
    assert packet["financials"]["revenue"][0]["value"] == 8_700_000_000.0


def test_value_prospectus_review_reference_requires_reviewed_status():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    extract = registry.call("stockvaluation.extract_prospectus", {"filing_url": PROSPECTUS_URL})
    review_reference = extract["structuredContent"]["prospectus"]["reviewReference"]
    result = registry.call(
        "stockvaluation.value_prospectus",
        {"review_reference": review_reference},
    )

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "PROSPECTUS_REVIEW_REQUIRED"
    assert client.calls == [("extract_prospectus", PROSPECTUS_URL, None, None)]


def test_value_prospectus_accepts_extract_payload_wrapper_after_review():
    client = FakeClient()
    registry = MCPToolRegistry(client)
    extract = registry.call("stockvaluation.extract_prospectus", {"filing_url": PROSPECTUS_URL})
    wrapped = extract["structuredContent"]
    wrapped["prospectus"]["packet"]["reviewStatus"] = "reviewed"

    result = registry.call(
        "stockvaluation.value_prospectus",
        {"packet": wrapped},
    )

    assert result["isError"] is False
    assert client.calls[1][0] == "value_prospectus"
    assert client.calls[1][1]["reviewStatus"] == "reviewed"


def test_value_prospectus_requires_reviewed_packet_before_service_call():
    client = FakeClient()
    result = MCPToolRegistry(client).call(
        "stockvaluation.value_prospectus",
        {"packet": _prospectus_packet("review_required")},
    )

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "PROSPECTUS_REVIEW_REQUIRED"
    assert result["structuredContent"]["failureCategory"] == "prospectus_review_required"
    assert "reviewed" in result["structuredContent"]["error"]["message"].lower()
    assert client.calls == []


def test_value_prospectus_uses_reviewed_packet_and_offering_price_basis():
    client = FakeClient()
    reviewed_packet = _prospectus_packet("reviewed")

    result = MCPToolRegistry(client).call(
        "stockvaluation.value_prospectus",
        {"packet": reviewed_packet},
    )

    assert result["isError"] is False
    assert client.calls == [("value_prospectus", reviewed_packet, None)]
    structured = result["structuredContent"]
    assert structured["tool"] == "stockvaluation.value_prospectus"
    assert structured["priceBasis"] == "offering_price"
    assert structured["valuationBasisStatus"] == "clean_pro_forma_basis"
    assert structured["valuationCaseStatus"] == "clean_valuation_case"
    assert structured["prospectus"]["reviewStatus"] == "reviewed"
    assert structured["dcf"]["estimatedValuePerShare"] == 412.34
    assert structured["provenance"]["sourceClass"] == "primary_filing"
    assert structured["provenance"]["provider"] == "sec-edgar-prospectus"
    assert structured["sourceQualityGate"]["reason"] == "prospectus_packet_reviewed"
    assert "Yahoo Finance" not in json.dumps(structured)
    visible_text = result["content"][0]["text"]
    assert "offering_price" in visible_text
    assert "structuredContent" in visible_text
    assert len(visible_text) < 650


def test_value_prospectus_passes_explicit_scenario_to_service():
    scenario = {
        "net_proceeds": 75_000_000_000.0,
        "rd_capitalization": True,
        "rd_amortization_period_years": 5,
        "segments": [
            {"name": "Launch", "target_revenue": 40_000_000_000.0},
            {"name": "Starlink / Connectivity", "target_revenue": 120_000_000_000.0},
            {"name": "AI", "target_revenue": 160_000_000_000.0},
            {"name": "Other or expansion revenue", "base_revenue": 0.0, "target_revenue": 100_000_000_000.0},
        ],
    }
    payload = _prospectus_valuation_payload()
    payload["scenario"] = scenario
    client = FakeClient(prospectus_valuation=payload)
    reviewed_packet = _prospectus_packet("reviewed")

    result = MCPToolRegistry(client).call(
        "stockvaluation.value_prospectus",
        {"packet": reviewed_packet, "scenario": scenario},
    )

    assert result["isError"] is False
    assert client.calls == [("value_prospectus", reviewed_packet, scenario)]
    assert result["structuredContent"]["scenario"] == scenario


def test_value_prospectus_challenged_basis_hides_clean_value_language():
    payload = _prospectus_valuation_payload()
    payload["valuationBasisStatus"] = "pro_forma_cash_missing"
    payload["valuationCaseStatus"] = "challenged_valuation_case"
    payload["proceedsBasis"] = None
    payload["valuationBasisWarnings"] = [
        "post-offering shares require pro-forma cash, but net offering proceeds were not extracted."
    ]
    payload["valuation"]["assumptionTransparency"]["valuationBasisStatus"] = "pro_forma_cash_missing"
    payload["valuation"]["assumptionTransparency"]["valuationCaseStatus"] = "challenged_valuation_case"
    payload["valuation"]["assumptionTransparency"]["baselineUseStatus"] = "challenged_baseline"
    payload["valuation"]["assumptionTransparency"]["baselineWarnings"] = payload["valuationBasisWarnings"]
    client = FakeClient(prospectus_valuation=payload)
    reviewed_packet = _prospectus_packet("reviewed")

    result = MCPToolRegistry(client).call(
        "stockvaluation.value_prospectus",
        {"packet": reviewed_packet},
    )

    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["valuationBasisStatus"] == "pro_forma_cash_missing"
    assert structured["valuationCaseStatus"] == "challenged_valuation_case"
    assert structured["baseline"]["valuationBasisStatus"] == "pro_forma_cash_missing"
    assert structured["baseline"]["valuationCaseStatus"] == "challenged_valuation_case"
    visible_text = result["content"][0]["text"]
    assert "Estimated value/share" not in visible_text
    assert "Mechanical diagnostic value is about $412.34/share" in visible_text
    assert "No clean prospectus valuation yet" in visible_text
    assert "A story scenario is required" in visible_text
    assert "pro_forma_cash_missing" in visible_text


def test_value_prospectus_clean_basis_but_challenged_case_marks_dcf_diagnostic_only():
    payload = _prospectus_valuation_payload()
    payload["valuationBasisStatus"] = "clean_pro_forma_basis"
    payload["valuationCaseStatus"] = "challenged_valuation_case"
    payload["proceedsBasis"] = "net_proceeds_disclosed_base_offering"
    payload["valuationBasisWarnings"] = [
        "Material unmapped prospectus segment revenue requires challenged baseline status."
    ]
    payload["valuation"]["assumptionTransparency"]["valuationBasisStatus"] = "clean_pro_forma_basis"
    payload["valuation"]["assumptionTransparency"]["valuationCaseStatus"] = "challenged_valuation_case"
    payload["valuation"]["assumptionTransparency"]["baselineUseStatus"] = "challenged_baseline"
    payload["valuation"]["assumptionTransparency"]["baselineWarnings"] = payload["valuationBasisWarnings"]
    client = FakeClient(prospectus_valuation=payload)
    reviewed_packet = _prospectus_packet("reviewed")

    result = MCPToolRegistry(client).call(
        "stockvaluation.value_prospectus",
        {"packet": reviewed_packet},
    )

    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["valuationBasisStatus"] == "clean_pro_forma_basis"
    assert structured["valuationCaseStatus"] == "challenged_valuation_case"
    assert structured["dcf"]["estimatedValuePerShare"] == 412.34
    assert structured["dcf"]["valueVisibility"] == "diagnostic_only"
    assert structured["dcf"]["caseStatus"] == "challenged_diagnostic"
    assert "clean user-facing intrinsic value" in structured["dcf"]["displayPolicy"]
    visible_text = result["content"][0]["text"]
    assert "Estimated value/share" not in visible_text
    assert "Mechanical diagnostic value is about $412.34/share" in visible_text
    assert "No clean prospectus valuation yet" in visible_text
    assert "A story scenario is required" in visible_text
    assert "clean_pro_forma_basis" in visible_text


def test_value_prospectus_uses_recommended_intrinsic_value_as_challenged_diagnostic():
    payload = _prospectus_valuation_payload()
    payload["valuationBasisStatus"] = "gross_proceeds_estimate_only"
    payload["valuationCaseStatus"] = "challenged_valuation_case"
    payload["proceedsBasis"] = "gross_proceeds_estimate_only"
    payload["valuation"]["recommendedIntrinsicValue"] = 5.871407929880455
    payload["valuation"]["companyDTO"]["estimatedValuePerShare"] = None
    payload["valuation"]["financialDTO"]["intrinsicValue"] = None
    payload["valuation"]["assumptionTransparency"]["valuationBasisStatus"] = "gross_proceeds_estimate_only"
    payload["valuation"]["assumptionTransparency"]["valuationCaseStatus"] = "challenged_valuation_case"
    payload["valuation"]["assumptionTransparency"]["baselineUseStatus"] = "challenged_baseline"
    client = FakeClient(prospectus_valuation=payload)

    result = MCPToolRegistry(client).call(
        "stockvaluation.value_prospectus",
        {"packet": _prospectus_packet("reviewed")},
    )

    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["dcf"]["estimatedValuePerShare"] == 5.871407929880455
    assert structured["dcf"]["valueVisibility"] == "diagnostic_only"
    assert structured["dcf"]["caseStatus"] == "challenged_diagnostic"
    assert "challenged diagnostic value" in structured["dcf"]["displayPolicy"]
    visible_text = result["content"][0]["text"]
    assert "5.871407929880455" not in visible_text
    assert "Mechanical diagnostic value is about $5.87/share" in visible_text
    assert "No clean prospectus valuation yet" in visible_text


def test_value_prospectus_challenged_text_names_story_scenario_requirement():
    payload = _prospectus_valuation_payload()
    payload["valuationBasisStatus"] = "clean_pro_forma_basis"
    payload["valuationCaseStatus"] = "challenged_valuation_case"
    payload["valuation"]["companyName"] = "Space Exploration Technologies Corp."
    payload["valuation"]["companyDTO"]["estimatedValuePerShare"] = 11.61
    payload["valuation"]["financialDTO"]["intrinsicValue"] = 11.61
    payload["valuation"]["assumptionTransparency"]["valuationBasisStatus"] = "clean_pro_forma_basis"
    payload["valuation"]["assumptionTransparency"]["valuationCaseStatus"] = "challenged_valuation_case"
    payload["valuation"]["assumptionTransparency"]["baselineUseStatus"] = "challenged_baseline"
    client = FakeClient(prospectus_valuation=payload)

    result = MCPToolRegistry(client).call(
        "stockvaluation.value_prospectus",
        {"packet": _prospectus_packet("reviewed")},
    )

    visible_text = result["content"][0]["text"]
    assert "No clean prospectus valuation yet" in visible_text
    assert "Mechanical diagnostic value is about $11.61/share" in visible_text
    assert "A story scenario is required" in visible_text
    assert "intrinsic" not in visible_text.lower()


def test_service_client_posts_prospectus_extract_to_api_v1_endpoint(monkeypatch):
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"data": _prospectus_extraction_payload()}).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("valuation_agent.service_client.request.urlopen", fake_urlopen)

    result = ValuationServiceClient(timeout=7).extract_prospectus(
        PROSPECTUS_URL,
        expected_company="Space Exploration Technologies Corp.",
        expected_symbol="SPACE",
    )

    assert captured["url"] == "http://localhost:8081/api/v1/prospectus/extract"
    assert captured["body"] == {
        "filing_url": PROSPECTUS_URL,
        "expected_company": "Space Exploration Technologies Corp.",
        "expected_symbol": "SPACE",
    }
    assert captured["timeout"] == 7
    assert result["status"] == "requires_review"


def test_service_client_posts_reviewed_prospectus_packet_to_valuation_endpoint(monkeypatch):
    captured = {}
    reviewed_packet = _prospectus_packet("reviewed")

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"data": _prospectus_valuation_payload()}).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return Response()

    monkeypatch.setattr("valuation_agent.service_client.request.urlopen", fake_urlopen)

    result = ValuationServiceClient(timeout=7).value_prospectus(reviewed_packet)

    assert captured["url"] == "http://localhost:8081/api/v1/prospectus/valuation"
    assert captured["body"] == {"packet": reviewed_packet}
    assert result["priceBasis"] == "offering_price"


def test_service_client_posts_prospectus_scenario_to_valuation_endpoint(monkeypatch):
    captured = {}
    reviewed_packet = _prospectus_packet("reviewed")
    scenario = {"net_proceeds": 75_000_000_000.0, "rd_capitalization": True}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"data": _prospectus_valuation_payload()}).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return Response()

    monkeypatch.setattr("valuation_agent.service_client.request.urlopen", fake_urlopen)

    result = ValuationServiceClient(timeout=7).value_prospectus(reviewed_packet, scenario)

    assert captured["url"] == "http://localhost:8081/api/v1/prospectus/valuation"
    assert captured["body"] == {"packet": reviewed_packet, "scenario": scenario}
    assert result["priceBasis"] == "offering_price"


def test_service_client_posts_segment_mapping_proposals_to_api_v1_endpoint(monkeypatch):
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"data": _segment_mapping_proposal_payload()}).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return Response()

    monkeypatch.setattr("valuation_agent.service_client.request.urlopen", fake_urlopen)

    segments = [{"name": "Pharmaceuticals", "revenueAmount": 600.0}]
    result = ValuationServiceClient(timeout=7).propose_segment_mappings(segments, 1_000.0)

    assert captured["url"] == "http://localhost:8081/api/v1/segments/propose-mappings"
    assert captured["timeout"] == 7
    assert captured["body"] == {"segments": segments, "consolidatedRevenue": 1_000.0}
    assert result["revenueCoveragePct"] == 72.0


def test_jsonrpc_mcp_server_lists_and_calls_tools():
    server = MCPJSONRPCServer(MCPToolRegistry(FakeClient()))

    initialized = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    listed = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    called = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "stockvaluation.value_ticker", "arguments": {"ticker": "MSFT"}},
        }
    )

    assert initialized["result"]["capabilities"]["tools"]["listChanged"] is False
    assert listed["result"]["tools"][0]["name"] == "stockvaluation.health"
    assert called["result"]["structuredContent"]["ticker"] == "MSFT"
    assert called["result"]["isError"] is False


def test_value_ticker_preserves_service_accounting_and_claims_status():
    registry = MCPToolRegistry(FakeClient())

    result = registry.call(
        "stockvaluation.value_ticker",
        {"ticker": "MSFT"},
    )

    assert result["isError"] is False
    structured = result["structuredContent"]
    accounting = structured["accountingAndClaims"]
    assert accounting["schemaVersion"] == "accounting_and_claims.v1"
    assert set(accounting) >= {
        "rdCapitalization",
        "sbcDilution",
        "leases",
        "optionsWarrants",
        "nolTax",
        "cash",
        "debt",
        "shareCount",
    }
    assert accounting["leases"]["status"] == "zero_by_default"
    assert accounting["cash"]["status"] == "returned"
    assert "accountingAndClaims" not in result["content"][0]["text"]


def test_value_ticker_visible_text_does_not_expose_mechanical_baseline_value():
    result = MCPToolRegistry(FakeClient()).call(
        "stockvaluation.value_ticker",
        {"ticker": "MSFT"},
    )

    assert result["isError"] is False
    assert result["structuredContent"]["dcf"]["estimatedValuePerShare"] == 412.34
    visible_text = result["content"][0]["text"]
    assert "412.34" not in visible_text
    assert "390.00" not in visible_text
    assert "Baseline use mechanical_only." in visible_text
    assert "Full JSON is in structuredContent." in visible_text


def test_jsonrpc_initialize_negotiates_supported_protocol_version():
    server = MCPJSONRPCServer(MCPToolRegistry(FakeClient()))

    older = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
    )
    unknown = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {
                "protocolVersion": "2099-01-01",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
    )

    assert older["result"]["protocolVersion"] == "2025-06-18"
    assert unknown["result"]["protocolVersion"] == "2025-11-25"


def test_value_ticker_returns_structured_dcf_json_for_msft():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call("stockvaluation.value_ticker", {"ticker": "MSFT"})

    assert result["isError"] is False
    assert result["structuredContent"]["ok"] is True
    assert result["structuredContent"]["ticker"] == "MSFT"
    assert result["structuredContent"]["valuation"]["companyName"] == "Microsoft Corporation"
    assert result["structuredContent"]["dcf"]["estimatedValuePerShare"] == 412.34
    assert result["structuredContent"]["assumptions"]["growth"]["revenueGrowthRateYears2To5"] == 7.0
    assert result["structuredContent"]["policy"]["notFinancialAdvice"] is True
    visible_text = result["content"][0]["text"]
    assert "stockvaluation.value_ticker" in visible_text
    assert "MSFT" in visible_text
    assert "structuredContent" in visible_text
    assert "not financial advice" in visible_text.lower()
    assert len(visible_text) < 500
    assert '"valuation"' not in visible_text
    assert "financialDTO" not in visible_text
    with pytest.raises(json.JSONDecodeError):
        json.loads(visible_text)
    assert client.calls == [("MSFT", {})]


def test_researched_baseline_is_read_only_policy_bearing_ticker_only_tool():
    payload = _valuation_payload()
    payload["sourceQualityGate"] = {
        "status": "requires_user_decision",
        "reason": "sec_http_error_yahoo_fallback",
        "primarySourceExpected": True,
        "fallbackSourceAvailable": True,
        "crossCheckRequired": True,
        "allowedActions": ["continue_with_fallback", "retry_primary_source", "stop"],
    }
    client = FakeClient(payload)
    registry = MCPToolRegistry(client)

    tool = next(item for item in registry.list_tools() if item["name"] == "stockvaluation.researched_baseline")
    assert tool["annotations"]["readOnlyHint"] is True
    assert "overrides" not in tool["inputSchema"]["properties"]

    result = registry.call("stockvaluation.researched_baseline", {"ticker": "MSFT"})

    assert result["isError"] is False
    assert client.calls == [("MSFT", {"researchedBaselineMode": True, "requestPolicyMode": "researched_baseline"})]
    structured = result["structuredContent"]
    assert structured["tool"] == "stockvaluation.researched_baseline"
    assert structured["sourceQualityGate"]["reason"] == "sec_http_error_yahoo_fallback"
    assert structured["sourceQualityGate"]["status"] == "requires_user_decision"
    assert structured["policy"]["baselineEntrypoint"] == "researched_baseline"


def test_mcp_preserves_service_source_quality_gate_for_value_ticker_without_research_policy():
    payload = _valuation_payload()
    payload["sourceQualityGate"] = {
        "status": "not_required",
        "reason": "primary_filing_used",
        "primarySourceExpected": False,
        "fallbackSourceAvailable": False,
        "crossCheckRequired": False,
        "allowedActions": [],
    }

    result = MCPToolRegistry(FakeClient(payload)).call("stockvaluation.value_ticker", {"ticker": "MSFT"})

    assert result["structuredContent"]["sourceQualityGate"] == payload["sourceQualityGate"]
    assert result["structuredContent"]["policy"]["baselineEntrypoint"] == "mechanical_baseline"


def test_recalculate_preserves_source_quality_gate_in_audit_packet_and_scenario_book():
    payload = _valuation_payload()
    payload["sourceQualityGate"] = {
        "status": "requires_user_decision",
        "reason": "sec_http_error_yahoo_fallback",
        "primarySourceExpected": True,
        "fallbackSourceAvailable": True,
        "crossCheckRequired": True,
        "allowedActions": ["continue_with_fallback", "retry_primary_source", "stop"],
    }
    client = FakeClient(payload)
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "user_refined_scenario"},
                "revenue_growth": 0.08,
            },
        },
    )

    structured = result["structuredContent"]
    audit_packet = structured["auditPacket"]["packet"]
    scenario_book = structured["scenarioBook"]["book"]
    assert audit_packet["final_report_inputs"]["source_quality_gate"] == payload["sourceQualityGate"]
    assert scenario_book["provenance_summary"]["source_quality_gate"] == payload["sourceQualityGate"]


def test_recalculate_preserves_explicit_source_quality_gate_bypass_from_request_policy():
    payload = _valuation_payload()
    client = FakeClient(payload)
    registry = MCPToolRegistry(client)
    gate = {
        "status": "bypassed_by_no_questions",
        "reason": "user_explicitly_requested_no_questions",
        "primarySourceExpected": True,
        "fallbackSourceAvailable": True,
        "crossCheckRequired": True,
        "allowedActions": [],
    }

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "user_refined_scenario", "source_quality_gate": gate},
                "revenue_growth": 0.08,
            },
        },
    )

    structured = result["structuredContent"]
    audit_packet = structured["auditPacket"]["packet"]
    scenario_book = structured["scenarioBook"]["book"]
    assert structured["sourceQualityGate"] == gate
    assert audit_packet["final_report_inputs"]["source_quality_gate"] == gate
    assert scenario_book["provenance_summary"]["source_quality_gate"] == gate


def test_value_ticker_exposes_honest_single_industry_baseline_contract():
    payload = _valuation_payload()
    payload["companyName"] = "NVIDIA Corporation"
    payload["assumptionTransparency"].update(
        {
            "baselineQuality": "single_industry_fallback",
            "segmentAware": False,
            "segmentCount": 0,
            "segmentCoveragePct": 0.0,
            "mappedIndustries": [],
            "weightedBaselineAssumptions": {},
        }
    )
    payload["assumptionTransparency"]["operatingAssumptions"]["targetOperatingMargin"] = 55.76
    client = FakeClient(payload)
    registry = MCPToolRegistry(client)

    result = registry.call("stockvaluation.value_ticker", {"ticker": "NVDA"})

    baseline = result["structuredContent"]["baseline"]
    assert baseline["baselineQuality"] == "single_industry_fallback"
    assert baseline["baselineUseStatus"] == "mechanical_only"
    assert baseline["segmentAware"] is False
    assert baseline["segmentCount"] == 0
    assert baseline["segmentCoveragePct"] == 0.0
    assert baseline["mappedIndustries"] == []
    assert baseline["weightedBaselineAssumptions"] == {}
    assert baseline["targetOperatingMargin"] == 55.76
    assert baseline["targetOperatingMarginStatus"] == "single_industry_mechanical_fallback"
    assert any("not segment-weighted" in warning for warning in baseline["baselineWarnings"])


def test_value_ticker_exposes_compact_source_provenance_metadata():
    payload = _valuation_payload()
    payload["assumptionTransparency"]["sourceProvenance"] = {
        "sourceClass": "yahoo_normalized",
        "provider": "yfinance-http",
        "sourceDate": "2025-06-30",
        "periodEnd": "2025-06-30",
        "retrievalStatus": "retrieved",
        "crossCheckStatus": "company_report_check_pending",
        "sourcePolicyStatus": "sec_http_error_yahoo_fallback",
        "warnings": [
            "US researched valuation is using Yahoo-normalized financials because SEC primary filing data was unavailable (sec_http_error_yahoo_fallback)."
        ],
        "dataQualityWarnings": [
            {
                "field": "revenue",
                "status": "material_mismatch",
                "normalizedValue": 100.0,
                "filingValue": 112.0,
                "differencePct": 0.1071,
                "thresholdPct": 0.05,
                "sourceClass": "primary_filing",
                "sourceDate": "2025-06-30",
                "normalizedSourceClass": "yahoo_normalized",
                "normalizedSourceDate": "2025-03-31",
                "normalizedPeriodEnd": "2025-03-31",
                "filingSourceClass": "primary_filing",
                "filingSourceDate": "2025-06-30",
                "filingPeriodEnd": "2025-06-30",
            }
        ],
    }
    result = MCPToolRegistry(FakeClient(payload)).call("stockvaluation.value_ticker", {"ticker": "MSFT"})

    provenance = result["structuredContent"]["provenance"]
    assert provenance == {
        "sourceClass": "yahoo_normalized",
        "provider": "yfinance-http",
        "sourceDate": "2025-06-30",
        "periodEnd": "2025-06-30",
        "retrievalStatus": "retrieved",
        "crossCheckStatus": "company_report_check_pending",
        "sourcePolicyStatus": "sec_http_error_yahoo_fallback",
        "warnings": [
            "US researched valuation is using Yahoo-normalized financials because SEC primary filing data was unavailable (sec_http_error_yahoo_fallback)."
        ],
        "dataQualityWarnings": [
            {
                "field": "revenue",
                "status": "material_mismatch",
                "normalizedValue": 100.0,
                "filingValue": 112.0,
                "differencePct": 0.1071,
                "thresholdPct": 0.05,
                "sourceClass": "primary_filing",
                "sourceDate": "2025-06-30",
                "normalizedSourceClass": "yahoo_normalized",
                "normalizedSourceDate": "2025-03-31",
                "normalizedPeriodEnd": "2025-03-31",
                "filingSourceClass": "primary_filing",
                "filingSourceDate": "2025-06-30",
                "filingPeriodEnd": "2025-06-30",
            }
        ],
    }
    visible_text = result["content"][0]["text"]
    assert "sec_http_error_yahoo_fallback" in visible_text
    assert len(visible_text) < 600


def test_value_ticker_preserves_live_sec_primary_filing_provenance_metadata():
    payload = _valuation_payload()
    payload["assumptionTransparency"]["sourceProvenance"] = {
        "sourceClass": "primary_filing",
        "provider": "sec-edgar-companyfacts",
        "sourceDate": "2026-07-30",
        "periodEnd": "2026-06-30",
        "retrievalStatus": "retrieved",
        "crossCheckStatus": "not_applicable",
        "sourcePolicyStatus": "primary_filing_used",
        "warnings": [],
        "dataQualityWarnings": [],
    }

    result = MCPToolRegistry(FakeClient(payload)).call("stockvaluation.value_ticker", {"ticker": "MSFT"})

    provenance = result["structuredContent"]["provenance"]
    assert provenance["sourceClass"] == "primary_filing"
    assert provenance["provider"] == "sec-edgar-companyfacts"
    assert provenance["sourceDate"] == "2026-07-30"
    assert provenance["periodEnd"] == "2026-06-30"
    assert provenance["sourcePolicyStatus"] == "primary_filing_used"
    assert "primary_filing_used" in result["content"][0]["text"]
    assert "sec-xbrl-fixture" not in json.dumps(result["structuredContent"])


def test_recalculate_preserves_compact_source_provenance_metadata():
    payload = _valuation_payload()
    payload["assumptionTransparency"]["sourceProvenance"] = {
        "sourceClass": "yahoo_normalized",
        "provider": "yfinance-http",
        "sourceDate": "2025-06-30",
        "periodEnd": "2025-06-30",
        "retrievalStatus": "retrieved",
        "crossCheckStatus": "company_report_cross_checked",
        "sourcePolicyStatus": "primary_adapter_not_supported_yahoo_normalized",
        "warnings": ["Company report cross-check is required for Yahoo-normalized data before researched claims."],
    }

    result = MCPToolRegistry(FakeClient(payload)).call(
        "stockvaluation.recalculate",
        {
            "ticker": "SAP.DE",
            "overrides": {"revenue_growth": 0.06},
        },
    )

    assert result["isError"] is False
    assert result["structuredContent"]["tool"] == "stockvaluation.recalculate"
    assert result["structuredContent"]["provenance"] == {
        "sourceClass": "yahoo_normalized",
        "provider": "yfinance-http",
        "sourceDate": "2025-06-30",
        "periodEnd": "2025-06-30",
        "retrievalStatus": "retrieved",
        "crossCheckStatus": "company_report_cross_checked",
        "sourcePolicyStatus": "primary_adapter_not_supported_yahoo_normalized",
        "warnings": ["Company report cross-check is required for Yahoo-normalized data before researched claims."],
        "dataQualityWarnings": [],
    }
    visible_text = result["content"][0]["text"]
    assert "primary_adapter_not_supported_yahoo_normalized" in visible_text
    assert len(visible_text) < 600


def test_invalid_ticker_returns_agent_readable_error_without_service_call():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call("stockvaluation.value_ticker", {"ticker": "MSFT;cat .env"})

    assert result["isError"] is True
    assert result["structuredContent"]["ok"] is False
    assert result["structuredContent"]["error"]["code"] == "INVALID_TICKER"
    assert result["structuredContent"]["recovery"]["agentAction"]
    visible_text = result["content"][0]["text"]
    assert "INVALID_TICKER" in visible_text
    assert "valid public ticker" in visible_text
    assert "structuredContent" in visible_text
    assert len(visible_text) < 700
    with pytest.raises(json.JSONDecodeError):
        json.loads(visible_text)
    assert client.calls == []


def test_recalculate_maps_supported_overrides_and_separates_requested_from_effective():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "revenue_growth": 0.09,
                "operating_margin": 44.0,
                "sales_to_capital": 2.3,
                "wacc": 0.085,
                "terminal_growth": 0.03,
                "tax_rate": 0.21,
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["requested"]["revenue_growth"] == 0.09
    assert assumptions["mapped"]["compoundAnnualGrowth2_5"] == 9.0
    assert assumptions["mapped"]["initialCostCapital"] == 8.5
    assert assumptions["mapped"]["overrideAssumptionTaxRate"]["overrideCost"] == 21.0
    assert assumptions["unsupported"] == {}
    assert assumptions["effective"]["operating_margin"] == 45.0
    assert client.calls[0][1]["salesToCapitalYears1To5"] == 2.3


def test_user_refined_scenario_maps_direct_margin_path_and_capital_efficiency_fields():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "user_refined_scenario"},
                "operating_margin_next_year": 0.38,
                "target_operating_margin": 43.5,
                "margin_convergence_year": 7,
                "sales_to_capital_years_1_to_5": 1.8,
                "sales_to_capital_years_6_to_10": 2.2,
                "user_judgment": {
                    "source_type": "user_judgment",
                    "answers": [{"question_id": "margin_durability", "selected_choice": "B"}],
                },
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["metadata"]["request_policy"] == {"mode": "user_refined_scenario"}
    assert assumptions["metadata"]["user_judgment"]["source_type"] == "user_judgment"
    assert assumptions["mapped"]["requestPolicyMode"] == "user_refined_scenario"
    assert assumptions["mapped"]["operatingMarginNextYear"] == 38.0
    assert assumptions["mapped"]["targetPreTaxOperatingMargin"] == 43.5
    assert assumptions["mapped"]["convergenceYearMargin"] == 7
    assert assumptions["mapped"]["salesToCapitalYears1To5"] == 1.8
    assert assumptions["mapped"]["salesToCapitalYears6To10"] == 2.2
    assert assumptions["unsupported"] == {}
    assert assumptions["effective"]["operating_margin_next_year"] == 41.0
    assert client.calls[0][1]["requestPolicyMode"] == "user_refined_scenario"


def test_user_refined_scenario_rejects_out_of_bounds_direct_inputs():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "user_refined_scenario"},
                "margin_convergence_year": 11,
                "sales_to_capital_years_1_to_5": -2,
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["mapped"]["requestPolicyMode"] == "user_refined_scenario"
    assert set(assumptions["unsupported"]) == {
        "margin_convergence_year",
        "sales_to_capital_years_1_to_5",
    }
    assert all(
        item["status"] == "scenario_input_out_of_bounds"
        for item in assumptions["unsupported"].values()
    )
    assert client.calls == []


def test_operating_margin_next_year_does_not_set_target_margin_in_mcp_mapping():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "user_refined_scenario"},
                "operating_margin_next_year": 35.0,
            },
        },
    )

    assert result["isError"] is False
    mapped = result["structuredContent"]["assumptions"]["mapped"]
    assert mapped["operatingMarginNextYear"] == 35.0
    assert "targetPreTaxOperatingMargin" not in mapped


def test_user_refined_scenario_rejects_explicit_scenario_only_fields():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "user_refined_scenario"},
                "revenue_growth": 8.0,
                "wacc": 8.5,
                "terminal_growth": 3.0,
                "tax_rate": 21.0,
                "growth_pattern_override": "THREE_STAGE",
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["mapped"]["requestPolicyMode"] == "user_refined_scenario"
    assert assumptions["mapped"]["compoundAnnualGrowth2_5"] == 8.0
    assert set(assumptions["unsupported"]) == {
        "wacc",
        "terminal_growth",
        "tax_rate",
        "growth_pattern_override",
    }
    assert all(
        item["status"] == "explicit_scenario_only_in_user_refined_scenario_mode"
        for item in assumptions["unsupported"].values()
    )
    scenario_book = result["structuredContent"]["scenarioBook"]
    assert "validation_warnings" not in scenario_book
    assert scenario_book["summary"]["book_status"] == "blocked"
    assert scenario_book["book"]["guided_refinement"]["status"] == "blocked"
    assert client.calls == []


def test_recalculate_never_accepts_direct_valuation_outputs_as_inputs():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {"fair_value": 500.0, "target_price": 525.0, "market_price": 490.0},
        },
    )

    assert result["isError"] is True
    unsupported = result["structuredContent"]["assumptions"]["unsupported"]
    assert set(unsupported) == {"fair_value", "target_price", "market_price"}
    assert all(item["status"] == "direct_valuation_output_rejected" for item in unsupported.values())
    assert client.calls == []


def test_recalculate_rejects_scenario_only_fields_in_autonomous_researched_mode():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "revenue_growth": 0.08,
                "evidence_packet": _valid_evidence_packet(),
                "wacc": 0.085,
                "terminal_growth": 0.03,
                "tax_rate": 0.21,
                "growth_pattern_override": "THREE_STAGE",
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["metadata"]["request_policy"] == {"mode": "autonomous_researched"}
    assert set(assumptions["unsupported"]) == {
        "wacc",
        "terminal_growth",
        "tax_rate",
        "growth_pattern_override",
    }
    assert assumptions["mapped"]["compoundAnnualGrowth2_5"] == 8.0
    assert client.calls == []


def test_recalculate_maps_researched_baseline_policy_to_service_flag():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "researched_baseline"},
                "revenue_growth": 0.08,
                "evidence_packet": _valid_evidence_packet(),
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["metadata"]["request_policy"] == {"mode": "researched_baseline"}
    assert assumptions["mapped"]["researchedBaselineMode"] is True
    assert client.calls[0][1]["researchedBaselineMode"] is True
    assert "request_policy" not in client.calls[0][1]


def test_recalculate_researched_baseline_without_segments_flags_baseline_state():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "NVDA",
            "overrides": {
                "request_policy": {"mode": "researched_baseline"},
                "revenue_growth": 0.08,
                "evidence_packet": _valid_evidence_packet(),
            },
        },
    )

    assert result["isError"] is False
    baseline = result["structuredContent"]["baseline"]
    assert baseline["baselineQuality"] == "single_industry_fallback"
    assert baseline["baselineUseStatus"] == "segment_evidence_insufficient"
    assert baseline["segmentAware"] is False
    assert any("researched baseline mode" in warning for warning in baseline["baselineWarnings"])


def test_recalculate_accepts_segment_payloads_without_collapsing_assumption_buckets():
    payload = copy.deepcopy(_valuation_payload())
    payload["assumptionTransparency"]["baselineQuality"] = "segment_weighted_baseline"
    payload["assumptionTransparency"]["segmentAware"] = True
    payload["assumptionTransparency"]["segmentCount"] = 2
    payload["assumptionTransparency"]["segmentCoveragePct"] = 100.0
    payload["assumptionTransparency"]["mappedIndustries"] = [
        "Software (System & Application)",
        "Electronics (Consumer & Office)",
    ]
    client = FakeClient(payload=payload)
    registry = MCPToolRegistry(client)
    segments = [
        {
            "segment_name": "Cloud software",
            "sector_key": "software-infrastructure",
            "mapped_industry": "Software (System & Application)",
            "components": ["Azure", "Server products"],
            "mapping_score": 0.92,
            "mapping_confidence": "high",
            "revenue_share": 52.5,
            "source_name": "FY annual report",
            "source_date": "2026-06-30",
            "source_url": "https://example.com/msft-annual-report",
            "validation_warnings": [],
            "operating_margin": 43.0,
        },
        {
            "segment_name": "Devices",
            "sector_key": "consumer-electronics",
            "mapped_industry": "Electronics (Consumer & Office)",
            "components": ["Surface", "Xbox"],
            "mapping_score": 0.78,
            "mapping_confidence": "medium",
            "revenue_share": 47.5,
            "source_name": "FY annual report",
            "source_date": "2026-06-30",
            "source_url": "https://example.com/msft-annual-report",
            "validation_warnings": [],
        },
    ]

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "revenue_growth": 0.08,
                "segments": segments,
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["requested"]["segments"] == segments
    first_segment = assumptions["mapped"]["segments"]["segments"][0]
    assert first_segment["revenueShare"] == 0.525
    assert first_segment["sector"] == "software-infrastructure"
    assert first_segment["industry"] == "Software (System & Application)"
    assert first_segment["sourceName"] == "FY annual report"
    assert first_segment["sourceDate"] == "2026-06-30"
    assert first_segment["sourceUrl"] == "https://example.com/msft-annual-report"
    assert "operatingMargin" not in first_segment
    assert any("Segment operating margin is report-only" in warning for warning in first_segment["validationWarnings"])
    assert assumptions["unsupported"] == {}
    assert result["structuredContent"]["baseline"]["baselineUseStatus"] == "validated_segment_weighted"
    assert assumptions["effective"]["revenue_growth"] == 7.0
    assert client.calls[0][1]["segments"] == assumptions["mapped"]["segments"]


def test_recalculate_rejects_names_only_segments_as_report_only():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "NVDA",
            "overrides": {
                "segments": [
                    {
                        "segment_name": "Compute and Networking",
                        "sector": "Semiconductors",
                        "mapped_industry": "Semiconductor",
                        "source_name": "FY 10-K",
                        "source_date": "2026-03-01",
                        "source_url": "https://example.com/nvda-10k",
                    }
                ]
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["segments"]["reason"] == "segment_evidence_insufficient"
    assert "revenue weights" in assumptions["unsupported"]["segments"]["message"]
    assert client.calls == []


def test_recalculate_blocks_segment_package_when_mapping_confidence_is_low():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "COST",
            "overrides": {
                "segments": [
                    {
                        "segment_name": "United States",
                        "sector": "Retail",
                        "mapped_industry": "Retail (Grocery and Food)",
                        "mapping_confidence": "low",
                        "revenue_share": 1.0,
                        "source_name": "FY annual report",
                        "source_date": "2026-10-10",
                        "source_url": "https://example.com/cost-annual-report",
                        "validation_warnings": ["geographic disclosure cannot drive operating economics"],
                    }
                ]
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["segments"]["reason"] == "segment_mapping_blocked"
    assert "mapping confidence" in assumptions["unsupported"]["segments"]["message"]
    assert client.calls == []


def test_recalculate_blocks_weighted_segments_without_service_sector_key():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "segments": [
                    {
                        "segment_name": "Cloud software",
                        "mapped_industry": "Software (System & Application)",
                        "mapping_confidence": "high",
                        "revenue_share": 1.0,
                        "source_name": "FY annual report",
                        "source_date": "2026-06-30",
                        "source_url": "https://example.com/msft-annual-report",
                    }
                ]
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["segments"]["reason"] == "segment_mapping_blocked"
    assert "sector_key" in assumptions["unsupported"]["segments"]["message"]
    assert client.calls == []


def test_recalculate_blocks_direct_geographic_segments_without_operating_segment_rationale():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "COST",
            "overrides": {
                "segments": [
                    {
                        "segment_name": "United States",
                        "sector_key": "discount-stores",
                        "mapped_industry": "Retail (General)",
                        "mapping_confidence": "high",
                        "revenue_share": 1.0,
                        "source_name": "FY annual report",
                        "source_date": "2026-10-10",
                        "source_url": "https://example.com/cost-annual-report",
                        "disclosure_level": "geography",
                    }
                ]
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["segments"]["reason"] == "segment_mapping_blocked"
    assert "Geographic disclosure" in assumptions["unsupported"]["segments"]["message"]
    assert client.calls == []


def test_recalculate_accepts_sector_override_instructions():
    client = FakeClient()
    registry = MCPToolRegistry(client)
    sector_overrides = [
        {
            "sector_key": "software-infrastructure",
            "parameter": "revenue_growth",
            "value": 12.0,
            "unit": "percent",
            "adjustment_type": "absolute",
            "timeframe": "years_1_to_5",
            "rationale": "Recent cloud segment evidence supports above-baseline growth.",
        }
    ]

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "sector_overrides": sector_overrides,
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["requested"]["sector_overrides"] == sector_overrides
    assert assumptions["unsupported"] == {}
    mapped = assumptions["mapped"]["sectorOverrides"][0]
    assert mapped == {
        "sectorName": "software-infrastructure",
        "parameterType": "revenue_growth",
        "value": 12.0,
        "adjustmentType": "absolute",
        "timeframe": "years_1_to_5",
    }
    assert client.calls[0][1]["sectorOverrides"] == assumptions["mapped"]["sectorOverrides"]


def test_recalculate_maps_valid_segment_economics_without_leaking_artifact_to_service():
    client = FakeClient()
    registry = MCPToolRegistry(client)
    segment_economics = _valid_segment_economics_artifact()

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "segment_economics": segment_economics,
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["requested"]["segment_economics"] == segment_economics
    assert assumptions["metadata"]["segment_economics"]["status"] == "partial_economics"
    assert assumptions["mapped"]["segments"]["segments"][0]["revenueShare"] == 1.0
    assert assumptions["mapped"]["segments"]["segments"][0]["sector"] == "software-infrastructure"
    assert assumptions["mapped"]["segments"]["segments"][0]["industry"] == "Software (System & Application)"
    assert assumptions["mapped"]["sectorOverrides"][0] == {
        "sectorName": "software-infrastructure",
        "parameterType": "operating_margin",
        "value": 36.0,
        "adjustmentType": "absolute",
        "timeframe": "both",
    }
    assert "segment_economics" not in client.calls[0][1]
    assert client.calls[0][1]["segments"] == assumptions["mapped"]["segments"]
    assert client.calls[0][1]["sectorOverrides"] == assumptions["mapped"]["sectorOverrides"]


def test_recalculate_blocks_segment_economics_without_service_sector_key_before_service_call():
    client = FakeClient()
    registry = MCPToolRegistry(client)
    segment_economics = _valid_segment_economics_artifact()
    segment_economics["segments"][0].pop("sector_key")

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "segment_economics": segment_economics,
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["segment_economics"]["status"] == "segment_mapping_blocked"
    assert "sector_key" in assumptions["unsupported"]["segment_economics"]["message"]
    assert client.calls == []


def test_recalculate_blocks_geographic_segment_economics_before_service_call():
    client = FakeClient()
    registry = MCPToolRegistry(client)
    segment_economics = _valid_segment_economics_artifact()
    segment_economics["ticker"] = "COST"
    segment_economics["company"] = "Costco Wholesale Corporation"
    segment_economics["segments"][0]["segment_name"] = "United States"
    segment_economics["segments"][0]["sector_key"] = "discount-stores"
    segment_economics["segments"][0]["mapped_industry"] = "Retail (Grocery and Food)"
    segment_economics["segments"][0]["disclosure_level"] = "geography"
    segment_economics["segments"][0].pop("drivers")

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "COST",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "segment_economics": segment_economics,
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["segment_economics"]["status"] == "segment_mapping_blocked"
    assert "Geographic disclosure" in assumptions["unsupported"]["segment_economics"]["message"]
    assert client.calls == []


def test_recalculate_blocks_rejected_segment_economics_before_service_call():
    client = FakeClient()
    registry = MCPToolRegistry(client)
    segment_economics = _valid_segment_economics_artifact()
    segment_economics["evidence_packet"] = _valid_evidence_packet(
        driver="operating_margin",
        evidence_summary="10-K found",
        assumption_implication="Generic source presence cannot support a segment margin change.",
    )

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "segment_economics": segment_economics,
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["segment_economics"]["status"] == "blocked_by_rejected_segment_economics"
    assert assumptions["metadata"]["segment_economics"]["rejected_economics"][0]["status"] == "missing_governed_evidence"
    assert (
        assumptions["metadata"]["segment_economics"]["metadata"]["evidence_packet"]["rejected_evidence"][0]["status"]
        == "generic_source_presence"
    )
    assert "segments" not in assumptions["mapped"]
    assert "sectorOverrides" not in assumptions["mapped"]
    assert client.calls == []


def test_recalculate_accepts_supported_growth_pattern_override():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "growth_pattern_override": "three_stage",
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["requested"]["growth_pattern_override"] == "three_stage"
    assert assumptions["mapped"]["growthPatternOverride"] == "THREE_STAGE"
    assert assumptions["unsupported"] == {}
    assert client.calls[0][1]["growthPatternOverride"] == "THREE_STAGE"


def test_recalculate_preserves_rationale_and_evidence_metadata_without_sending_to_service():
    client = FakeClient()
    registry = MCPToolRegistry(client)
    evidence_used = [
        {
            "claim": "Azure growth remained above company average.",
            "source_title": "FY earnings release",
            "source_url": "https://example.com/msft-earnings",
            "source_date": "2026-01-30",
            "evidence_type": "earnings",
        }
    ]

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "revenue_growth": 0.09,
                "rationale": "Cited cloud evidence supports a modest growth adjustment.",
                "evidence_used": evidence_used,
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["requested"]["evidence_used"] == evidence_used
    assert assumptions["metadata"]["rationale"] == "Cited cloud evidence supports a modest growth adjustment."
    assert assumptions["metadata"]["evidence_used"] == evidence_used
    assert assumptions["unsupported"] == {}
    assert "rationale" not in client.calls[0][1]
    assert "evidence_used" not in client.calls[0][1]


def test_recalculate_preserves_valid_evidence_packet_metadata_without_sending_to_service():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "revenue_growth": 0.09,
                "evidence_packet": _valid_evidence_packet(),
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["mapped"]["compoundAnnualGrowth2_5"] == 9.0
    assert assumptions["metadata"]["evidence_packet"]["ok"] is True
    assert assumptions["metadata"]["evidence_packet"]["status"] == "valid_governed_evidence"
    assert assumptions["metadata"]["evidence_packet"]["governed_evidence"][0]["driver"] == "revenue_growth"
    assert "evidence_packet" not in client.calls[0][1]


def test_recalculate_returns_compact_valuation_audit_packet_metadata():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "revenue_growth": 0.09,
                "evidence_packet": _valid_evidence_packet(),
                "baseline_plausibility": {
                    "status": "accepted",
                    "unsupported_blockers": [],
                },
                "assumption_judgment": {
                    "status": "governed_recalculation_supported",
                    "assumptions_left_unchanged": [],
                },
            },
        },
    )

    assert result["isError"] is False
    audit = result["structuredContent"]["auditPacket"]
    assert audit["summary"]["final_case_type"] == "evidence_constrained_governed_recalculation"
    assert audit["summary"]["evidence_status"] == "valid_governed_evidence"
    assert audit["reference"].startswith("valuation_audit_packet:")
    packet = audit["packet"]
    assert packet["schema_version"] == "valuation_audit_packet.v1"
    assert packet["evidence_packet"]["governed_evidence"][0]["driver"] == "revenue_growth"
    assert packet["baseline_plausibility"]["status"] == "accepted"
    assert packet["assumption_judgment"]["status"] == "governed_recalculation_supported"
    assert packet["assumption_buckets"]["requested"]["revenue_growth"] == 0.09
    assert packet["assumption_buckets"]["mapped"]["compoundAnnualGrowth2_5"] == 9.0
    assert packet["assumption_buckets"]["effective"]["revenue_growth"] == 7.0
    assert packet["recalculate_payloads"][0]["status"] == "executed"
    visible_text = result["content"][0]["text"]
    assert "schema_version" not in visible_text
    assert "governed_evidence" not in visible_text
    assert "Full JSON is in structuredContent." in visible_text


def test_recalculate_returns_compact_scenario_book_with_market_diagnostics():
    payload = _valuation_payload()
    payload["assumptionTransparency"]["marketImpliedExpectations"] = {
        "revenueGrowth": {"modelValue": 7.0, "impliedValue": 11.5, "solved": True}
    }
    payload["assumptionTransparency"]["pricedInExpectations"] = {
        "frontier": [{"operatingMargin": 42.0, "impliedRevenueGrowth": 11.5}],
        "scenarios": [{"headline": "Higher growth needed to justify market price"}],
        "grid": [{"growth": 10.0, "margin": 42.0}],
    }
    client = FakeClient(payload)
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "revenue_growth": 0.09,
                "evidence_packet": _valid_evidence_packet(),
            },
        },
    )

    assert result["isError"] is False
    scenario_book = result["structuredContent"]["scenarioBook"]
    assert scenario_book["reference"].startswith("scenario_book:")
    assert scenario_book["summary"]["main_scenario_type"] == "evidence_constrained_base"
    assert scenario_book["book"]["schema_version"] == "scenario_book.v1"
    assert scenario_book["book"]["main_scenario_id"] == "evidence_base"
    assert [scenario["type"] for scenario in scenario_book["book"]["scenarios"]] == ["evidence_constrained_base"]
    assert scenario_book["book"]["scenarios"][0]["assumptions"]["mapped"]["compoundAnnualGrowth2_5"] == 9.0
    assert scenario_book["book"]["diagnostics"][0]["visibility"] == "diagnostic_only"
    assert scenario_book["book"]["diagnostics"][0]["evidence_status"] == "not_evidence"
    assert scenario_book["book"]["internal_references"]["mechanical_baseline"]["visibility"] == "internal_only"
    visible_text = result["content"][0]["text"]
    assert "scenario_book.v1" not in visible_text
    assert "mechanical_baseline" not in visible_text


def test_recalculate_audit_packet_preserves_unsupported_fields_when_blocked():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "wacc": 8.5,
                "terminal_growth": 3.0,
                "evidence_packet": _valid_evidence_packet(),
            },
        },
    )

    assert result["isError"] is True
    assert client.calls == []
    audit = result["structuredContent"]["auditPacket"]
    assert audit["summary"]["final_case_type"] == "insufficient_researched_evidence"
    unsupported = audit["packet"]["assumption_buckets"]["unsupported"]
    assert set(unsupported) == {"wacc", "terminal_growth"}
    assert unsupported["wacc"]["reason"] == "scenario_only_in_autonomous_researched_mode"


def test_recalculate_audit_packet_records_guided_refinement_bypass():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {
                    "mode": "autonomous_researched",
                    "guided_refinement": "bypassed",
                    "guided_refinement_bypass_reason": "quick valuation requested",
                },
                "evidence_packet": _valid_evidence_packet(confidence="low"),
            },
        },
    )

    assert result["isError"] is False
    audit = result["structuredContent"]["auditPacket"]
    assert audit["summary"]["final_case_type"] == "evidence_constrained_no_change"
    assert audit["summary"]["guided_refinement_status"] == "bypassed"
    assert audit["packet"]["guided_refinement"] == {
        "status": "bypassed",
        "bypass_reason": "quick valuation requested",
        "user_judgment": None,
    }
    scenario_book = result["structuredContent"]["scenarioBook"]
    assert scenario_book["summary"]["book_status"] == "completed_with_bypass"
    assert scenario_book["summary"]["guided_refinement_status"] == "bypassed"
    assert [scenario["type"] for scenario in scenario_book["book"]["scenarios"]] == ["evidence_constrained_base"]


def test_recalculate_audit_packet_records_user_refined_scenario_case():
    client = FakeClient()
    registry = MCPToolRegistry(client)
    user_judgment = {
        "source_type": "user_judgment",
        "scenario_label": "user-refined scenario",
        "answers": [{"driver": "operating_margin_next_year", "choice": "slower margin ramp"}],
    }

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "user_refined_scenario"},
                "operating_margin_next_year": 39.0,
                "user_judgment": user_judgment,
                "evidence_packet": _valid_evidence_packet(confidence="low"),
            },
        },
    )

    assert result["isError"] is False
    audit = result["structuredContent"]["auditPacket"]
    assert audit["summary"]["final_case_type"] == "user_refined_scenario"
    assert audit["summary"]["guided_refinement_status"] == "completed"
    assert audit["packet"]["guided_refinement"]["user_judgment"] == user_judgment
    assert audit["packet"]["assumption_buckets"]["mapped"]["operatingMarginNextYear"] == 39.0
    scenario_book = result["structuredContent"]["scenarioBook"]
    assert "validation_warnings" not in scenario_book
    assert scenario_book["summary"]["main_scenario_type"] == "user_refined_scenario"
    assert scenario_book["book"]["main_scenario_id"] == "user_refined"
    assert scenario_book["book"]["guided_refinement"]["final_recalculate_reference"] == "recalculate_payload:0"
    assert scenario_book["book"]["scenarios"][0]["source"] == "guided_user_judgment"
    assert scenario_book["book"]["scenarios"][0]["assumptions"]["metadata"]["user_judgment"] == user_judgment


def test_recalculate_blocks_autonomous_changes_without_evidence_packet():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "revenue_growth": 0.09,
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["evidence_packet"]["status"] == "missing_evidence_packet_for_requested_changes"
    assert client.calls == []


def test_recalculate_blocks_autonomous_changes_not_supported_by_matching_evidence_driver():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "operating_margin": 0.44,
                "evidence_packet": _valid_evidence_packet(driver="revenue_growth"),
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["evidence_packet"]["status"] == "evidence_driver_mismatch"
    assert assumptions["unsupported"]["evidence_packet"]["missing_drivers"] == ["operating_margin"]
    assert client.calls == []


def test_recalculate_blocks_unsupported_governed_evidence_packet_before_service_call():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "revenue_growth": 0.09,
                "evidence_packet": _valid_evidence_packet(
                    driver="risk_wacc",
                    evidence_summary="The filing describes regulatory risk.",
                ),
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["evidence_packet"]["status"] == "blocked_by_unsupported_fields"
    assert assumptions["metadata"]["evidence_packet"]["unsupported_blockers"] == [
        {
            "field": "risk_wacc",
            "status": "unsupported_governed_driver",
            "reason": "risk_wacc is report-only in autonomous researched evidence validation.",
        }
    ]
    assert client.calls == []


def test_recalculate_blocks_autonomous_changes_when_evidence_packet_has_no_governed_evidence():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "revenue_growth": 0.09,
                "evidence_packet": _valid_evidence_packet(confidence="low"),
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["evidence_packet"]["status"] == "no_governed_evidence_for_requested_changes"
    assert assumptions["metadata"]["evidence_packet"]["status"] == "valid_no_governed_change"
    assert assumptions["metadata"]["evidence_packet"]["rejected_evidence"][0]["status"] == "low_confidence_governed_change"
    assert client.calls == []


def test_recalculate_blocks_autonomous_changes_when_evidence_packet_is_stale():
    client = FakeClient()
    registry = MCPToolRegistry(client)
    evidence_packet = _valid_evidence_packet(source_date="2023-01-01")
    evidence_packet["as_of_date"] = "2026-05-29"

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "revenue_growth": 0.09,
                "evidence_packet": evidence_packet,
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["unsupported"]["evidence_packet"]["status"] == "no_governed_evidence_for_requested_changes"
    assert assumptions["metadata"]["evidence_packet"]["ok"] is True
    assert assumptions["metadata"]["evidence_packet"]["status"] == "valid_no_governed_change"
    assert assumptions["metadata"]["evidence_packet"]["rejected_evidence"][0]["status"] == "stale_governed_change"
    assert client.calls == []


def test_recalculate_allows_no_change_evidence_packet_as_metadata_only():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "MSFT",
            "overrides": {
                "request_policy": {"mode": "autonomous_researched"},
                "evidence_packet": _valid_evidence_packet(confidence="low"),
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["metadata"]["evidence_packet"]["status"] == "valid_no_governed_change"
    assert assumptions["mapped"]["researchedBaselineMode"] is True
    assert "compoundAnnualGrowth2_5" not in assumptions["mapped"]
    assert client.calls[0][1] == {
        "researchedBaselineMode": True,
        "requestPolicyMode": "autonomous_researched",
    }


def test_recalculate_rejects_unsupported_override_fields():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {"ticker": "MSFT", "overrides": {"cash": 1, "share_count": 2}},
    )

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "UNSUPPORTED_OVERRIDES"
    assert result["structuredContent"]["assumptions"]["requested"] == {"cash": 1, "share_count": 2}
    assert set(result["structuredContent"]["assumptions"]["unsupported"]) == {"cash", "share_count"}
    assert client.calls == []


def test_recalculate_preserves_unsupported_accounting_fields_as_blocked_report_only():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "NVDA",
            "overrides": {
                "request_policy": {"mode": "researched_baseline"},
                "operating_margin_next_year": 60.0,
                "rd_capitalization": True,
                "leases": {"capitalize": True},
                "sbc_dilution": {"value": 1},
                "options": {"value": 100},
                "options_warrants": {"value": 100},
                "nols": 10,
                "nol_tax": {"value": 10},
                "cash": 1,
                "debt": 2,
                "share_count": 3,
                "accounting_adjustments": {"normalize": True},
            },
        },
    )

    assert result["isError"] is True
    unsupported = result["structuredContent"]["assumptions"]["unsupported"]
    assert set(unsupported) == {
        "operating_margin_next_year",
        "rd_capitalization",
        "leases",
        "sbc_dilution",
        "options",
        "options_warrants",
        "nols",
        "nol_tax",
        "cash",
        "debt",
        "share_count",
        "accounting_adjustments",
    }
    assert unsupported["operating_margin_next_year"]["status"] == "scenario_only_in_autonomous_researched_mode"
    for key, item in unsupported.items():
        if key == "operating_margin_next_year":
            continue
        assert item["status"] == "blocked_report_only"
        assert "report-only" in item["message"]
    audit_accounting = result["structuredContent"]["auditPacket"]["packet"]["accounting_decisions"]
    for key in {
        "rd_capitalization",
        "leases",
        "sbc_dilution",
        "options_warrants",
        "nol_tax",
        "cash",
        "debt",
        "share_count",
    }:
        assert key in audit_accounting["requested"]
        assert key in audit_accounting["unsupported"]
    assert client.calls == []


def test_recalculate_maps_governed_rd_capitalization_only_for_explicit_scenario():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "NVDA",
            "overrides": {
                "request_policy": {"mode": "explicit_scenario"},
                "rd_capitalization": {
                    "enabled": True,
                    "rd_history": [
                        {
                            "fiscal_year": 2026,
                            "amount": 12_000.0,
                            "source_url": "https://example.com/nvda-2026-10k",
                            "source_date": "2026-02-26",
                        },
                        {
                            "fiscal_year": 2025,
                            "amount": 9_000.0,
                            "source_url": "https://example.com/nvda-2025-10k",
                            "source_date": "2025-02-27",
                        },
                        {
                            "fiscal_year": 2024,
                            "amount": 7_000.0,
                            "source_url": "https://example.com/nvda-2024-10k",
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
                },
            },
        },
    )

    assert result["isError"] is False
    assumptions = result["structuredContent"]["assumptions"]
    assert assumptions["mapped"]["isExpensesCapitalize"] is True
    assert client.calls[0][1]["isExpensesCapitalize"] is True
    accounting = assumptions["metadata"]["accounting_and_claims"]
    assert accounting["status"] == "valid_accounting_and_claims"
    assert accounting["governed_scenarios"][0]["topic"] == "rd_capitalization"
    assert accounting["governed_scenarios"][0]["status"] == "governed_scenario_supported"
    audit_packet = result["structuredContent"]["auditPacket"]["packet"]
    assert result["structuredContent"]["auditPacket"]["summary"]["final_case_type"] == (
        "evidence_constrained_governed_recalculation"
    )
    audit_metadata = audit_packet["assumption_buckets"]["metadata"]
    assert audit_metadata["accounting_and_claims"]["governed_scenarios"][0]["topic"] == "rd_capitalization"
    audit_accounting = audit_packet["accounting_decisions"]
    assert audit_accounting["requested"]["rd_capitalization"]["enabled"] is True
    assert audit_accounting["mapped"] == {
        "isExpensesCapitalize": True,
        "rdAmortizationMethod": "straight_line",
        "rdAmortizationPeriodYears": 4,
    }
    assert audit_accounting["governed_scenarios"][0]["topic"] == "rd_capitalization"
    assert audit_accounting["unsupported"] == {}
    scenario_book = result["structuredContent"]["scenarioBook"]
    assert scenario_book["summary"]["main_scenario_type"] == "explicit_scenario"
    assert scenario_book["book"]["scenarios"][0]["type"] == "explicit_scenario"
    assert scenario_book["book"]["scenarios"][0]["source"] == "explicit_user_request"
    assert scenario_book["book"]["scenarios"][0]["accounting_claims_status"]["rdCapitalization"]["status"] == (
        "governed_scenario_supported"
    )


def test_recalculate_rejects_invalid_rd_capitalization_before_service_call():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "NVDA",
            "overrides": {
                "request_policy": {"mode": "explicit_scenario"},
                "rd_capitalization": {
                    "enabled": True,
                    "rd_history": [
                        {
                            "fiscal_year": 2026,
                            "amount": 12_000.0,
                            "source_url": "https://example.com/nvda-2026-10k",
                            "source_date": "2026-02-26",
                        }
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
                },
            },
        },
    )

    assert result["isError"] is True
    unsupported = result["structuredContent"]["assumptions"]["unsupported"]
    assert unsupported["rd_capitalization"]["status"] == "source_required"
    accounting = result["structuredContent"]["assumptions"]["metadata"]["accounting_and_claims"]
    assert accounting["rejected_claims"][0]["topic"] == "rd_capitalization"
    assert client.calls == []


def test_recalculate_blocks_lease_schedule_even_for_explicit_scenario():
    client = FakeClient()
    registry = MCPToolRegistry(client)

    result = registry.call(
        "stockvaluation.recalculate",
        {
            "ticker": "COST",
            "overrides": {
                "request_policy": {"mode": "explicit_scenario"},
                "leases": {
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
            },
        },
    )

    assert result["isError"] is True
    assumptions = result["structuredContent"]["assumptions"]
    audit_accounting = result["structuredContent"]["auditPacket"]["packet"]["accounting_decisions"]
    assert assumptions["mapped"] == {"requestPolicyMode": "explicit_scenario"}
    assert assumptions["unsupported"]["leases"]["status"] == "blocked_report_only"
    assert audit_accounting["requested"]["leases"]["enabled"] is True
    assert audit_accounting["mapped"] == {}
    assert audit_accounting["unsupported"]["leases"]["status"] == "blocked_report_only"
    assert audit_accounting["governed_scenarios"] == []
    assert result["structuredContent"]["auditPacket"]["summary"]["final_case_type"] == (
        "insufficient_researched_evidence"
    )
    assert client.calls == []


def test_report_reference_keeps_mechanical_value_out_of_default_report():
    report = (
        Path(__file__).parents[2]
        / "skills"
        / "stockvaluation-io"
        / "references"
        / "report.md"
    ).read_text()
    lower = report.lower()

    assert "do not show the internal mechanical model value in the default report" in lower
    assert "asks for audit/debug detail" in lower


def test_report_reference_requires_audit_block_with_source_class_and_versions():
    report = (
        Path(__file__).parents[2]
        / "skills"
        / "stockvaluation-io"
        / "references"
        / "report.md"
    ).read_text()
    lower = report.lower()

    assert "audit (gates from run state, evidence/guided status, source class, skill and service versions)" in lower
    assert '"source_class"' in lower
    assert '"skill_version"' in lower
    assert '"service_version"' in lower


def test_missing_service_and_non_json_failures_have_stable_shapes():
    class MissingService(FakeClient):
        def value_ticker(self, ticker, overrides=None):
            raise ServiceUnavailable("connection refused")

    class NonJson(FakeClient):
        def value_ticker(self, ticker, overrides=None):
            raise NonJsonServiceResponse("html body")

    missing = MCPToolRegistry(MissingService()).call("stockvaluation.value_ticker", {"ticker": "MSFT"})
    non_json = MCPToolRegistry(NonJson()).call("stockvaluation.value_ticker", {"ticker": "MSFT"})

    assert missing["structuredContent"]["error"]["code"] == "MISSING_LOCAL_SERVICE"
    assert missing["structuredContent"]["failureCategory"] == "missing_local_service"
    assert non_json["structuredContent"]["error"]["code"] == "NON_JSON_SERVICE_RESPONSE"
    assert non_json["structuredContent"]["failureCategory"] == "non_json_service_response"


def test_currency_conversion_failure_has_specific_agent_readable_shape():
    class CurrencyFailure(FakeClient):
        def value_ticker(self, ticker, overrides=None):
            raise ServiceHTTPError(
                500,
                "Cannot safely value TSM because market price currency USD differs "
                "from financial statement currency TWD and conversion failed.",
            )

    result = MCPToolRegistry(CurrencyFailure()).call("stockvaluation.value_ticker", {"ticker": "TSM"})

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "CURRENCY_CONVERSION_FAILED"
    assert result["structuredContent"]["failureCategory"] == "currency_conversion_failed"
    assert "currency conversion" in result["structuredContent"]["recovery"]["agentAction"].lower()


def test_generic_http_5xx_failure_is_upstream_service_error():
    class UpstreamFailure(FakeClient):
        def value_ticker(self, ticker, overrides=None):
            raise ServiceHTTPError(503, "valuation dependency returned an unexpected service error")

    result = MCPToolRegistry(UpstreamFailure()).call("stockvaluation.value_ticker", {"ticker": "MSFT"})

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "UPSTREAM_SERVICE_ERROR"
    assert result["structuredContent"]["failureCategory"] == "upstream_service_error"
    assert result["structuredContent"]["recovery"]["agentAction"]


def test_explain_failure_extracts_nested_error_message_without_echoing_raw_json():
    registry = MCPToolRegistry(FakeClient())
    message = (
        "Cannot safely value TSM because market price currency USD differs "
        "from financial statement currency TWD and conversion failed."
    )

    result = registry.call(
        "stockvaluation.explain_failure",
        {"error": {"ok": False, "error": {"code": "VALUATION_SERVICE_ERROR", "message": message}}},
    )

    assert result["isError"] is False
    assert result["structuredContent"]["failureCategory"] == "currency_conversion_failed"
    assert result["structuredContent"]["message"] == message
    assert "{'code':" not in result["structuredContent"]["message"]


def test_explain_failure_extracts_nested_error_message_from_json_string_payload():
    registry = MCPToolRegistry(FakeClient())
    message = (
        "Cannot safely value TSM because market price currency USD differs "
        "from financial statement currency TWD and conversion failed."
    )
    payload = {
        "ok": False,
        "tool": "stockvaluation.value_ticker",
        "failureCategory": "currency_conversion_failed",
        "error": {"code": "CURRENCY_CONVERSION_FAILED", "message": message},
    }

    result = registry.call("stockvaluation.explain_failure", {"error": json.dumps(payload)})

    assert result["isError"] is False
    assert result["structuredContent"]["failureCategory"] == "currency_conversion_failed"
    assert result["structuredContent"]["message"] == message
    assert not result["structuredContent"]["message"].startswith("{")


def test_explain_failure_preserves_existing_structured_failure_category():
    registry = MCPToolRegistry(FakeClient())
    payload = {
        "ok": False,
        "tool": "stockvaluation.value_ticker",
        "failureCategory": "upstream_service_error",
        "error": {"code": "UPSTREAM_SERVICE_ERROR", "message": "Valuation failed."},
    }

    result = registry.call("stockvaluation.explain_failure", {"error": payload})

    assert result["isError"] is False
    assert result["structuredContent"]["failureCategory"] == "upstream_service_error"
    assert "upstream error" in result["structuredContent"]["recovery"]["agentAction"].lower()


def test_explain_failure_classifies_frankfurter_provider_failures_as_currency_conversion():
    registry = MCPToolRegistry(FakeClient())

    result = registry.call(
        "stockvaluation.explain_failure",
        {"error": {"message": "Frankfurter currency provider unavailable while loading USD base rates"}},
    )

    assert result["isError"] is False
    assert result["structuredContent"]["failureCategory"] == "currency_conversion_failed"
    assert "currency conversion" in result["structuredContent"]["recovery"]["agentAction"].lower()


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ("Financial companies are unsupported", "unsupported_company"),
        ("financial services sector companies are not supported", "unsupported_company"),
        ("insufficient financial data for ticker", "insufficient_financial_data"),
        ("DEFAULT_PASSWORD is required", "missing_configuration"),
        ("reference data is stale", "stale_reference_data"),
    ],
)
def test_explain_failure_classifies_common_agent_failures(message, category):
    registry = MCPToolRegistry(FakeClient())

    result = registry.call("stockvaluation.explain_failure", {"error": {"message": message}})

    assert result["isError"] is False
    assert result["structuredContent"]["failureCategory"] == category
    assert result["structuredContent"]["recovery"]["agentAction"]
