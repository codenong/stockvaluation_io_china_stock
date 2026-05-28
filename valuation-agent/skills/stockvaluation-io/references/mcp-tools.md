# MCP Tools

All StockValuation tools return MCP `structuredContent` with JSON. Read `structuredContent` first. The text block is a serialized copy for clients that do not expose structured output.

## `stockvaluation.health`

Checks the local MCP adapter and valuation service.

Input:

```json
{}
```

Expected output:

```json
{
  "ok": true,
  "tool": "stockvaluation.health",
  "service": {
    "name": "stockvaluation-service",
    "status": "UP"
  },
  "mcp": {
    "name": "valuation-agent",
    "version": "0.1.0"
  }
}
```

## `stockvaluation.value_ticker`

Fetches the baseline local DCF JSON.

Input:

```json
{
  "ticker": "MSFT"
}
```

Use these output sections:

- `valuation`: full valuation-service payload.
- `dcf`: compact DCF summary for reporting.
- `baseline`: normalized live baseline contract for report writers.
- `assumptions`: grouped assumptions and rationales.
- `growthAnchor`: Damodaran growth-anchor mapping, confidence, percentile band, source date, and warnings.
- `referenceData`: market-data and reference-data status.
- `warnings`: service and data-quality notes.
- `policy`: educational-use and no-advice guardrails.

Read `baseline` before presenting assumptions:

- `baseline.baselineQuality`: `segment_weighted_baseline`, `single_industry_fallback`, `segment_evidence_insufficient`, `segment_mapping_blocked`, or `not_calculated`.
- `baseline.baselineUseStatus`: `validated_segment_weighted`, `mechanical_only`, `segment_evidence_insufficient`, `challenged_baseline`, or `blocked`.
- `baseline.segmentAware`, `baseline.segmentCount`, `baseline.segmentCoveragePct`, `baseline.mappedIndustries`, and `baseline.weightedBaselineAssumptions`.
- `baseline.baselineWarnings`, `baseline.unsupportedBaselineDrivers`, and `baseline.unsupportedAdjustmentFields`.
- `baseline.targetOperatingMargin`, `baseline.targetOperatingMarginSource`, and `baseline.targetOperatingMarginStatus`.

If `baselineUseStatus` is `mechanical_only`, `segment_evidence_insufficient`, `challenged_baseline`, or `blocked`, do not present target operating margin as a validated researched or segment-weighted assumption. A single-industry fallback can be shown as deterministic mechanical output, but it is not evidence-constrained research.

Reportable rich-output fields are nested in `valuation` when the Java service returns them:

- `valuation.assumptionTransparency.baselineQuality`: `segment_weighted_baseline`, `single_industry_fallback`, `segment_evidence_insufficient`, or `segment_mapping_blocked`.
- `valuation.assumptionTransparency.baselineUseStatus`: whether the baseline is validated for researched use or only mechanical/challenged.
- `valuation.assumptionTransparency.segmentCoveragePct`: percent of company revenue represented by accepted mapped segment evidence.
- `valuation.assumptionTransparency.mappedIndustries`: industry rows used for segment weighting.
- `valuation.assumptionTransparency.weightedBaselineAssumptions`: segment-weighted growth, target operating margin, sales-to-capital, and discount-rate assumptions used before researched overrides.
- `valuation.assumptionTransparency.baselineWarnings`, `unsupportedBaselineDrivers`, `unsupportedAdjustmentFields`, `targetOperatingMarginSource`, and `targetOperatingMarginStatus`.
- `valuation.assumptionTransparency.marketImpliedExpectations`: single-variable implied growth, margin, and sales-to-capital checks.
- `valuation.assumptionTransparency.pricedInExpectations`: priced-in expectation grid and scenario package.
- `valuation.assumptionTransparency.pricedInExpectations.frontier`: break-even or priced-in operating-margin vs implied-growth frontier.
- `valuation.assumptionTransparency.pricedInExpectations.scenarios`: scenario headline table with risk and capital-efficiency settings.
- `valuation.assumptionTransparency.pricedInExpectations.grid`: sensitivity grid when returned.
- `valuation.companyDTO.pvTerminalValue`, `valuation.companyDTO.pvCFOverNext10Years`, `valuation.companyDTO.terminalCashFlow`, and `valuation.companyDTO.terminalValue`: terminal value and cash-flow composition.
- `valuation.financialDTO.fcff`, `valuation.financialDTO.reinvestment`, and `valuation.financialDTO.roic`: free-cash-flow, reinvestment, and return-on-capital trajectories.

Use these fields as report inputs, not autonomous model changes. Market-implied fields are not evidence. If a field is absent, say it is unavailable or omit the related table.

## `stockvaluation.recalculate`

Recalculates deterministic DCF output with governed scenario overrides. In the default full researched valuation workflow, call it once after producing `assumption_judgment` when the payload is supported.

Input:

```json
{
  "ticker": "MSFT",
  "overrides": {
    "revenue_growth": 8.5,
    "operating_margin_next_year": 39.0,
    "operating_margin": 42.0,
    "target_operating_margin": 42.0,
    "margin_convergence_year": 6,
    "sales_to_capital": 2.4,
    "sales_to_capital_years_1_to_5": 2.4,
    "sales_to_capital_years_6_to_10": 2.0,
    "wacc": 8.25,
    "terminal_growth": 3.0,
    "tax_rate": 21.0,
    "segments": [
      {
        "segment_name": "Cloud software",
        "sector": "Cloud software",
        "mapped_industry": "Software",
        "components": ["Azure"],
        "mapping_score": 0.9,
        "mapping_confidence": "high",
        "revenue_share": 0.525,
        "source_name": "FY annual report",
        "source_date": "2026-06-30",
        "source_url": "https://example.com/annual-report",
        "validation_warnings": [],
        "operating_margin": 43.0
      }
    ],
    "sector_overrides": [
      {
        "sector": "Cloud software",
        "parameter": "revenue_growth",
        "value": 12.0,
        "unit": "percent",
        "adjustment_type": "absolute",
        "timeframe": "years_1_to_5",
        "rationale": "Cited segment evidence supports the adjustment."
      }
    ],
    "growth_pattern_override": "THREE_STAGE",
    "request_policy": {
      "mode": "user_refined_scenario"
    },
    "rationale": "Brief reason for the governed recalculation.",
    "user_judgment": {
      "source_type": "user_judgment",
      "scenario_label": "user-refined scenario",
      "answers": []
    },
    "evidence_used": [
      {
        "claim": "string",
        "source_title": "string",
        "source_url": "string",
        "source_date": "YYYY-MM-DD or unknown",
        "evidence_type": "filing|earnings|company_news|macro|segment",
        "driver": "revenue_growth|operating_margin|reinvestment_sales_to_capital|risk_wacc|terminal_value_mature_state|accounting_adjustments",
        "direction": "supports higher assumption|supports lower assumption|neutral/mixed",
        "confidence": "high|medium|low",
        "assumption_implication": "string",
        "allowed_to_affect_autonomous_recalculation": true,
        "model_action": "governed assumption change|report explanation only|explain/flag only unsupported"
      }
    ]
  }
}
```

Supported override keys:

- `revenue_growth`
- `operating_margin_next_year` (scenario-only; rejected in autonomous researched mode)
- `operating_margin` (target operating margin only)
- `target_operating_margin`
- `target_pre_tax_operating_margin`
- `margin_convergence_year`
- `sales_to_capital`
- `sales_to_capital_years_1_to_5`
- `sales_to_capital_years_6_to_10`
- `wacc`
- `terminal_growth`
- `tax_rate`
- `segments`
- `sector_overrides`
- `growth_pattern_override`
- `request_policy`
- `rationale`
- `evidence_used`
- `user_judgment`

Request policy modes:

- `mechanical_baseline`: no discretionary valuation judgment. Use for mechanical baseline context only.
- `autonomous_researched`: strict evidence-constrained mode. Only governed driver evidence may change supported autonomous fields.
- `user_refined_scenario`: bounded user-judgment scenario after guided refinement. User answers are scenario inputs, not evidence.
- `explicit_scenario`: user explicitly requests a scenario outside the default guided flow.

`segments` may be a list or an object with a `segments` list. Segment package fields required for baseline use are segment name, revenue weight or revenue amount, source name, source date, source URL or reference, mapped industry, mapping confidence, and validation warnings. Revenue weights may be decimals that sum near `1.0` or percentages that sum near `100`; MCP maps them to service decimal weights. Segment names without revenue weights, generic source presence, missing source metadata, low mapping confidence, or less than 80% mapped coverage are rejected from segment weighting and reported as unsupported.

Baseline quality values:

- `segment_weighted_baseline`: credible segment package was used.
- `single_industry_fallback`: no segment package was available.
- `segment_evidence_insufficient`: names or generic sources were found without enough revenue-weighted evidence.
- `segment_mapping_blocked`: revenue evidence exists but mapped industry coverage or confidence was insufficient.

For autonomous assumption judgment, only driver-specific evidence for `revenue_growth`, `operating_margin`, `sales_to_capital`, and sector-level `sector_overrides` for those same parameters may change. `segments`, `rationale`, and `evidence_used` are context or metadata. Do not use `growth_pattern_override` autonomously; reserve it for explicit user-requested scenarios or supported payloads that are not autonomous judgment changes. Do not autonomously change `operating_margin_next_year`, WACC, terminal growth, tax rate, cash, debt, share count, market price, accounting adjustments, or direct valuation outputs.

`operating_margin_next_year` is scenario-only in autonomous researched mode. User-refined and explicit scenarios may send it directly, and it must not silently set `targetPreTaxOperatingMargin`.

User-refined scenario mode may send direct valid inputs for revenue growth, operating margin next year, target operating margin, margin convergence year, sales-to-capital years 1-5, sales-to-capital years 6-10, `segments`, and sector-level revenue growth, operating margin, and sales-to-capital. Sales-to-capital scenario inputs must remain auditable and must not be silently replaced by mechanical guards.

`margin_convergence_year` must be a finite projection year from 1 to 10. Sales-to-capital inputs must be finite positive multiples from 0.05x to 20x. Out-of-bounds values are rejected instead of silently capped.

`user_refined_scenario` must not send WACC, terminal growth, tax rate, or `growth_pattern_override`; those are explicit-scenario-only fields when the user asks for that specific scenario outside bounded guided refinement.

Terminal growth must remain within mature-economy and risk-free-rate constraints. If a requested terminal growth is unsafe, the service should reject it with an agent-readable error rather than silently accepting or capping it.

Generic source presence is not evidence. Do not attach "10-K found" or "SEC filing source captured" as support for a researched recalculate call.

The response separates:

- `assumptions.requested`: what the user or agent requested.
- `assumptions.mapped`: fields sent to the valuation service.
- `assumptions.unsupported`: rejected fields.
- `assumptions.effective`: what the service actually used.
- `assumptions.metadata`: rationale and evidence preserved for auditability but not sent to the valuation service.
- `baseline`: live baseline quality/use-status contract after validation or rejection.

Do not pass debt, cash, share count, market price, option value, fair value, target price, terminal value, equity value, upside/downside, direct market-price calibration, or other direct valuation-output fields.

## `stockvaluation.get_assumptions`

Returns the current assumption transparency slice for a ticker.

Input:

```json
{
  "ticker": "MSFT"
}
```

Use it when the user asks for assumption critique without requiring the full valuation payload again.

## `stockvaluation.get_growth_anchor`

Returns the mapped growth anchor:

- mapped entity
- region
- year
- confidence
- percentile band
- source date
- warnings

## `stockvaluation.get_reference_data_status`

Returns service/reference-data status. With a ticker, it can include ticker-specific growth-anchor metadata.

## `stockvaluation.explain_failure`

Classifies structured errors into agent-readable categories:

- `unsupported_company`
- `insufficient_financial_data`
- `missing_local_service`
- `missing_configuration`
- `stale_reference_data`
- `non_json_service_response`
- `currency_conversion_failed`
- `upstream_service_error`
- `unknown_failure`

Use it before explaining failures to the user.
