# Educational Valuation Report Template

Use this structure after the full researched valuation workflow completes. Write the report from MCP JSON, the valuation audit packet, evidence packet, segment discovery, `assumption_judgment`, baseline plausibility, guided-refinement `user_judgment` when present, recalculation output, and effective assumptions.

Do not print raw `assumption_judgment` JSON by default. Summarize it in prose and tables. Do not invent missing values. If MCP/service output does not return a value, say unavailable or omit the table.

Do not print raw `valuation_audit_packet` JSON by default. Summarize the packet status, packet reference, final case type, rejected evidence, unsupported fields, guided-refinement status, and data-quality limitations in prose or compact tables. Keep mechanical baseline value/detail out of user-facing output unless the user explicitly asks for audit/debug detail.

The user-refined scenario is the main scenario when guided refinement was completed. The mechanical baseline is internal scaffolding by default: do not include mechanical baseline value as a primary valuation case in the main report. Keep mechanical baseline detail available only in the explicit audit/debug section.

## Educational-Use Framing

This report is for educational use only and is not financial advice. It explains one local DCF model output and the assumptions that drive it. The result should be read as a scenario, not an instruction.

## Valuation Audit Packet Summary

Use `structuredContent.auditPacket.summary` when returned. State the final case type before presenting any valuation result:

- `evidence_constrained_no_change`: evidence was valid or reviewable, but no governed model change was accepted.
- `evidence_constrained_governed_recalculation`: governed evidence supported a supported recalculation.
- `user_refined_scenario`: bounded user judgment created the main scenario; user answers are not external evidence.
- `insufficient_researched_evidence`: the run did not earn a user-facing valuation case.

Include the packet reference and a compact status summary. Do not present `mechanical_baseline` as a final case type, visible scenario, or report case. If the audit packet says `insufficient_researched_evidence`, stop or explain the insufficiency without showing the mechanical baseline value.

## Valuation Snapshot

Lead with the scenario the user actually selected. Include compact values only when returned by MCP/service output.

| Field | Value |
| --- | --- |
| Company |  |
| Ticker |  |
| Main scenario | user-refined scenario, evidence-constrained base, or one-shot baseline path |
| User-refined scenario intrinsic value per share |  |
| Evidence-constrained base intrinsic value per share |  |
| Market price |  |
| Equity value |  |
| Gap to market | currency amount and percent |
| Currency and source date |  |
| Model, growth pattern, projection years |  |
| Service/model/data versions |  |
| Baseline quality | segment_weighted_baseline, single_industry_fallback, segment_evidence_insufficient, segment_mapping_blocked, or not_calculated |
| Baseline use status | validated_segment_weighted, mechanical_only, segment_evidence_insufficient, challenged_baseline, or blocked |
| Segment coverage |  |
| Mapped industries |  |
| Target operating margin source/status | segment-weighted, single-industry mechanical fallback, governed override, unsupported/challenged, or blocked |

Separate market price, model intrinsic value, assumptions, and evidence. Describe the gap as a model result, not as a recommendation. The mechanical baseline value is omitted from the default snapshot unless the user asks for audit/debug detail.

## Source Quality Summary

Use `structuredContent.provenance` and `valuation.assumptionTransparency.sourceProvenance` when returned. Keep this section compact and visible in the default report.

| Field | Value |
| --- | --- |
| Core financial source class | `primary_filing`, `yahoo_normalized`, `company_ir`, or `agent_researched` |
| Provider |  |
| Source date / period end |  |
| Retrieval status |  |
| Source policy status | `valid_source_provenance`, `primary_filing_used`, `primary_source_missing_fallback`, `yahoo_normalized_with_cross_check_status`, `stale_source_date`, or `missing_source_date` |
| Cross-check status | `company_report_cross_checked`, `company_report_check_pending`, `company_report_unavailable`, `not_applicable`, or other returned status |
| Material warnings |  |

For US researched valuations, prefer SEC/XBRL, company facts, or filing-derived primary financial data when returned. If the output shows `primary_source_missing_fallback`, say the run used Yahoo-normalized financials as a classified fallback and do not imply the core financials are primary-source backed.

For non-US researched valuations, Yahoo-normalized financials may be the main normalized source when the report labels the source class and gives the company-report or filing cross-check status. If cross-checks are pending, say so plainly and treat material accounting or segment claims as limitations until checked.

If Yahoo-normalized data and filing/company-report data differ materially, include the returned data-quality warning and treat it as a limitation, not as an automatic assumption override.

## Central Narrative Tension

Write a short prose setup before the driver sections. If `marketImpliedExpectations` or `pricedInExpectations` are returned, use them as the central tension:

- What growth is the market price implying?
- What operating margin is the market price implying?
- What sales-to-capital or reinvestment efficiency is required?
- What risk or cost-of-capital setting makes the current price easier or harder to justify?
- Are those combinations believable given the evidence?

Use market-implied/priced-in data as report inputs, not autonomous model changes. Market-implied diagnostics are never evidence for the evidence-constrained base. Do not use market-implied values as the researched base.

## Growth

Write prose, not only bullets. Explain revenue drivers, market expansion, scale advantages, pricing power, segment growth, growth-anchor context, and what growth would have to be true. Compare the main scenario growth to returned market-implied growth when available.

## Margins

Write prose. Explain current and target operating margins, operating leverage, cost structure, pricing power, competitive positioning, and what margin expansion or compression would have to be true. Compare the main scenario margin to returned market-implied margin when available.

## Investment Efficiency

Write prose. Explain sales-to-capital, reinvestment discipline, return on capital, asset intensity, capital efficiency, and whether the growth story can be funded. Tie high growth to reinvestment needs.

## Risk

Write prose. Explain operational, competitive, regulatory, macro, currency, cyclicality, cost-of-capital, and data-quality risks. WACC, terminal growth, and tax changes are explain-only in autonomous researched judgment unless the user explicitly requests a supported scenario.

## Market-Implied Expectations

Use `valuation.assumptionTransparency.marketImpliedExpectations` when returned.

| Lever | Model value | Implied value | Gap | Solved? | Note |
| --- | --- | --- | --- | --- | --- |
| Revenue growth |  |  |  |  |  |
| Operating margin |  |  |  |  |  |
| Sales-to-capital |  |  |  |  |  |

Explain that each single-variable implied metric holds other variables fixed. If `marketImpliedExpectations` is absent, say it is unavailable rather than recreating it.

## Assumptions Used

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

## Data Quality And Limitations

Cover Yahoo Finance coverage, missing or stale data, unsupported-company warnings, growth-anchor confidence warnings, currency issues, and absent report fields. Do not hide unsupported fields.

If evidence is weak or missing, keep the relevant assumption baseline/conservative rather than forcing a researched change. Do not invent missing values.

## Key Takeaways

Use a prose conclusion, not recommendation language. Cover:

- The central valuation tension.
- Strongest assumption support.
- Weakest assumption support.
- What would change the model.
- Which topics are supported adjustments, supported explanations, explain-only, future-support, unsupported-stop, or out-of-scope.

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

## Guided User Judgment And User-Refined Scenario

Use this section when guided refinement was run. If the user requested a quick/no-questions path, say guided refinement was bypassed by request.

State plainly: user answers define a scenario; they are not independent evidence.

| Question | Driver | Baseline assumption | Evidence summary | User answer | Model action |
| --- | --- | --- | --- | --- | --- |
|  | revenue growth, margin path, target margin, convergence year, sales-to-capital, sector driver, or report-only topic |  |  |  | user scenario override, report-only user judgment, or unsupported |

Do not include unsupported answers in the MCP payload. Keep report-only answers in prose and metadata.

## Evidence And Segment Summary

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

| Segment | Disclosure | Source | Source date | Mapped industry | Mapping confidence | Driver affected | Use in model |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

## Assumption Judgment Summary

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

Explain tax-rate assumptions, R&D capitalization, operating lease conversion, options/warrants, NOLs, one-time charges, and other claims only when supported by service output or cited as explain-only limitations. R&D capitalization is explain/flag only until governed input support is fully wired and tested.

## Effective Assumptions

State the assumptions the deterministic service actually used after recalculation. Keep requested, mapped, unsupported, metadata, and effective assumptions separate when describing recalculation.
