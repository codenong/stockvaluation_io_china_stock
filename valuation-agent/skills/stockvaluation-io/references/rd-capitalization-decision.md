# R&D Capitalization Decision

R&D capitalization matters because research spending may be closer to investment than a one-year operating expense. It can affect operating income, invested capital, reinvestment, and return on capital. In the current agent-native product, it is explain/flag only in autonomous researched mode. A governed accounting scenario may capitalize R&D only through the tested AccountingAndClaims path.

## When It Matters

- The company has material R&D relative to revenue, operating income, or reinvestment.
- The business is software, semiconductors, pharmaceuticals, biotechnology, medtech, internet platforms, or another research-heavy model.
- Reported operating margins look low because research investment is expensed immediately.
- Growth appears high but reported reinvestment looks understated.

## Evidence Required

- Latest annual report, 10-K, 20-F, 10-Q, or earnings release with R&D expense.
- Multi-year R&D history if the user asks for an explicit scenario.
- Source provenance with source class, provider, source date, and retrieved status.
- An amortization policy with method and amortization period.
- Service-returned R&D capitalization status from `AccountingAndClaims` when available.

## Allowed action

- Explain/flag only in autonomous researched valuation.
- Explain why capitalizing R&D can raise operating income, create a research asset, increase invested capital, and change ROIC.
- If the service returns an R&D adjustment, report that returned value and describe its effect.
- Use the governed accounting scenario only when `request_policy.mode = "explicit_scenario"` and the AccountingAndClaims validator accepts multi-year R&D history, amortization policy, and source provenance.
- The service boundary must also receive the amortization method and amortization period; otherwise the R&D scenario is rejected even if the agent-side validator was bypassed.
- Preserve R&D evidence in the report or `assumption_judgment.evidence_used` only as evidence; it is not a governed autonomous recalculate field.

## Do not

- Do not send R&D capitalization, amortization period, research asset, or adjusted operating income through `stockvaluation.recalculate` outside the governed AccountingAndClaims explicit scenario.
- Do not toggle `isExpensesCapitalize` autonomously.
- Do not infer an R&D asset from a single expense line.
- Do not present explain-only R&D commentary as part of the model value.
- Do not calculate missing valuation values outside MCP/service output.

## Report Guidance

Use language like:

- "R&D capitalization is relevant to interpreting reported margins, but autonomous researched mode does not allow R&D adjustment."
- "The service returned `source_required`, so this report flags the issue qualitatively."
- "A governed R&D scenario needs multi-year R&D history, amortization policy, source provenance, and audit recording."

## QA Expectation

Reports for research-heavy companies should mention the limitation when relevant. They must not silently adjust margins, reinvestment, invested capital, ROIC, or intrinsic value for R&D.
