# Growth And Reinvestment Discipline

Damodaran-style valuation ties growth to the capital needed to produce it. In StockValuation.io, revenue growth, operating margin, and sales-to-capital are the current governed autonomous levers.

## When It Matters

- Growth is materially above history, the growth anchor, management guidance, or sector context.
- The company is scaling stores, plants, distribution, inventory, cloud infrastructure, sales capacity, or working capital.
- The report's story relies on asset-light economics or improving capital efficiency.
- The priced-in frontier requires a growth and margin combination that looks demanding.

## Evidence Required

- Dated, cited primary evidence for demand, pricing, market size, guidance, backlog, segment growth, or customer expansion.
- Segment evidence when a specific business line drives the growth story.
- Evidence on capital intensity: capex, working capital, stores, plants, platform investment, or asset-light recurring revenue.
- MCP baseline assumptions and growth-anchor confidence.

## Allowed action

- Propose governed `revenue_cagr`, `operating_margin`, and `sales_to_capital` changes only when evidence is strong, dated, cited, and directly tied to the driver.
- Use sector-level overrides only when official segment evidence supports a clean mapping.
- Keep evidence, rationale, requested, mapped, unsupported, and effective assumptions separate.
- Use priced-in expectations as report inputs, not as automatic model changes.

## Do not

- Do not adjust WACC, terminal growth, tax rate, cash, debt, share count, option value, or direct valuation output as part of autonomous growth judgment.
- Do not assume high growth can be funded with no reinvestment.
- Do not invent segment shares or capital intensity.
- Do not calculate missing valuation values outside MCP/service output.

## Report Guidance

The growth section should answer:

- What revenue growth is modeled?
- What evidence supports or challenges it?
- What reinvestment does it require through sales-to-capital?
- What growth is implied by market price when `marketImpliedExpectations` or `pricedInExpectations` is returned?

## QA Expectation

If evidence is weak, the researched case should be a no-change case with a clear reason. A growth change without reinvestment discussion is incomplete.
