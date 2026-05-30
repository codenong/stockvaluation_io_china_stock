# Options, Leases, And Other Claims

Claims outside operating assets bridge operating value to common equity value. Explain them when the service returns them; do not invent them. Use AccountingAndClaims statuses to distinguish returned values from missing schedules, zero_by_default defaults, source_required gaps, governed scenario support, and unsupported direct claims.

## When It Matters

- The service returns debt, cash, minority interests, non-operating assets, value of options, lease conversion, or option/warrant fields.
- Employee options or warrants are material.
- Lease commitments are economically debt-like.
- The gap between operating asset value and common equity value is material.

## Evidence Required

- Service-returned `companyDTO` bridge fields.
- Service-returned option or lease adjustment fields.
- Service-returned AccountingAndClaims status for leases, options/warrants, cash, debt, and share count.
- Cited filing evidence only for discussion, not autonomous model changes.

## Allowed action

- Explain returned debt, cash, minority interests, non-operating assets, value of options, and common-equity bridge.
- Explain operating lease conversion only when service output returns it; otherwise label `zero_by_default`, `missing`, or `source_required`.
- Leases are report-only in Phase 5; use AccountingAndClaims status rather than sending lease schedules as model inputs.
- Explain option overhang only when service output returns option value or the user asks for qualitative context.

## Do not

- Do not invent option values, lease liabilities, pensions, minority interests, or non-operating assets.
- Do not pass lease, option, or other-claim adjustments as autonomous researched changes.
- Do not send lease schedules through `stockvaluation.recalculate`; Phase 5 has no governed lease scenario path.
- Direct claim value overrides remain blocked unless a future governed scenario contract explicitly supports them.
- Do not combine operating performance and claims in one unexplained number.
- Do not calculate missing valuation values outside MCP/service output.

## Report Guidance

Show a bridge from operating value to common equity only with returned fields. If fields are absent, say the bridge is unavailable or omit the table.

## QA Expectation

Reports must keep other claims separate from growth, margins, and reinvestment.
