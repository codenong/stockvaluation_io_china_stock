# Baseline Plausibility And Evidence-Constrained Base

Use this reference after driver-specific evidence extraction and before `assumption_judgment`.

The goal is to keep the deterministic service output visible as the mechanical baseline while deciding whether it is strong enough to describe as an evidence-constrained researched base case.

## Core Definitions

- `mechanical_baseline`: the first successful `stockvaluation.value_ticker` output. It is useful model output, but it may reflect service/reference defaults rather than a researched base case.
- `evidence_constrained_base`: the researched case after the plausibility gate, driver-specific evidence review, and any governed `stockvaluation.recalculate` call. If no governed change is allowed, it can be a no-change researched case with explicit blockers.
- `market_implied_diagnostics`: service-returned `marketImpliedExpectations`, `pricedInExpectations`, frontier, grid, and scenario data. These are report diagnostics only. They are not evidence and must not become autonomous model changes.
- `optimistic_assumption_stack`: a combination of favorable assumptions, such as high forward growth, high margins, favorable sales-to-capital, low-risk mature-state assumptions, and terminal durability that together need stronger evidence than any one input alone.
- `unsupported_blockers`: assumption problems that the current governed workflow cannot autonomously fix, such as next-year margin path, WACC, terminal growth, tax, accounting adjustments, options, leases, NOLs, cash, debt, share count, market price, or direct valuation-output fields.

## Required Inputs

Use only returned MCP JSON and driver-specific evidence:

- Mechanical baseline DCF summary, assumptions, warnings, and model/growth pattern.
- Growth-anchor p25/p50/p75, confidence, mapped entity, region, and warnings.
- Market price and model intrinsic value per share.
- `marketImpliedExpectations` and `pricedInExpectations` when returned.
- Driver-specific evidence for revenue growth, operating margin, reinvestment/sales-to-capital, risk/WACC, terminal mature state, and accounting adjustments.
- Recalculate response metadata when a governed recalculate call succeeds: requested, mapped, unsupported, metadata, and effective assumptions.

Do not invent missing values. If a field is absent, mark it unavailable and explain the limitation.

## Plausibility Gate

Run these checks before treating a mechanical baseline as a researched base case.

### Price / Value Gap

Flag the baseline when either condition is true:

- Absolute gap between model value and market price is greater than 50%.
- Service warnings or growth pattern indicate a forced `THREE_STAGE` upgrade because price and intrinsic value diverged materially.

This flag does not mean the market price is correct. It means the assumption stack needs evidence review.

### Growth

Flag growth when one or more conditions are true:

- Baseline years 2-5 revenue growth is above the growth-anchor p75 band.
- Baseline years 2-5 revenue growth is materially above market-implied revenue growth.
- Trailing revenue growth is strong, but there is no cited forward evidence for the runway, segment mix, pricing, demand, bookings, backlog, or TAM.

Trailing growth alone is not enough to support a high forward runway.

### Margin Path

Evaluate next-year operating margin and target operating margin separately.

- `operating_margin_next_year` is scenario-only for guided refinement or explicit scenarios. Treat next-year margin as an unsupported margin-path blocker in autonomous researched mode.
- `operating_margin` maps to target operating margin only.
- Compare next-year margin to trailing evidence, current mix, operating leverage, cost structure, and market-implied diagnostics.
- Compare target margin to trailing evidence and durable mature-state evidence. Do not treat target-margin support as proof that the next-year margin path is supported.

### Reinvestment / Sales-To-Capital

Flag reinvestment when high growth depends on favorable sales-to-capital without support from capex, R&D, working-capital, capacity, acquisition, or segment evidence.

R&D and capex intensity should be visible in the report even when they are not autonomous override fields.

### Risk, Terminal, And Accounting

Risk/WACC, terminal mature-state, and accounting evidence can challenge the baseline, but they are explain/flag only unless a current governed contract explicitly supports the change and tests cover it.

Do not autonomously change WACC, terminal growth, tax, R&D capitalization, leases, options, NOLs, cash, debt, share count, market price, equity value, terminal value, or direct valuation outputs.

## Output Shape

Add a `baseline_plausibility` object to `assumption_judgment`:

```json
{
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
}
```

## Fail-Closed Rules

- If evidence is weak, mixed, stale, uncited, generic, or not driver-specific, keep assumptions baseline/conservative and document why.
- If a problematic field is unsupported, flag it as an unsupported blocker instead of silently accepting the mechanical baseline as rational.
- If market-implied diagnostics suggest different assumptions, report them as diagnostics only. Do not use them as evidence and do not send them to `stockvaluation.recalculate`.
- If there are governed evidence-constrained changes, send only supported fields to `stockvaluation.recalculate` and preserve requested, mapped, unsupported, metadata, and effective assumptions separately.
- If there are no governed changes, write an evidence-constrained no-change case that explicitly says why the mechanical baseline remains challenged.

## NVDA-Like Acceptance Pattern

An NVDA-like case should trigger an optimistic-baseline warning when the mechanical baseline value is materially above market price and the assumptions stack high years 2-5 growth, a very high next-year margin path, favorable sales-to-capital, and mature-state durability that is not fully supported by driver-specific evidence.

The report must not call that mechanical baseline the rational researched base. It must show the mechanical baseline, the evidence-constrained researched status, market-implied diagnostics, assumptions left unchanged, and unsupported blockers.
