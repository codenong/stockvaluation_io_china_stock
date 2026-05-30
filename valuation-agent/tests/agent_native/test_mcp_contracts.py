import json
from pathlib import Path

import pytest

from valuation_agent.mcp_tools import MCPToolRegistry
from valuation_agent.mcp_server import MCPJSONRPCServer
from valuation_agent.service_client import (
    NonJsonServiceResponse,
    ServiceHTTPError,
    ServiceUnavailable,
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


class FakeClient:
    def __init__(self, payload=None):
        self.payload = payload or _valuation_payload()
        self.calls = []

    def health(self):
        return {"status": "UP"}

    def value_ticker(self, ticker, overrides=None):
        self.calls.append((ticker, overrides or {}))
        return self.payload


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


def test_mcp_tools_list_has_required_stockvaluation_contracts():
    registry = MCPToolRegistry(FakeClient())

    tools = registry.list_tools()
    names = {tool["name"] for tool in tools}

    assert names == {
        "stockvaluation.health",
        "stockvaluation.value_ticker",
        "stockvaluation.recalculate",
        "stockvaluation.get_assumptions",
        "stockvaluation.get_growth_anchor",
        "stockvaluation.get_reference_data_status",
        "stockvaluation.explain_failure",
    }
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert tool["outputSchema"]["type"] == "object"


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
        "sourcePolicyStatus": "primary_source_missing_fallback",
        "warnings": [
            "US researched valuation is using Yahoo-normalized financials because primary filing data is missing or unavailable."
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
        "sourcePolicyStatus": "primary_source_missing_fallback",
        "warnings": [
            "US researched valuation is using Yahoo-normalized financials because primary filing data is missing or unavailable."
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
            }
        ],
    }
    visible_text = result["content"][0]["text"]
    assert "primary_source_missing_fallback" in visible_text
    assert len(visible_text) < 600


def test_recalculate_preserves_compact_source_provenance_metadata():
    payload = _valuation_payload()
    payload["assumptionTransparency"]["sourceProvenance"] = {
        "sourceClass": "yahoo_normalized",
        "provider": "yfinance-http",
        "sourceDate": "2025-06-30",
        "periodEnd": "2025-06-30",
        "retrievalStatus": "retrieved",
        "crossCheckStatus": "company_report_cross_checked",
        "sourcePolicyStatus": "yahoo_normalized_with_cross_check_status",
        "warnings": ["Company report cross-check status is explicit for Yahoo-normalized data."],
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
        "sourcePolicyStatus": "yahoo_normalized_with_cross_check_status",
        "warnings": ["Company report cross-check status is explicit for Yahoo-normalized data."],
        "dataQualityWarnings": [],
    }
    visible_text = result["content"][0]["text"]
    assert "yahoo_normalized_with_cross_check_status" in visible_text
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
    client = FakeClient()
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
                "options": {"value": 100},
                "nols": 10,
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
        "options",
        "nols",
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
    assert client.calls == []


def test_report_template_requires_baseline_use_status_before_assumptions():
    template = (
        Path(__file__).parents[2]
        / "skills"
        / "stockvaluation-io"
        / "references"
        / "report-template.md"
    ).read_text()

    snapshot = template.index("## Valuation Snapshot")
    assumption_summary = template.index("## Assumption Judgment Summary")

    assert "Baseline use status" in template[snapshot:assumption_summary]
    assert "target operating margin source/status" in template[snapshot:assumption_summary].lower()


def test_report_template_requires_source_quality_summary():
    template = (
        Path(__file__).parents[2]
        / "skills"
        / "stockvaluation-io"
        / "references"
        / "report-template.md"
    ).read_text()
    lower = template.lower()

    assert "## Source Quality Summary" in template
    assert "source class" in lower
    assert "source policy status" in lower
    assert "cross-check status" in lower
    assert "primary_filing_used" in lower
    assert "primary_source_missing_fallback" in lower
    assert "yahoo_normalized_with_cross_check_status" in lower


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
