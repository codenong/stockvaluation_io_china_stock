# Investor-Friendly Valuation Report Template

This file is the canonical controlling structure for the final investor-facing educational valuation report. Use this structure after the full researched valuation workflow completes. Write the report from MCP JSON, the Scenario Book, the valuation audit packet, evidence packet, evidence review gate status, segment discovery, `assumption_judgment`, baseline plausibility, guided-refinement `user_judgment` when present, recalculation output, and effective assumptions.

`narrative-report-style.md` is subordinate to this template. narrative-report-style.md is subordinate to the report template. It may improve prose, but it must not remove, rename, or reorder required template sections. Do not use the older loose story-and-numbers shape as the controlling report structure.

For prospectus mode, use this same template after `stockvaluation.extract_prospectus` has stopped at `prospectus_extraction_review_required`, the user has reviewed or corrected the `ProspectusFinancialPacket`, and `stockvaluation.value_prospectus` has returned a result. Label `priceBasis = offering_price`, source class `primary_filing`, and provider `sec-edgar-prospectus` in plain prose. Prospectus mode remains educational use only and not financial advice, but the report should state that boundary once near the start rather than repeating it throughout.

## Final Report Rendering Contract

The final answer must render the required report-template headings in order. Do not replace this template with a compressed memo, even when the user asks for a concise answer. A final answer that starts with a sentence such as "Using stockvaluation.io, the user-refined case values COMPANY at PRICE" and then gives only "Key assumptions", "Main caveats", and "Sources used" is not template-compliant.

The default report is for an investor-reader, not an agent debugger. Use plain section names and plain prose. Do not use visible default headings named `Educational-Use Framing`, `Valuation Audit Packet Summary`, `Scenario Book Summary`, or `Internal Baseline Audit`. Do not print internal terms such as `MCP`, `structuredContent`, `sourceQualityGate`, `mechanical_only`, `mechanical baseline`, `mechanical model value`, `valuation_audit_packet`, or `scenario_book.v1` in the default report body unless the user explicitly asks for audit/debug detail.

Use one concise no-advice line near the start. Do not repeat "educational use only" or "not financial advice" before every table or section.

Do not show the internal mechanical model value in the default report. If no evidence-constrained base, user-refined deterministic scenario, or explicit supported scenario exists, state that no reliable user-facing valuation case was produced and explain the blockers in plain English. Show the internal mechanical value only in the explicit audit/debug appendix when the user asks for it.

Every final report must visibly include evidence review status and guided-refinement status. If a status is unavailable, say unavailable in the relevant template section rather than omitting the section.

Diagnostic scenarios stay diagnostic. Do not blend the main scenario with a diagnostic no-segment run, market-implied diagnostic, sensitivity run, or unsupported scenario into a headline valuation range. If a diagnostic run is useful, put it under `What The Price Would Need`, `Sensitivity Analysis`, or an explicit audit/debug appendix, and label why it is not the main scenario.

Use these section names as the visible spine of the final report unless the user explicitly asks for audit/debug appendices to be added:

1. How To Read This
2. Valuation View
3. What Was Reviewed
4. Source Confidence
5. Business Story
6. Growth
7. Profitability
8. Reinvestment Needs
9. Risk
10. What The Price Would Need
11. Key Assumptions
12. Data Limits
13. Bottom Line
14. Sources
15. Guided Judgment
16. Evidence And Segment Detail
17. Assumption Support

Do not print raw `assumption_judgment` JSON by default. Summarize it in prose and tables. Do not invent missing values. If MCP/service output does not return a value, say unavailable or omit the table.

Do not print raw `valuation_audit_packet` JSON by default. Summarize the packet status, packet reference, final case type, rejected evidence, unsupported fields, guided-refinement status, and data-quality limitations only in audit/debug detail. Keep mechanical baseline value/detail out of user-facing output unless the user explicitly asks for audit/debug detail.

Do not print raw `scenario_book.v1` JSON by default. Summarize the Scenario Book status, reference, main scenario, scenario types, evidence review status, guided-refinement status, diagnostics, unsupported inputs, and limitations only in audit/debug detail.

No raw hidden JSON by default: keep hidden guided question plans, audit packets, Scenario Book internals, and assumption-judgment objects summarized unless the user explicitly asks for audit/debug detail.

The user-refined scenario is the main scenario when guided refinement was completed. Mechanical baseline is internal-only and remains internal-only by default. Mechanical baseline is internal scaffolding by default: do not include mechanical baseline value as a primary valuation case in the main report. Keep mechanical baseline detail available only in the explicit audit/debug section.

## How To Read This

Use one concise line: this report is for educational use only and is not financial advice. Then move on. Explain that the report compares business facts, assumptions, and model output; it is not an instruction to buy, sell, hold, or participate in an offering.

## Internal Valuation Metadata (Debug Only)

This section is audit/debug-only. Do not include it in the default report.

Use `structuredContent.auditPacket.summary` when returned. State the final case type before presenting any valuation result:

- `evidence_constrained_no_change`: evidence was valid or reviewable, but no governed model change was accepted.
- `evidence_constrained_governed_recalculation`: governed evidence supported a supported recalculation.
- `user_refined_scenario`: bounded user judgment created the main scenario; user answers are not external evidence.
- `insufficient_researched_evidence`: the run did not earn a user-facing valuation case.

Include the packet reference and a compact status summary only in audit/debug detail. Do not present `mechanical_baseline` as a final case type, visible scenario, or report case. If the audit packet says `insufficient_researched_evidence`, stop or explain the insufficiency without showing the mechanical baseline value.

## Scenario Metadata (Debug Only)

This section is audit/debug-only. Do not include it in the default report.

Use `structuredContent.scenarioBook.summary` and `structuredContent.scenarioBook.book` when returned. State the main scenario before presenting valuation values.

Valid user-facing scenario types:

- `evidence_constrained_base`: researched case after evidence review, plausibility gate, and governed recalculation when supported.
- `user_refined_scenario`: bounded user judgment after guided refinement completed or the user accepted defaults.
- `explicit_scenario`: user-requested supported scenario outside the default guided flow.

Diagnostics:

- `market_implied_diagnostic`
- `priced_in_diagnostic`
- `sensitivity_diagnostic`

Market-implied diagnostics are diagnostic-only. They are not evidence, autonomous changes, or the main scenario.

If guided refinement was bypassed by a quick/no-questions request, state the guided-refinement bypass and do not invent a user-refined scenario. If guided defaults were accepted in a workflow with deterministic recalculation support, state that defaults are user judgment, not external evidence, and that the workflow created exactly one user-refined scenario. If there is no deterministic recalculation path, describe defaults as report-only guided judgment.

Each scenario table must keep requested, mapped, unsupported, metadata, and effective assumptions separate. Include payload reference, audit packet reference, evidence/provenance references, segment economics status, and AccountingAndClaims status when material.

Do not present direct valuation outputs, fair value, target price, upside/downside, market price fitting, cash, debt, share count, or report-only accounting topics as mapped scenario inputs unless a tested governed contract accepted them.

## Valuation View

Lead with the scenario the user actually selected. Include compact values only when returned by MCP/service output.

| Field | Value |
| --- | --- |
| Company |  |
| Ticker |  |
| Valuation status | reliable user-facing case produced, challenged, or unavailable |
| Case shown | user-refined scenario, evidence-supported base case, explicit scenario, or unavailable |
| Intrinsic value per share | only when a user-facing case exists |
| Market price |  |
| Offering price | prospectus mode only |
| Equity value |  |
| Gap to market | currency amount and percent |
| Currency and source date |  |
| Prospectus review status | reviewed, review_required, corrected, stopped, or not_applicable |
| Prospectus price basis | `offering_price` when returned by `stockvaluation.value_prospectus` |
| Main limitation | plain-English blocker or data limit |

Separate market price, model intrinsic value, assumptions, and evidence. Describe the gap as a model result, not as a recommendation. The mechanical baseline value and mechanical model value are omitted from the default snapshot unless the user asks for audit/debug detail.

For prospectus mode, call the comparable price input the offering price, not a trading market price. The offering price is the prospectus price basis, not a live quote. Use `stockvaluation.value_prospectus` output and the reviewed packet; do not substitute Yahoo Finance, yfinance, market-data revenue estimates, or a live market price.

For prospectus mode, read `valuationBasisStatus`, `valuationCaseStatus`, `proceedsBasis`, and `valuationBasisWarnings` before presenting any value. Use these plain labels:

- `clean_pro_forma_basis` and `clean_valuation_case`: post-offering shares and cash/proceeds are on a clean basis.
- `pro_forma_cash_missing`: post-offering shares require pro-forma cash, but net proceeds or pro-forma cash were not resolved.
- `gross_proceeds_estimate_only`: only gross proceeds could be inferred; that is a challenged basis, not clean net cash.
- `challenged_valuation_case`: no clean user-facing valuation was produced.

If the case is challenged, or if `dcf.valueVisibility = diagnostic_only`, do not show the internal diagnostic value by default. Put the blocker in `Valuation View`, `Data Limits`, and `Bottom Line` in plain English.

A clean cash/share basis is not enough to headline a value. If `valuationBasisStatus = clean_pro_forma_basis` but `valuationCaseStatus = challenged_valuation_case` or `baseline.baselineUseStatus = challenged_baseline`, the report must say the cash/share basis was fixed but no clean user-facing valuation case was produced. Do not use labels such as `Evidence-reviewed prospectus base`, `Intrinsic value per share`, or `StockValuation.io estimated` for the diagnostic value unless the user explicitly asks for audit/debug detail.

## What Was Reviewed

State whether the user reviewed the evidence, corrected it, added sources, continued with caveats, bypassed review by explicit quick/no-questions/automation/smoke-test request, or the workflow stopped earlier. Use plain words. User corrections are not external evidence unless source-backed and processed through evidence rules.

| Field | Status |
| --- | --- |
| Evidence review status | approved, corrected, caveated, bypassed, not run, or unavailable |
| Review timing | after evidence gathering and before guided valuation refinement |
| User action | approve, corrections, additional sources, continue with caveats, or explicit bypass |
| Source-backed corrections processed | yes/no/unavailable |
| Remaining caveats |  |

If the review was bypassed for a quick/no-questions/automation/smoke-test path, label the bypass plainly and do not imply the user approved the evidence base.

## Source Confidence

Use `structuredContent.provenance`, `structuredContent.sourceQualityGate`, and `valuation.assumptionTransparency.sourceProvenance` when returned. Keep this section compact and visible in the default report, but translate internal statuses into plain English. The default full researched baseline should come from `stockvaluation.researched_baseline`; `stockvaluation.value_ticker` remains mechanical. Use `financial-field-definitions.md` for field meanings and reconciliation language.

| Field | Value |
| --- | --- |
| Core financial source | SEC filing, company report, Yahoo-normalized data, company IR, or agent research |
| Provider or document |  |
| Source date / period end |  |
| How the source was used | primary source, fallback, cross-check, or report-only context |
| Cross-check | completed, pending, unavailable, not needed, or not applicable |
| Prospectus price basis | offering price when returned |
| Material warnings |  |

Translate raw service statuses into these plain labels. Keep raw status codes in audit/debug detail unless the user asks for them.

For US researched valuations, prefer SEC/EDGAR companyfacts, XBRL, company facts, or filing-derived primary financial data when returned. If the provider is `sec-edgar-companyfacts`, say live SEC/EDGAR primary filing data was used for the returned core financials, with the returned source date and period end. If the output shows `sec_http_error_yahoo_fallback` or another `sec_*_yahoo_fallback` status, say the run used Yahoo-normalized financials as a classified fallback and do not imply the core financials are primary-source backed. If `sourceQualityGate.status` is `requires_user_decision`, say whether the user approved fallback, requested retry, stopped, or explicitly bypassed the gate, but do not use a visible `Source quality gate` row or heading.

SEC primary-filing provenance does not mean full GAAP/non-GAAP reconciliation, segment-footnote extraction, lease parsing, or accounting cleanup was completed. Treat those topics according to returned AccountingAndClaims statuses and evidence rules.

For prospectus mode, `primary_filing` / `sec-edgar-prospectus` means the reviewed packet came from the SEC prospectus HTML filing. It does not mean the model has audited every pro forma adjustment or accounting claim. If `sourceQualityGate.reason = prospectus_extraction_review_required`, report whether the packet was approved, corrected, supplemented with sources, or stopped before `stockvaluation.value_prospectus`.

Prospectus packet approval is only extraction review. It is not the evidence review gate and does not replace guided valuation refinement. For prospectus reports, still show evidence review status and guided-refinement status. If the workflow stopped at the prospectus packet review, say guided refinement was not run because valuation had not reached that stage. If the user explicitly requested quick/no-questions/automation/smoke-test, label that bypass.

If there is no prospectus-specific recalculation path, label accepted guided defaults as report-only guided defaults. Do not call report-only prospectus guided answers a user-refined scenario, do not call them recalculated, and do not make them the headline value. Use a user-refined scenario label only when a deterministic prospectus recalc actually happened. If the user accepted defaults after a visible multi-question count, all remaining default answers must be summarized before the report; do not skip hidden questions silently.

SEC filing facts are primary. External news is report-only context and may confirm background, but external news must not override filing facts from the prospectus.

For non-US researched valuations, Yahoo-normalized financials may be the main normalized source when the report labels the source class and gives the company-report or filing cross-check status. If `primary_adapter_not_supported_yahoo_normalized` is returned, say no supported deterministic primary-filing adapter covered this listing and company-report cross-check is required. If cross-checks are pending, say so plainly and treat material accounting or segment claims as limitations until checked.

If Yahoo-normalized data and filing/company-report data differ materially, include the returned data-quality warning and treat it as a limitation, not as an automatic assumption override. For field-specific interpretation, use `financial-field-definitions.md`; do not invent definitions for revenue, operating income, cash, debt, shares, R&D, SBC, tax, pretax income, minority interest, or book equity.

If a returned data-quality warning has `period_mixed_quarterly_balance_yearly_shares`, say the model mixed quarterly cash/debt/equity with a yearly share count because quarterly shares were missing. Treat it as a data limitation, not as a user-refined assumption.

## Business Story

Write a short prose setup before the driver sections. If `marketImpliedExpectations` or `pricedInExpectations` are returned, use them as the central tension:

- What growth is the market price implying?
- What operating margin is the market price implying?
- What sales-to-capital or reinvestment efficiency is required?
- What risk or cost-of-capital setting makes the current price easier or harder to justify?
- Are those combinations believable given the evidence?

Use market-implied/priced-in data as report inputs, not autonomous model changes. Market-implied diagnostics are never evidence for the evidence-constrained base. Do not use market-implied values as the researched base.

## Growth

Write prose, not only bullets. Explain revenue drivers, market expansion, scale advantages, pricing power, segment growth, growth-anchor context, and what growth would have to be true. Compare the main scenario growth to returned market-implied growth when available.

## Profitability

Write prose. Explain current and target operating margins, operating leverage, cost structure, pricing power, competitive positioning, and what margin expansion or compression would have to be true. Compare the main scenario margin to returned market-implied margin when available.

## Reinvestment Needs

Write prose. Explain sales-to-capital, reinvestment discipline, return on capital, asset intensity, capital efficiency, and whether the growth story can be funded. Tie high growth to reinvestment needs.

## Risk

Write prose. Explain operational, competitive, regulatory, macro, currency, cyclicality, cost-of-capital, and data-quality risks. WACC, terminal growth, and tax changes are explain-only in autonomous researched judgment unless the user explicitly requests a supported scenario.

## What The Price Would Need

Use `valuation.assumptionTransparency.marketImpliedExpectations` when returned.

| Lever | Model value | Implied value | Gap | Solved? | Note |
| --- | --- | --- | --- | --- | --- |
| Revenue growth |  |  |  |  |  |
| Operating margin |  |  |  |  |  |
| Sales-to-capital |  |  |  |  |  |

Explain that each single-variable implied metric holds other variables fixed. If `marketImpliedExpectations` is absent, say it is unavailable rather than recreating it.

## Key Assumptions

Summarize requested, mapped, unsupported, and effective assumptions separately. The assumptions the deterministic service actually used are the effective assumptions.

| Assumption | Evidence-constrained base | User requested | Sent to MCP | User-refined effective | Status |
| --- | --- | --- | --- | --- | --- |
| Revenue growth |  |  |  |  |  |
| Operating margin next year |  | unsupported or explicit scenario only |  |  | scenario-only user judgment |
| Target operating margin |  |  |  |  |  |
| Margin convergence year |  |  |  |  |  |
| Sales-to-capital years 1-5 |  |  |  |  |  |
| Sales-to-capital years 6-10 |  |  |  |  |  |
| Segment or sector-level drivers |  |  |  |  |  |

Do not call user answers evidence. Do not include unsupported answers in the MCP payload. Do not present market-implied diagnostics as a user-refined scenario unless the user explicitly selected bounded assumptions and the service recalculated them.

## Data Limits

Cover Yahoo Finance coverage, missing or stale data, unsupported-company warnings, growth-anchor confidence warnings, currency issues, and absent report fields. Do not hide unsupported fields.

If evidence is weak or missing, keep the relevant assumption baseline/conservative rather than forcing a researched change. Do not invent missing values.

## Bottom Line

Use a prose conclusion, not recommendation language. Cover:

- The central valuation tension.
- Strongest assumption support.
- Weakest assumption support.
- What would change the model.
- Which topics are supported adjustments, supported explanations, explain-only, future-support, unsupported-stop, or out-of-scope.

## Sources

List direct sources with dates. For prospectus mode, put the SEC filing first. External news may be included only as report-only context and must not override filing facts.

## Break-Even / Priced-In Frontier

Use `valuation.assumptionTransparency.pricedInExpectations.frontier` when returned. Label this as a break-even or priced-in table only when the service returned combinations that support the market price.

| Operating margin | Implied revenue growth | Intrinsic value | Gap to market | Solved? | Note |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

Do not hand-create a break-even table if `pricedInExpectations.frontier` is absent.

## Scenario Headline Table

Use `valuation.assumptionTransparency.pricedInExpectations.scenarios` when returned.

| Scenario | Risk setting | Capital-efficiency setting | WACC | Sales-to-capital | Headline |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

Keep scenarios educational. Do not turn scenarios into recommendation cases.

## Sensitivity Analysis

Use only service-returned sensitivity, `pricedInExpectations.grid`, market-implied metrics, or explicitly recalculated MCP scenarios. Include a two-variable table or compact heat-map-style table when returned. If sensitivity data is absent, explain the most sensitive assumptions qualitatively instead of inventing values.

## Guided Judgment

Use this section when guided refinement was run. If the user requested a quick/no-questions path, say guided refinement was bypassed by request.

State plainly: user answers define a scenario; they are not independent evidence.

| Question | Driver | Baseline assumption | Evidence summary | User answer | Model action |
| --- | --- | --- | --- | --- | --- |
|  | revenue growth, margin path, target margin, convergence year, sales-to-capital, sector driver, or report-only topic |  |  |  | user scenario override, report-only user judgment, or unsupported |

Do not include unsupported answers in the MCP payload. Keep report-only answers in prose and metadata.

If guided refinement was bypassed, do not fabricate a user-refined scenario, do not describe accepted defaults as user answers, and make the evidence-constrained base the main user-facing case only when evidence was sufficient.

## Evidence And Segment Detail

Use this area to connect cited evidence and official segment data to valuation drivers. Keep supported vs explain-only model actions visible. Use driver-specific evidence from `{baseDir}/references/driver-specific-evidence.md`; generic source presence is not enough.

### Driver-Specific Evidence

Summarize the evidence used for assumption judgment. Include source date and direct source URL for every cited claim. If evidence is weak or missing, say the assumption remains baseline/conservative rather than forcing a researched change.

| Driver | Evidence summary | Source | Source date | Direction | Confidence | Assumption implication | Model action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Revenue growth |  |  |  | supports higher/lower or neutral/mixed | high/medium/low |  | governed change, report explanation only, or explain/flag only unsupported |
| Operating margin |  |  |  | supports higher/lower or neutral/mixed | high/medium/low |  | governed change, report explanation only, or explain/flag only unsupported |
| Reinvestment / sales-to-capital |  |  |  | supports higher/lower or neutral/mixed | high/medium/low |  | governed change, report explanation only, or explain/flag only unsupported |
| Risk / WACC |  |  |  | supports higher/lower or neutral/mixed | high/medium/low |  | explain/flag only unless explicit supported scenario |
| Terminal value / mature state |  |  |  | supports higher/lower or neutral/mixed | high/medium/low |  | explain/flag only unless future governed support exists |
| Accounting adjustments |  |  |  | supports higher/lower or neutral/mixed | high/medium/low |  | explain/flag only unless service-returned support exists |

Do not cite search snippets as evidence. Do not count "10-K found", "earnings release found", "SEC filing source captured", or other generic source presence as evidence. The row must name the driver and the relevant fact.

### Segment Discovery

Summarize reportable or business segments from official sources. If revenue shares, margins, or growth rates are not disclosed, say unavailable.

State `segment_economics_quality` when a SegmentEconomics artifact is returned: `validated_full_economics`, `partial_economics`, `revenue_only_segments`, `segment_evidence_insufficient`, or `segment_mapping_blocked`. Reconcile that artifact status against returned service baseline fields: SegmentEconomics acceptance is not effective unless `baseline.segmentAware` is true and `baseline.baselineUseStatus` confirms `validated_segment_weighted`. Do not describe a revenue-only segment package as fully segment-modeled. Show per-driver segment status so revenue mix, growth, margin, and reinvestment intensity are visibly separate.

| Segment | Disclosure | Source | Source date | Mapped industry | Mapping confidence | Driver affected | Use in model |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

| Segment | Revenue mix | Growth | Margin | Reinvestment intensity | Segment economics quality | Limitation |
| --- | --- | --- | --- | --- | --- | --- |
|  | model-supported, report-only, unavailable, or blocked | model-supported, report-only, unavailable, or blocked | model-supported, report-only, unavailable, or blocked | model-supported, report-only, unavailable, or blocked |  |  |

Revenue-only segment evidence cannot support growth, margin, or reinvestment changes. Product or sub-business facts such as Search, YouTube, subscriptions, devices, or Other Bets are report-only unless directly sourced and accepted for that specific driver.

## Assumption Support

Explain whether the evidence supports a governed change or no change. Include confidence and no-change rationale when applicable. Keep supported vs explain-only topics separate. Evidence packet summaries belong here; raw research logs do not.

| Assumption | Baseline | Researched change | Effective | Rationale |
| --- | --- | --- | --- | --- |
| Revenue growth |  |  |  |  |
| Operating margin next year |  | unsupported or explicit scenario only |  |  |
| Operating margin |  |  |  |  |
| Sales-to-capital |  |  |  |  |

## Internal Baseline Audit

This section is explicit audit/debug detail. Do not include it in the default report unless the user asks for audit/debug detail or needs reproducibility detail. It may expose the mechanical baseline, segment-aware mechanical baseline construction, baseline plausibility findings, and blocked fields.

Keep these concepts separate:

- User-refined scenario: deterministic recalculation from bounded `user_judgment` answers.
- Evidence-constrained base: researched case after driver-specific evidence, plausibility gate, and governed recalculation if supported.
- Market-implied diagnostics: report-only implied assumptions or priced-in scenarios. These are not evidence and not autonomous model changes.
- Mechanical baseline: first successful deterministic MCP valuation, internal scaffolding by default.

Show whether the mechanical baseline was segment-aware before researched overrides. Use only MCP/service output and the validated segment package.

| Field | Value |
| --- | --- |
| Baseline quality | `segment_weighted_baseline`, `single_industry_fallback`, `segment_evidence_insufficient`, or `segment_mapping_blocked` |
| Baseline use status |  |
| Segment coverage |  |
| Segment-aware | true/false |
| Mapped industries |  |
| Weighted baseline assumptions | revenue growth, target operating margin, sales-to-capital, WACC when returned |
| Baseline warnings |  |
| Unsupported baseline drivers / adjustment fields |  |
| Segment package used | yes/no plus reason |

If only generic source presence or segment names without revenue weights were found, say the segment package was report-only and label the baseline `segment_evidence_insufficient`. If segment revenue evidence exists but mapping is below the coverage or confidence threshold, label it `segment_mapping_blocked`. If no usable package exists, label the baseline `single_industry_fallback`.

Show baseline quality and baseline use status before presenting assumptions. If `baselineUseStatus` is `mechanical_only`, `segment_evidence_insufficient`, `challenged_baseline`, or `blocked`, do not present target operating margin as a validated researched or segment-weighted assumption.

### Baseline Plausibility Findings

Summarize `baseline_plausibility` in prose and a compact table.

| Check | Status | Evidence or comparison | Action |
| --- | --- | --- | --- |
| Price/value gap | flagged or not flagged | model value vs market price | challenge baseline or no flag |
| Growth | flagged or not flagged | baseline vs growth anchor and evidence | governed change or no-change reason |
| Margin path | flagged or not flagged | next-year margin and target margin separately | target-margin change or unsupported next-year blocker |
| Reinvestment | flagged or not flagged | sales-to-capital vs capex/R&D/working-capital evidence | governed change or no-change reason |
| Risk/WACC | explain/flag only | company risk evidence | no autonomous WACC change |
| Terminal mature state | explain/flag only | durability and competition evidence | no autonomous terminal-growth change |
| Accounting adjustments | explain/flag only | R&D, leases, options, NOLs, tax, cash, debt, share-count evidence | no autonomous accounting change |

### Unsupported Blockers

List unsupported blockers explicitly. Include next-year margin path when it is a problem, because current `operating_margin` control maps only to target operating margin.

| Field | Why unsupported | Report action |
| --- | --- | --- |
| operating_margin_next_year | scenario-only in autonomous researched mode | flag margin-path limitation or use only in user-refined/explicit scenarios |
| wacc | scenario or explain/flag only | do not autonomously change |
| terminal_growth | scenario or explain/flag only | do not autonomously change |
| tax/accounting/options/leases/NOLs/cash/debt/share count/direct outputs | unsupported for autonomous researched recalculation | explain or flag only |

## Terminal Value And Cash-Flow Composition

Use service-returned fields when available:

- Explicit-period present value: `valuation.companyDTO.pvCFOverNext10Years`.
- Terminal value present value: `valuation.companyDTO.pvTerminalValue`.
- Terminal value share of total value: derive only from returned PV fields when both are present.
- Terminal cash flow and terminal value: `valuation.companyDTO.terminalCashFlow` and `valuation.companyDTO.terminalValue`.
- Free cash flow and reinvestment trajectory: `valuation.financialDTO.fcff` and `valuation.financialDTO.reinvestment`.

If these fields are absent, say the composition is unavailable.

## Tax And Accounting Adjustments

Use `structuredContent.accountingAndClaims` and `valuation.assumptionTransparency.accountingAndClaims` when returned. AccountingAndClaims is the structured status source for R&D capitalization, SBC/dilution, leases, options/warrants, NOL/tax, cash, debt, and share count.

Show supported versus report-only accounting labels before explaining impact. Valid labels include `returned`, `missing`, `stale`, `zero_by_default`, `source_required`, `blocked_report_only`, `governed_scenario_supported`, `reconciled`, `conflict`, and `unsupported`.

| Topic | Status | Model treatment | Source class / provider | Effective? | Report action |
| --- | --- | --- | --- | --- | --- |
| R&D capitalization |  | governed scenario, report-only, or unsupported |  | yes/no |  |
| SBC / dilution |  | report-only by default |  | no |  |
| Leases |  | returned, source-required, or zero-by-default |  | yes/no |  |
| Options / warrants |  | service-calculated when inputs are available or blocked report-only |  | yes/no |  |
| NOL / tax |  | scenario-only or report-only |  | yes/no |  |
| Cash |  | service-returned data quality context |  | yes/no |  |
| Debt |  | service-returned data quality context |  | yes/no |  |
| Share count |  | service-returned data quality context |  | yes/no |  |

Do not infer accounting support from a numeric zero. A zero adjustment needs a status such as `returned`, `missing`, `zero_by_default`, or `source_required`. Do not invent accounting adjustments when service fields are absent, missing, defaulted, unsupported, or report-only.

For SBC/dilution, show service-returned report-only diagnostics when present: SBC percent of revenue, SBC percent of operating income or free cash flow, diluted share-count trend, and diluted-share consistency status. Do not treat SBC as a hidden cash-flow, reinvestment, or dilution adjustment.

For cash, debt, and share count, show source and reconciliation status before discussing the equity bridge. Statuses such as `stale`, `reconciled`, `conflict`, and `source_required` are data-quality labels, not free-form override permission.

Explain tax-rate assumptions, R&D capitalization, operating lease conversion, options/warrants, NOLs, one-time charges, and other claims only when supported by service output or cited as explain-only limitations. R&D capitalization can affect recalculation only through the governed AccountingAndClaims explicit scenario with multi-year R&D history, amortization policy, source provenance, and audit recording. Lease conversion is report-only in Phase 5 and has no governed recalculation path. SBC/dilution, leases, options/warrants, NOL/tax, cash, debt, and share-count topics remain report-only, statused, or scenario-only unless a tested governed path accepts them.

## Effective Assumptions

State the assumptions the deterministic service actually used after recalculation. Keep requested, mapped, unsupported, metadata, and effective assumptions separate when describing recalculation.
