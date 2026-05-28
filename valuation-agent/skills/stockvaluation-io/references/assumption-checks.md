# Assumption Checks

Use these checks after reading MCP JSON.

Before any report insight affects the model, classify it with `{baseDir}/references/damodaran-coverage-map.md`:

- Supported autonomous changes: revenue growth, operating margin, sales-to-capital, and sector-level versions of those same levers.
- Supported explanations: service-returned model, terminal, risk, accounting, priced-in, and composition fields.
- Explain-only or future-support topics: WACC, terminal growth, tax, R&D capitalization, leases, options, NOLs, one-time normalization, relative valuation, acquisitions, and real options unless explicit governed support exists.
- Unsupported-stop topics: financial firms, unsupported companies, missing local service, insufficient financial data, and failed currency conversion.

## Growth

- Compare requested and effective growth assumptions.
- Compare growth to the growth-anchor percentile band.
- Challenge growth above the anchor's upper band unless the user supplied a clear reason.
- If confidence is weak, say the anchor is directional.

## Margins

- Compare target margins to current margins.
- Explain whether expansion requires pricing power, scale, mix, cost reduction, or operating leverage.
- Flag abrupt margin expansion.

## Reinvestment

- Review sales-to-capital assumptions.
- Lower sales-to-capital means higher reinvestment needs.
- Do not let a high-growth scenario ignore reinvestment.

## Cost Of Capital

- Explain the risk-free rate, equity risk premium, and convergence when returned.
- Challenge low discount-rate assumptions if growth and business risk are also high.
- Do not autonomously change WACC in researched judgment.

## Terminal Growth

- Terminal growth should be mature and bounded.
- Flag terminal growth above long-run mature-economy logic.
- Do not autonomously change terminal growth in researched judgment.

## Market-Implied And Priced-In Expectations

- Use `marketImpliedExpectations` and `pricedInExpectations` as report inputs when returned.
- Explain that single-variable implied metrics hold other assumptions fixed.
- Show priced-in frontier, scenario, grid, or sensitivity tables only when the service returned the data.
- Do not invent break-even, sensitivity, terminal composition, or scenario values.

## Scenario Discipline

- Auto-recalculate once after `assumption_judgment` in the default full researched valuation workflow when the governed payload is supported.
- Ask before running extra user-requested scenarios beyond the default researched recalculation.
- Use only supported `stockvaluation.recalculate` override keys.
- Report requested, mapped, unsupported, and effective assumptions separately.
