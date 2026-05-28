# Assumption Judgment

Produce a strict `assumption_judgment` JSON object before calling `stockvaluation.recalculate`.

Use `{baseDir}/references/driver-specific-evidence.md` and `{baseDir}/references/baseline-plausibility.md` before producing this object. Generic source presence must not appear in `evidence_used`; every item must be tied to a valuation driver and a relevant fact.

## Contract

```json
{
  "baseline_assumptions": {
    "revenue_cagr": null,
    "operating_margin_next_year": null,
    "operating_margin": null,
    "sales_to_capital": null
  },
  "baseline_plausibility": {
    "baseline_quality": "plausible|challenged|unsupported_mechanical_only",
    "mechanical_baseline_label": "mechanical baseline",
    "price_value_gap_flag": {
      "flagged": true,
      "threshold_pct": 50,
      "gap_pct": null,
      "reason": "string"
    },
    "optimistic_assumption_stack": {
      "flagged": true,
      "flags": [
        {
          "driver": "revenue_growth|operating_margin|reinvestment_sales_to_capital|risk_wacc|terminal_value_mature_state|accounting_adjustments",
          "baseline_value": null,
          "comparison_value": null,
          "reason": "string"
        }
      ]
    },
    "market_implied_diagnostics_status": "report_only_not_evidence",
    "researched_case_status": "governed_recalculation|no_governed_change|blocked_by_unsupported_fields",
    "unsupported_blockers": [
      {
        "field": "string",
        "reason": "string"
      }
    ]
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
  ],
  "dcf_adjustment_instructions": [
    {
      "parameter": "revenue_cagr|operating_margin|sales_to_capital",
      "new_value": 0,
      "unit": "percent|x",
      "rationale": "string"
    }
  ],
  "sector_adjustment_instructions": [
    {
      "sector": "string",
      "parameter": "revenue_growth|operating_margin|sales_to_capital",
      "value": 0,
      "unit": "percent|x",
      "adjustment_type": "absolute|relative_multiplier|relative_additive",
      "timeframe": "years_1_to_5|years_6_to_10|both",
      "rationale": "string"
    }
  ],
  "confidence": "low|medium|high",
  "assumptions_left_unchanged": [
    {
      "parameter": "revenue_cagr|operating_margin_next_year|operating_margin|sales_to_capital",
      "reason": "string"
    }
  ],
  "no_change_reason": "string|null"
}
```

## Governed Changes

Autonomous judgment may only propose changes to:

- `revenue_cagr`
- `operating_margin`
- `sales_to_capital`
- Sector-level versions of revenue growth, operating margin, and sales-to-capital

`operating_margin` maps to target operating margin only. Do not use it as a substitute for next-year operating margin path support.

`operating_margin_next_year` is not a governed autonomous MCP override. It is available only for explicit user scenarios such as guided refinement, and it must not be used as a substitute for target operating margin.

Do not autonomously change WACC, terminal growth, tax rate, cash, debt, share count, market price, terminal value, equity value, option value, or other direct valuation-output fields.

Evidence for risk/WACC, terminal value, accounting adjustments, leases, R&D capitalization, options, NOLs, one-time charges, tax, cash, debt, share count, and direct valuation-output fields may explain the report or be flagged as unsupported. It must not be converted into an autonomous recalculate override.

## Evidence Strength Gate

Before proposing a governed change, verify:

- The evidence is driver-specific, dated, cited, and stronger than generic source presence.
- `direction`, `confidence`, and `assumption_implication` are populated.
- `allowed_to_affect_autonomous_recalculation` is `true`.
- `model_action` is `governed assumption change`.
- The driver maps to revenue growth, operating margin, sales-to-capital, or a sector-level version of those same drivers.
- Conflicting evidence and data-quality warnings have been considered.
- Baseline plausibility has been considered, including price/value gap, growth anchor, market-implied diagnostics, margin path, reinvestment, terminal durability, risk, and accounting flags.

If any condition fails, keep the relevant assumption baseline/conservative and explain the no-change reason.

## Recalculate Payload Mapping

After producing `assumption_judgment`, convert only governed instructions into `stockvaluation.recalculate` overrides:

- `revenue_cagr` maps to `revenue_growth`.
- `operating_margin` maps to `operating_margin`.
- `sales_to_capital` maps to `sales_to_capital`.
- `operating_margin_next_year` does not map to an autonomous override; flag it in `baseline_plausibility.unsupported_blockers` for the evidence-constrained base and reserve it for `user_refined_scenario` or `explicit_scenario`.
- `dcf_adjustment_instructions` map to `stockvaluation.recalculate` overrides.
- `sector_adjustment_instructions` map to `sector_overrides`.
- `evidence_used` stays attached to the recalculate metadata.
- Use a short `rationale` that summarizes why the governed changes were or were not made.

## Fail-Closed Rules

- Weak, mixed, stale, or uncited evidence means no autonomous adjustment.
- Generic source presence means no autonomous adjustment.
- Evidence must include source URLs and dates before it can support a change.
- Keep requested, mapped, unsupported, and effective assumptions separate after recalculation.
- If there are no governed changes, set `dcf_adjustment_instructions` and `sector_adjustment_instructions` to empty arrays and explain `no_change_reason`.
- If the mechanical baseline is challenged but no governed change is allowed, set `baseline_plausibility.researched_case_status` to `blocked_by_unsupported_fields` or `no_governed_change` and list the unsupported blockers instead of calling the mechanical baseline rational.
- Market-implied diagnostics are report-only, not evidence, and must not appear as evidence for autonomous changes.

## Distinct User Judgment Package

Keep `assumption_judgment` autonomous. Do not mix user answers into `evidence_used`.

Guided refinement uses a separate `user_judgment` package:

```json
{
  "source_type": "user_judgment",
  "scenario_label": "user-refined scenario",
  "answers": [],
  "requested_assumptions": {},
  "mapped_assumptions": {},
  "unsupported_assumptions": {},
  "not_evidence_statement": "User answers define a scenario; they are not independent evidence."
}
```

Attach `user_judgment` as recalculate metadata only when calling `stockvaluation.recalculate` with `request_policy.mode = "user_refined_scenario"` or `request_policy.mode = "explicit_scenario"`.
