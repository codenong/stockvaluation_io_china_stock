# Damodaran Coverage Map

Use this map after baseline MCP valuation and evidence collection, before `assumption_judgment`. Each topic is classified by current product support. The support state controls whether the user agent may adjust the model, explain the issue, or stop.

Support states:

- `supported_adjustment`: the MCP/service contract currently accepts the adjustment and the skill permits it under evidence rules.
- `supported_explanation`: the service returns data the agent may explain, but not newly adjust.
- `explain_only`: the agent may teach, flag, or cite the topic, but must not change model math.
- `future_support`: useful topic that requires new MCP/service work before governed adjustment.
- `unsupported_stop`: company type or data state where the agent must stop instead of producing a synthetic DCF.
- `out_of_scope`: valid finance topic outside the current public-ticker educational product.

## Model choice

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm
- Current product support state: `supported_explanation` for FCFF on supported public non-financial operating companies; `unsupported_stop` for financial firms until a governed excess-return, DDM, or FCFE path exists.
- User-agent allowed action: Explain why the local service selected FCFF, cite model-fit concerns, and stop for banks, insurers, brokers, and asset managers.
- Evidence required: Company type, sector, revenue model, debt meaning, and whether operating cash flows and reinvestment can be interpreted in an FCFF model.
- Report guidance: State that Java owns the deterministic FCFF math and that other valuation models are educational context unless future MCP support exists.
- QA expectation: Reports must not imply the agent can switch valuation models autonomously.

## Business lifecycle

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm
- Current product support state: `supported_explanation` for template/growth-pattern interpretation; `future_support` for governed lifecycle model switching beyond current service behavior.
- User-agent allowed action: Classify lifecycle qualitatively as young, high-growth, transition, mature, declining, cyclical, or distressed, then explain how it affects growth duration, margins, reinvestment, risk, and terminal value.
- Evidence required: Recent financial history, profitability, revenue growth, cyclicality, management disclosures, and service-returned template metadata.
- Report guidance: Mature or regular growth companies can be discussed normally; young, negative-earnings, declining, cyclical, or distressed companies need explicit caution and no invented normalization.
- QA expectation: Lifecycle labels must not create unsupported WACC, terminal growth, tax, distress, or model-choice changes.

## Revenue growth

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html
- Current product support state: `supported_adjustment` through governed `revenue_growth` and sector-level revenue growth overrides.
- User-agent allowed action: Propose a bounded autonomous growth change only with strong, dated, cited evidence and a clear link to the growth anchor and segment/business drivers.
- Evidence required: Filings, earnings releases, guidance, market-size evidence, segment growth, pricing/demand evidence, and growth-anchor context.
- Report guidance: Explain what growth must be true, what evidence supports it, and how growth interacts with reinvestment and terminal maturity.
- QA expectation: Weak, mixed, stale, or uncited growth evidence produces no autonomous change.

## Margins

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html
- Current product support state: `supported_adjustment` through governed `operating_margin` and sector-level operating margin overrides.
- User-agent allowed action: Propose a bounded margin change only when evidence supports operating leverage, pricing power, mix shift, cost discipline, cyclicality normalization, or segment margin mix.
- Evidence required: Current margins, target margins, segment margins, operating expense commentary, cyclicality, and cited management or filing data.
- Report guidance: Explain what margin expansion or compression would have to be true and whether the modeled target is sector-consistent.
- QA expectation: Do not present unexplained margin expansion as researched judgment.

## Reinvestment

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html
- Current product support state: `supported_adjustment` through governed `sales_to_capital` and sector-level sales-to-capital overrides.
- User-agent allowed action: Use sales-to-capital as the current governed proxy for reinvestment needs and capital efficiency.
- Evidence required: Asset intensity, store/capacity buildout, working capital, infrastructure needs, software/asset-light economics, and segment mix.
- Report guidance: Tie high growth to reinvestment. Explain that lower sales-to-capital means more reinvestment, and higher sales-to-capital means more capital efficiency.
- QA expectation: No growth story should ignore the capital required to support it.

## Terminal value

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm
- Current product support state: `supported_explanation` for returned terminal growth, terminal cost of capital, terminal ROIC/reinvestment, and terminal cash-flow composition; `explain_only` for autonomous terminal growth changes.
- User-agent allowed action: Explain mature-state logic, terminal value share, and sensitivity when service fields are returned.
- Evidence required: Service-returned terminal growth, terminal WACC, terminal ROIC/reinvestment, PV terminal value, explicit-period PV, and growth-to-risk consistency.
- Report guidance: State when terminal value dominates, compare terminal growth to mature-economy/risk-free-rate logic, and do not create a break-even table unless returned by the service.
- QA expectation: Do not autonomously change terminal growth; do not invent terminal composition values.

## Risk and discount rates

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html
- Current product support state: `supported_explanation` for returned risk-free rate, ERP source, initial/terminal cost of capital, and currency notes; `explain_only` for autonomous WACC changes.
- User-agent allowed action: Explain WACC, currency consistency, country risk, business risk, cyclicality, and data-quality uncertainty.
- Evidence required: Currency of cash flows, stock currency, country exposure when available, risk-free-rate source, ERP source, leverage/cyclicality context, and service warnings.
- Report guidance: Use risk to test the story; do not lower WACC to make the valuation work.
- QA expectation: Do not autonomously change WACC, country risk, beta, cost of debt, or capital structure.

## Accounting cleanup

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm
- Current product support state: `explain_only` for autonomous changes; `supported_explanation` when the service returns R&D, lease, option, NOL, tax, or other adjustment outputs.
- User-agent allowed action: Flag material accounting issues and explain service-returned adjustments.
- Evidence required: R&D expense materiality, lease commitments, stock-based compensation, one-time charges, restructuring, goodwill, and service-returned adjustment fields.
- Report guidance: Separate accounting concepts from model changes. Say when the service did not return a value.
- QA expectation: Do not autonomously toggle R&D capitalization, leases, options, NOLs, or one-time normalization.

## Taxes and NOLs

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html
- Current product support state: `supported_explanation` for returned tax-rate and NOL arrays; `explain_only` for autonomous tax/NOL changes unless the user explicitly requests a supported scenario.
- User-agent allowed action: Explain effective versus marginal tax concepts and service-returned tax behavior.
- Evidence required: Returned tax assumptions, NOL output if present, statutory/marginal tax evidence when cited, and service notes.
- Report guidance: Do not invent NOL schedules or tax shields. State unavailable when not returned.
- QA expectation: Autonomous researched judgment must not change tax rate or NOLs.

## Options and other claims

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm
- Current product support state: `supported_explanation` when service returns option/warrant, minority interest, debt, cash, or non-operating asset fields; `explain_only` for new claims.
- User-agent allowed action: Explain returned claims that bridge operating asset value to common equity value.
- Evidence required: Service-returned company DTO fields, option value outputs, debt/cash/minority interest fields, and cited disclosure only for discussion.
- Report guidance: Keep operating performance separate from claims on equity value.
- QA expectation: Do not invent option values, pension deficits, minority interests, or debt-like claims.

## Segment valuation

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html
- Current product support state: `supported_adjustment` for governed sector-level growth, margin, and sales-to-capital overrides when disclosed segment evidence is strong; `supported_explanation` for qualitative segment discussion.
- User-agent allowed action: Discover official segments, preserve disclosed revenue/margin data, and use segment evidence only when it is cited and mapped cleanly.
- Evidence required: Latest annual report, 10-K, 20-F, 10-Q, earnings release, investor presentation, segment revenue shares, segment margins, and source dates.
- Report guidance: Distinguish product, geography, and reportable segments. Mark undisclosed values as unavailable.
- QA expectation: Do not invent segment shares, margins, growth rates, or sector weights.

## Special companies

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm
- Current product support state: `unsupported_stop` for financial firms and unsupported company types; `supported_explanation` or `explain_only` for cyclical, commodity, young, troubled, or declining firms when the service can produce a baseline but confidence is limited.
- User-agent allowed action: Stop for financial firms; explain fragility for companies where FCFF inputs are hard to interpret.
- Evidence required: Company sector, business model, profitability, data sufficiency, commodity/cyclical exposure, and service failure categories.
- Report guidance: Do not force a synthetic valuation when the service fails or the company type is unsupported.
- QA expectation: Negative cases must fail closed with `stockvaluation.explain_failure`.

## Relative valuation

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html
- Current product support state: `out_of_scope` for a multiples engine; `explain_only` as educational context.
- User-agent allowed action: Mention multiples only as context if the user asks, and keep them separate from the MCP DCF output.
- Evidence required: Comparable set, fundamentals, growth, margins, risk, and reinvestment drivers if discussed.
- Report guidance: Do not use multiples to overwrite intrinsic value.
- QA expectation: Reports must not present relative valuation as a service-returned model unless future MCP support exists.

## Acquisitions and value enhancement

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm
- Current product support state: `out_of_scope` for acquisitions, synergy, control value, LBO, and value-enhancement engines.
- User-agent allowed action: Explain that these are outside the current local public-ticker DCF workflow.
- Evidence required: Not applicable unless a future scenario tool exists.
- Report guidance: Do not add synergy, control premiums, restructuring gains, or LBO assumptions to the model.
- QA expectation: Acquisition and synergy language must not alter valuation output.

## Real options

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm
- Current product support state: `out_of_scope` for real-option valuation engines; `explain_only` for educational context.
- User-agent allowed action: Flag patents, natural resources, expansion options, or abandonment options only as qualitative context.
- Evidence required: Specific option-like asset, exclusivity, uncertainty, exercise cost, and future MCP support before any model value.
- Report guidance: Do not add option value unless the service returns it as an options/warrants adjustment.
- QA expectation: No real-option value should be invented.

## Story-to-numbers discipline

- Damodaran source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm
- Current product support state: `supported_explanation` for narrative discipline across returned assumptions and `supported_adjustment` only for governed growth, margin, sales-to-capital, and sector versions.
- User-agent allowed action: Map every narrative claim to growth, margins, reinvestment, risk, or terminal assumptions, then classify the action state before it affects the model.
- Evidence required: Cited, dated evidence tied to a specific valuation driver and service-returned values that can be reported without invention.
- Report guidance: Combine story and numbers while separating market price, model value, evidence, assumptions, limitations, and unsupported topics.
- QA expectation: Unsupported topics must remain explain-only or stop conditions, not silent model changes.
