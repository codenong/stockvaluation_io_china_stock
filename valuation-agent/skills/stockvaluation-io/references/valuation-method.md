# Valuation Method And Coverage Boundary

Damodaran-style interpretation of local DCF JSON. Never do the valuation math yourself; every value comes from MCP/service output.

## Core Logic

Value operating assets from expected FCFF; reinvestment ties growth to capital through sales-to-capital and return on capital; cost of capital converges to a mature level; terminal growth stays bounded by mature-economy logic; equity value is operating value plus cash and non-operating assets less debt-like claims, minority interests, and option value. Compare intrinsic value to market price as a model gap, not an instruction.

## Coverage Boundary

| Class | Topics | Action |
| --- | --- | --- |
| Supported autonomous changes | revenue growth, target operating margin, sales-to-capital, sector-level versions, source-backed R&D capitalization | governed `recalculate` with strong evidence or AccountingAndClaims validation |
| Supported explanations | model selection, terminal fields, risk/discount fields, accounting statuses, market-implied/priced-in data, composition fields | explain returned values only |
| Explain-only / future support | WACC, terminal growth, tax, leases, options, NOLs, one-time normalization, relative valuation, acquisitions, real options | flag; user scenarios only where the contract already supports the field |
| Unsupported stop | financial firms, unsupported companies, missing service, insufficient data, failed currency conversion | stop cleanly, `explain_failure`, no synthetic valuation |

## Method Checks

- **Growth**: compare assumptions to the growth-anchor percentile band; challenge growth above the upper band without clear evidence; weak anchor confidence is directional only. High growth cannot ignore reinvestment.
- **Margins**: compare target to current margins; explain what expansion requires (pricing power, scale, mix, leverage); flag abrupt expansion.
- **Reinvestment**: lower sales-to-capital means higher reinvestment need; a growth change without reinvestment discussion is incomplete.
- **Cost of capital**: explain returned risk-free rate, ERP, and convergence; challenge low discount rates paired with high growth and risk; never change WACC autonomously.
- **Terminal value**: state whether terminal value dominates the PV and how fragile that is; flag terminal growth near or above mature-economy/risk-free logic; never change terminal growth autonomously; invalid user terminal-growth values are rejected, not capped.
- **Market-implied / priced-in**: use returned `marketImpliedExpectations` and `pricedInExpectations` as report inputs and the report's central tension (what growth/margin/reinvestment/risk the price requires, and whether that is believable). They are report-only — not evidence and not autonomous model changes. Single-variable implied metrics hold other inputs fixed. Never invent break-even, frontier, sensitivity, or composition values the service did not return.

## Lifecycle Framing

Young/high-growth: market size, path to margins, reinvestment. Transition: margin convergence and capital efficiency. Mature: durable margins, terminal growth, capital discipline. Cyclical/commodity: mid-cycle caution. Distressed: survival risk; stop when service support is insufficient. Note when the service selects a longer template or forces a growth-pattern change. Do not switch models autonomously or normalize negative earnings by inventing margins.

## Stop Rules

- Financial firms (banks, insurers, brokers, asset managers, lenders, exchanges): stop until a governed excess-return/DDM/FCFE workflow exists. No synthetic FCFF report.
- Private firms, unavailable tickers, funds, trusts, non-operating vehicles: out of scope for the public-ticker product.
- Insufficient data, missing price or statements, currency-conversion failure: stop; never fill gaps or convert currency manually.
- Failure reports state the category, plain-language message, recovery path, and that no valuation was invented. Negative cases fail closed.

## Data Limits

Yahoo-normalized data can be missing, stale, restated, or inconsistent; reference-data mapping is an anchor, not proof of industry-median behavior; say so in the report when confidence is weak.
