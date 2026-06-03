# Financial Field Definitions

Canonical source: `valuation-service/src/main/resources/data/financial_field_definitions.json`.

SEC and Yahoo are adapters into the same StockValuation financial schema. The service-owned JSON is the machine-readable contract for field meaning, accepted SEC concepts, accepted Yahoo keys, reconciliation thresholds, and field-level audit provenance. This reference mirrors the canonical field list for report writing; do not treat it as a separate source of truth.

## Allowed Action

- Use `stockvaluation.researched_baseline` for default full researched baseline runs.
- In the final educational report, summarize source class, provider, source date, period end, source policy status, `sourceQualityGate`, and material warnings compactly.
- Use field-level provenance and data-quality warnings from audit/debug surfaces when discussing revenue, operating income, cash, debt, shares, R&D, SBC, tax, pretax income, minority interest, or book equity.
- Explain that Yahoo-normalized fallback can fill the same schema, but it is not primary-filing data.
- For non-US Yahoo-normalized researched valuations, say company-report cross-check is required before researched claims when `company_report_check_pending` is present.

## Canonical Fields

- `revenue`: duration income-statement revenue used for scale, growth, and margin denominator.
- `operating_income`: duration income-statement operating profit used for current margin and profitability context.
- `interest_expense`: duration income-statement interest cost used for debt-cost diagnostics and accounting context.
- `tax_provision`: duration income-statement tax expense or benefit used for effective-tax interpretation.
- `pretax_income`: duration income-statement pretax income used with tax provision for effective-tax diagnostics.
- `research_and_development`: duration R&D expense used for accounting-cleanup diagnostics; autonomous researched mode does not capitalize it.
- `basic_shares`: duration average basic shares; do not mix with point-in-time shares without warning.
- `diluted_shares`: duration average diluted shares; report dilution context but do not override share count autonomously.
- `shares_outstanding`: point-in-time common shares used for per-share equity bridge.
- `book_equity`: point-in-time balance-sheet equity used for invested-capital and accounting context.
- `total_debt`: point-in-time debt used in the claims bridge; direct debt overrides remain blocked in autonomous researched mode.
- `cash_and_short_term_investments`: point-in-time cash and short-term investments used in the claims bridge; direct cash overrides remain blocked in autonomous researched mode.
- `minority_interest`: point-in-time noncontrolling interest used in claims and equity bridge context.
- `stock_based_compensation`: duration SBC used for report-only SBC and dilution diagnostics.

## Reconciliation Rules

Use service-returned `dataQualityWarnings` first. The canonical JSON currently defines these thresholds: 5% for default core fields, revenue, operating income, cash and short-term investments, and total debt; 2% for share counts; 10% for R&D, SBC, tax provision, pretax income, and minority interest. Always surface sign mismatches for operating income, tax provision, and pretax income; missing/present material mismatches for R&D, SBC, and minority interest; and unit, currency, period, stale source-date, fallback tag/key, missing required field, and average-share versus point-in-time-share warnings.

## Do Not

- Do not describe Yahoo-normalized data as `primary_filing`.
- Do not infer accounting cleanup support from a numeric value alone.
- Do not turn report-only fields such as R&D capitalization, SBC dilution, cash, debt, or share-count changes into autonomous researched model inputs.
- Do not hardcode ticker-specific support claims. SEC/20-F/IFRS support is capability-based and must be returned by the service.
- Do not copy test fixtures into production support logic or report them as live filing coverage.
