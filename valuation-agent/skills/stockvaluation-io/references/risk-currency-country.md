# Risk, Currency, And Country

Risk belongs in the report, but autonomous WACC changes are not currently allowed in researched judgment. The agent explains returned risk fields and flags uncertainty.

## When It Matters

- Cash-flow currency, stock currency, and discount-rate inputs may not align.
- The company has material country, commodity, regulatory, or cyclicality exposure.
- The model value only works under optimistic cost-of-capital assumptions.
- Service warnings mention currency conversion, stale reference data, or low-confidence reference matching.

## Evidence Required

- MCP `dcf.currency`, `dcf.stockCurrency`, risk-free-rate source, ERP source, initial WACC, and terminal WACC.
- Country of incorporation or operating exposure when cited by filings.
- Service-returned warnings and reference-data status.
- Cited external evidence only when country/currency exposure is material to the driver.

## Allowed action

- Explain returned risk-free rate, ERP source, initial cost of capital, terminal cost of capital, and currency consistency.
- Use risk as a narrative challenge in the market-implied/priced-in discussion.
- Flag low-confidence country exposure or currency conversion problems.
- If a user explicitly requests a supported scenario, WACC may be passed through `stockvaluation.recalculate`; that is not an autonomous researched adjustment.

## Do not

- Do not autonomously change WACC.
- Do not invent beta, lambda, country-risk premium, cost of debt, or capital structure.
- Do not manually convert currencies when the service reports a conversion failure.
- Do not calculate missing valuation values outside MCP/service output.

## Report Guidance

Risk should answer: what discount-rate path did the service return, what risks make the cash flows more fragile, and whether the market-implied expectations require too-easy risk assumptions.

## QA Expectation

Reports must keep risk explanation separate from model changes. Currency conversion failure must stop or use `stockvaluation.explain_failure`.
