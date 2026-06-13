# Accounting And Claims

`AccountingAndClaims` in the service output is the structured status source for accounting cleanup and capital-claim topics. Most topics are report-only: explain returned values, flag materiality, and never invent adjustments. Status vocabulary: `returned`, `missing`, `zero_by_default`, `source_required`, `blocked_report_only`, `governed_scenario_supported`, `unsupported`, plus `stale` / `reconciled` / `conflict` for cash, debt, and share-count reconciliation. Never infer support from a numeric zero.

## Topic Rules

- **R&D capitalization**: automatic in the normal autonomous researched flow when the payload has multi-year R&D history, an amortization policy (method and period), and retrieved non-Yahoo source provenance. The same governed source-backed payload also works in `request_policy.mode = "explicit_scenario"`. The validator rejects anything less. Never infer a research asset from one expense line or a bare true/false flag.
- **Operating leases**: report-only; explain returned conversions; never send lease schedules through `recalculate`.
- **Options / warrants / dilution**: explain returned option value and dilution separately from operating performance; SBC diagnostics (SBC % of revenue, diluted share-count trend) are report-only economics.
- **Tax and NOLs**: explain returned effective assumptions; never invent NOL schedules or tax shields.
- **One-time charges / restructuring / impairments**: never autonomously normalize.
- **Cash, debt, share count**: report the source/reconciliation status before discussing the claims; direct claim-value overrides remain blocked.

## Equity Bridge

Show the bridge from operating value to common equity only from returned `companyDTO` fields (debt, cash, minority interests, non-operating assets, value of options). If fields are absent, omit the table — the report builder never writes filler. Keep claims separate from growth, margins, and reinvestment.

## Field Definitions

Read canonical fields from the service: revenue and prior revenue (consolidated rows, not segment subrows), operating income (loss) from operations, cash and short-term investments, total debt, book equity, operating cash flow, capital expenditures, share counts with explicit basis (`pro_forma_post_offering` vs reported). Never mix period bases silently; flag mixed quarterly balance-sheet and yearly share data instead of reconciling by hand. The report separates "reported accounting issue" from "service-returned model adjustment" and states limitations plainly.
