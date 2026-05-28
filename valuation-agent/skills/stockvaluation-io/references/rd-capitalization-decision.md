# R&D Capitalization Decision

R&D capitalization matters because research spending may be closer to investment than a one-year operating expense. It can affect operating income, invested capital, reinvestment, and return on capital. In the current agent-native product, it is explain/flag only unless future governed MCP/service support is added and tested.

## When It Matters

- The company has material R&D relative to revenue, operating income, or reinvestment.
- The business is software, semiconductors, pharmaceuticals, biotechnology, medtech, internet platforms, or another research-heavy model.
- Reported operating margins look low because research investment is expensed immediately.
- Growth appears high but reported reinvestment looks understated.

## Evidence Required

- Latest annual report, 10-K, 20-F, 10-Q, or earnings release with R&D expense.
- Multi-year R&D history if the user asks for an explicit scenario.
- Service-returned R&D capitalization or research asset fields if available.
- A clear note on whether the current MCP payload exposes governed adjustment support.

## Allowed action

- Explain/flag only in autonomous researched valuation.
- Explain why capitalizing R&D can raise operating income, create a research asset, increase invested capital, and change ROIC.
- If the service returns an R&D adjustment, report that returned value and describe its effect.
- Preserve R&D evidence in the report or `assumption_judgment.evidence_used` only as evidence; it is not a governed autonomous recalculate field today.
- If future MCP support exists, require explicit fields, source dates, amortization period, and tests before changing the support state.

## Do not

- Do not send R&D capitalization, amortization period, research asset, or adjusted operating income through `stockvaluation.recalculate` unless a future governed field is documented.
- Do not toggle `isExpensesCapitalize` autonomously.
- Do not infer an R&D asset from a single expense line.
- Do not present explain-only R&D commentary as part of the model value.
- Do not calculate missing valuation values outside MCP/service output.

## Report Guidance

Use language like:

- "R&D capitalization is relevant to interpreting reported margins, but the current MCP contract does not allow autonomous R&D adjustment."
- "The service did not return an R&D capitalization value, so this report flags the issue qualitatively."
- "If a future governed R&D scenario is requested, it needs multi-year R&D history and explicit service support."

## QA Expectation

Reports for research-heavy companies should mention the limitation when relevant. They must not silently adjust margins, reinvestment, invested capital, ROIC, or intrinsic value for R&D.
