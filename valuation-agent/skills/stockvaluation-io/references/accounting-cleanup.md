# Accounting Cleanup

Accounting cleanup asks whether reported accounting numbers represent economic operating cash flows. In the current product, most accounting cleanup is explain-only unless the service returns explicit adjustment output.

## When It Matters

- R&D, operating leases, stock-based compensation, restructuring, goodwill impairments, one-time charges, or cyclicality materially affect reported earnings.
- Taxes or NOLs change free cash flow.
- Service output includes accounting adjustment fields.
- The user asks why margins, ROIC, or reinvestment look distorted.

## Evidence Required

- Latest filing or earnings source with the accounting item.
- Service-returned adjustment fields for R&D capitalization, operating lease conversion, options/warrants, tax rate, and NOLs when available.
- Multi-year evidence before any future governed normalization support is used.

## Allowed action

- Explain service-returned accounting adjustments.
- Flag material accounting items that may affect interpretation.
- State when an adjustment is unavailable in MCP/service output.
- Preserve evidence for future user-requested scenarios without changing the model autonomously.

## Do not

- Do not autonomously normalize one-time charges.
- Do not toggle R&D capitalization, operating leases, options, NOLs, tax, restructuring, or stock-based compensation adjustments.
- Do not treat explain-only accounting commentary as a model change.
- Do not calculate missing valuation values outside MCP/service output.

## Report Guidance

The report should separate "reported accounting issue" from "service-returned model adjustment." If the service did not return the adjustment, explain the limitation plainly.

## QA Expectation

Accounting sections must not alter intrinsic value unless the value came from MCP/service output.
