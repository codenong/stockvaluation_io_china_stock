# Accounting Cleanup

Accounting cleanup asks whether reported accounting numbers represent economic operating cash flows. In the current product, AccountingAndClaims is the structured status source for accounting cleanup and capital-claim topics. Most topics are report-only unless the service returns explicit adjustment output or a tested governed accounting scenario accepts the payload.

## When It Matters

- R&D, operating leases, stock-based compensation, restructuring, goodwill impairments, one-time charges, or cyclicality materially affect reported earnings.
- Taxes or NOLs change free cash flow.
- Service output includes accounting adjustment fields.
- The user asks why margins, ROIC, or reinvestment look distorted.

## Evidence Required

- Latest filing or earnings source with the accounting item.
- Service-returned AccountingAndClaims statuses for R&D capitalization, SBC/dilution, leases, options/warrants, NOL/tax, cash, debt, and share count.
- Service-returned SBC diagnostics when available: SBC percent of revenue, SBC percent of operating income or free cash flow, diluted share-count trend, and diluted-share consistency status.
- Cash, debt, and share-count source/reconciliation status: returned, missing, stale, reconciled, conflict, or source_required.
- Multi-year evidence, source provenance, and audit recording before governed normalization support is used.

## Allowed action

- Explain service-returned accounting adjustments.
- Flag material accounting items that may affect interpretation.
- State when an adjustment is unavailable in MCP/service output.
- Use supported versus report-only accounting labels from AccountingAndClaims.
- Report SBC/dilution diagnostics as report-only economics, not model changes.
- Report cash, debt, and share-count source and reconciliation status before discussing those claims.
- Preserve evidence for future user-requested scenarios without changing the model autonomously.

## Do not

- Do not autonomously normalize one-time charges.
- Do not toggle R&D capitalization except through its Phase 5 governed accounting scenario path. Do not toggle operating leases, options, NOLs, tax, restructuring, or stock-based compensation adjustments.
- Do not treat explain-only accounting commentary as a model change.
- Do not infer accounting support from a numeric zero; require `returned`, `missing`, `zero_by_default`, `source_required`, `blocked_report_only`, `governed_scenario_supported`, or `unsupported`.
- Do not calculate missing valuation values outside MCP/service output.

## Report Guidance

The report should separate "reported accounting issue" from "service-returned model adjustment." If the service did not return the adjustment, explain the limitation plainly and use the AccountingAndClaims status rather than inventing support.

## QA Expectation

Accounting sections must not alter intrinsic value unless the value came from MCP/service output.
