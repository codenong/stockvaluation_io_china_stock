# Driver-Specific Evidence Extraction

Use this reference after source discovery and before `assumption_judgment`. The goal is to turn researched material into evidence tied to specific valuation drivers, not to prove that a source exists.

## Required Drivers

Classify every evidence item into exactly one of these drivers:

- `revenue_growth`: segment growth, backlog, bookings, guidance, unit volume, pricing power, customer growth, TAM, geographic growth, and cyclicality.
- `operating_margin`: gross margin trend, operating leverage, mix shift, cost structure, restructuring, scale benefits, commodity or input costs, and competitive pressure.
- `reinvestment_sales_to_capital`: capex intensity, R&D intensity, working-capital needs, acquisition dependence, store or unit expansion, asset-light versus asset-heavy model, and capitalized R&D relevance.
- `risk_wacc`: leverage, interest burden, cyclicality, country exposure, customer concentration, regulatory risk, commodity exposure, and business-model volatility.
- `terminal_value_mature_state`: competitive advantage durability, market saturation, long-term industry growth, steady-state reinvestment needs, and margin-fade risk.
- `accounting_adjustments`: R&D intensity and useful life, lease obligations, operating leases, stock-based compensation or options, NOLs, one-time charges, restructuring, impairments, and other accounting cleanup topics.

## Required Evidence Item Fields

Each extracted evidence item must preserve these fields:

- `driver`: one required driver from the list above.
- `source_name`: filing, release, presentation, transcript, data table, or other source name.
- `source_url`: direct URL when available. Do not use a search-result URL as the source.
- `source_date`: release, filing, publication, presentation, or data date; use `unknown` only when no date is available.
- `evidence_summary`: short factual summary of the relevant fact. Do not invent facts, numbers, or quotes.
- `direction`: one of `supports higher assumption`, `supports lower assumption`, or `neutral/mixed`.
- `confidence`: one of `high`, `medium`, or `low`.
- `assumption_implication`: what the evidence means for the specific valuation assumption, including no-change implications.
- `allowed_to_affect_autonomous_recalculation`: boolean. `true` only when the driver is governed, the source is dated and cited, and the evidence is strong enough for a researched model change.
- `model_action`: one of `governed assumption change`, `report explanation only`, or `explain/flag only unsupported`.

## Evidence Roles

Classify the role before judging an assumption:

- `report explanation only`: Useful for explaining the report, but not strong enough for a model change.
- `governed assumption change`: Strong, dated, cited evidence for `revenue_growth`, `operating_margin`, `reinvestment_sales_to_capital`, or a sector-level version of those same levers.
- `explain/flag only unsupported`: Useful evidence for `risk_wacc`, `terminal_value_mature_state`, `accounting_adjustments`, or another unsupported model field. Explain it, flag the limitation, and do not send it to `stockvaluation.recalculate`.

## Allowed Action

- Use revenue growth evidence to explain or, when strong enough, govern `revenue_cagr` or sector-level revenue-growth changes.
- Use operating margin evidence to explain or, when strong enough, govern `operating_margin` or sector-level margin changes.
- Use reinvestment / sales-to-capital evidence to explain or, when strong enough, govern `sales_to_capital` or sector-level sales-to-capital changes.
- Use risk / WACC, terminal value / mature-state, and accounting-adjustment evidence in the report as explanations or flags unless current governed support explicitly allows a scenario.

## Do Not

- Do not calculate DCF values or direct valuation outputs from evidence.
- Do not count source discovery as evidence.
- Do not use unsupported evidence to change WACC, terminal growth, tax, R&D capitalization, leases, options, NOLs, one-time charges, cash, debt, share count, or direct valuation-output fields.

## Generic Source Presence Is Not Evidence

Do not count these as evidence:

- "10-K found."
- "Earnings release found."
- "Investor presentation available."
- "SEC filing source captured."
- "The company has a risk factors section."

A source becomes evidence only when the item names the valuation driver and the relevant fact. For example, "FY revenue increased 6% from pricing and volume in the North America segment" can support `revenue_growth`; "latest 10-K available" cannot.

## Autonomous Recalculation Boundary

Only these researched evidence items may affect autonomous recalculation:

- `revenue_growth` evidence that supports `revenue_cagr` or a sector-level revenue-growth override.
- `operating_margin` evidence that supports `operating_margin` or a sector-level operating-margin override.
- `reinvestment_sales_to_capital` evidence that supports `sales_to_capital` or a sector-level sales-to-capital override.

These drivers are explain/flag only in autonomous researched judgment unless future governed support is explicit and tested:

- `risk_wacc`: do not autonomously change WACC, beta, equity-risk premium, country-risk premium, debt spread, or risk-free rate.
- `terminal_value_mature_state`: do not autonomously change terminal growth, terminal WACC, terminal value, or projection length.
- `accounting_adjustments`: do not autonomously change R&D capitalization, lease conversion, stock-based compensation, options, NOLs, one-time charges, tax, cash, debt, share count, or direct valuation-output fields.

## Strength Threshold

Use a researched assumption change only when all of the following are true:

- The evidence is driver-specific, dated, and cited.
- The source is primary or otherwise reliable for the claim.
- The direction and assumption implication are clear.
- Conflicting evidence has been addressed.
- The affected assumption is governed by the current MCP/service contract.
- The change is modest and explainable relative to the baseline assumption, growth anchor, segment mix, and data-quality warnings.

If evidence is weak, missing, stale, generic, uncited, or mixed, leave the assumption baseline/conservative and explain the no-change reason.

## Accounting Adjustment Discipline

Accounting evidence can improve interpretation, but it is explain/flag only unless the current MCP/service output explicitly returns a supported adjustment or a future governed input is documented and tested. R&D intensity, operating lease obligations, stock-based compensation, options, NOLs, restructuring, impairments, and one-time charges should not alter autonomous intrinsic value in the researched workflow.
