# Prospectus Mode

Use prospectus mode when the user provides a SEC EDGAR HTML prospectus URL for an IPO, direct listing, confidential-submission follow-on, or other offering document where ordinary ticker market data is unavailable or inappropriate. This mode is educational use only and not financial advice.

Prospectus mode is a filing-first version of the normal researched valuation workflow. The valuation model and final guided refinement flow stay the same; the difference is that the base financial packet comes from a reviewed prospectus instead of ticker market-data endpoints.

1. Call `stockvaluation.extract_prospectus` with the SEC EDGAR Archives filing URL.
2. Stop for review when `sourceQualityGate.reason = prospectus_extraction_review_required`.
3. After the user approves or corrects the packet, set `reviewStatus` to `reviewed` and call `stockvaluation.value_prospectus`.
4. Continue into the normal researched workflow: build the evidence packet, stop at `evidence-review-gate.md`, run baseline plausibility checks, then use `guided-valuation-refinement.md` for material user-judgment questions unless the user explicitly requested quick/no-questions/automation/smoke-test.

The valuation result must identify `priceBasis = offering_price`, `sourceClass = primary_filing`, and `provider = sec-edgar-prospectus`. Do not describe the result as a live trading-price valuation. The offering price is the prospectus price basis, not a recommendation, target price, buy/sell/hold view, or personalized investment instruction.

Read `valuationBasisStatus`, `valuationCaseStatus`, `proceedsBasis`, `valuationBasisWarnings`, `dcf.valueVisibility`, `baseline.baselineUseStatus`, `baseline.baselineWarnings`, and `baseline.unsupportedBaselineDrivers` before showing any value. If `valuationBasisStatus = clean_pro_forma_basis` and `valuationCaseStatus = clean_valuation_case`, the cash/share basis and valuation case are clean. If `valuationBasisStatus = pro_forma_cash_missing`, say post-offering shares require pro-forma cash and net proceeds were not resolved. If `valuationBasisStatus = gross_proceeds_estimate_only`, say only gross proceeds could be inferred and that is not a clean basis. If `valuationCaseStatus = challenged_valuation_case`, `dcf.valueVisibility = diagnostic_only`, or `baseline.baselineUseStatus = challenged_baseline`, say no clean user-facing valuation was produced and do not show the diagnostic value before evidence review. A clean cash/share basis is not enough to headline a value when the segment or assumption case remains challenged.

If `unsupportedBaselineDrivers` includes `prospectus_default_used`, `prospectus_zero_default`, `prospectus_growth_default`, or `rd_capitalization_source_missing`, say the service used fallback defaults only to run a diagnostic DCF. Ask the agent/user to supply or research the missing country, currency, operating income, prior revenue, cash, debt, book equity, or R&D source before treating the valuation as clean.

If the user later chooses `continue with caveats`, asks for valuation detail, or asks for audit detail, show the returned `dcf.estimatedValuePerShare` as a challenged diagnostic value when it exists. Put the warning next to the number: it is diagnostic-only, depends on incomplete cash/share or segment evidence, and is not a clean intrinsic value, fair value, target price, or recommendation.

Prospectus extraction review is not the evidence review gate. It only checks whether the filing-derived packet is safe to use as model input. It also does not replace guided valuation refinement. User approval of the extracted packet is not permission to skip framing questions, evidence review, assumption judgment, or guided user questions in the default workflow.

## Scenario And Source Boundaries

Prospectus mode has a deterministic explicit scenario path through `stockvaluation.value_prospectus.scenario`. Use it when the user/model supplies story assumptions such as net proceeds, target revenue, margin, sales-to-capital, R&D capitalization, terminal cost of capital, terminal growth, and terminal return on capital.

The valuation service extracts raw prospectus segment candidate tables and rows. It does not choose segment rows, compute final segment weights, or hard-code segment-to-industry mapping. When material candidate rows are present, use the agent's search tools and the normal `segment-discovery.md` workflow to research what each row actually means, distinguish totals from subrows, and decide which rows belong in the model. Then pass a deterministic `scenario.segments` object to `stockvaluation.value_prospectus` with explicit `name`, `sector_key`, `mapped_industry`, revenue path or target revenue, target margin, sales-to-capital, and any segment-specific terminal assumptions. Keep the source rationale in the evidence packet and report, not as hidden Java mapping.

Do not turn a material prospectus segment gap into a vague prompt such as "provide segment mappings." Ask the actual story-to-numbers question: should the disclosed businesses be modeled separately, which disclosed rows are base businesses versus subrows or optional upside, and what bounded segment growth, margin, and reinvestment assumptions should be used. The agent must show source-backed default choices before asking the user to correct them. If the prospectus has enough segment revenue, margin, and reinvestment evidence to create a bounded default, build the explicit `scenario.segments` package and send it to `stockvaluation.value_prospectus`; do not leave the business-definition or segment-mix story as report-only by default.

For unusual IPOs, do not force all business lines into a single industry. If a material raw segment cannot be mapped with source-backed evidence, leave it unmapped in the review and say a clean segment scenario is not ready. If the segment is an optional future business or expansion option, keep it as an explicit upside scenario rather than the default case unless the prospectus or other source-backed evidence supports making it part of the base story.

If guided answers are not sent through `stockvaluation.value_prospectus.scenario`, they are report-only guided defaults. Do not call report-only prospectus guided answers a user-refined scenario, and do not say they changed the per-share value. When `stockvaluation.apply_guided_answers` returns a supported `prospectusScenarioCandidate`, run `stockvaluation.value_prospectus` again with that scenario before writing the final report. If it returns `userJudgment.scenario_status = candidate_values_required`, do not write the final report yet; supply source-backed candidate values for the listed requirements or ask the user for the missing story-to-number assumptions. A prospectus report may say user defaults were accepted for report context only; it may call the final case a scenario only when deterministic prospectus scenario valuation actually happened.

If a visible guided card says "Question 1 of 3", then ask all three questions one at a time, or when the user chooses `use defaults`, summarize all remaining default answers before the final report. All remaining default answers must be summarized. Do not skip hidden questions silently.

SEC filing facts are primary. External news is report-only context unless it is used only to confirm non-model background. External news must not override filing facts, offering price, share count, segment revenue, cash, debt, revenue, or operating results extracted from the SEC prospectus.

## Required review

Before calling `stockvaluation.value_prospectus`, review the extracted `ProspectusFinancialPacket` with the user:

- Company legal name, expected symbol, CIK, accession number, form type, filing date, and source URL.
- Offering price, offering-price unit, share-count basis, and post-offering share count.
- Country of incorporation, valuation currency, and industry or segment industry mapping.
- Revenue, operating income or operating loss, cash, debt, operating cash flow, capital expenditures, and source table titles.
- Raw segment candidate tables and rows, candidate revenue amounts, source rows, source tables, and any researched mappings supplied by the agent or user.
- Any unresolved pro forma basis, missing units, ambiguous scales, or conflicting share-count facts.

User approval is a modeling-input review, not financial advice. User corrections are not external evidence unless they are backed by filing rows or additional cited primary sources.

Do not show the user only a bare list of allowed actions. Show a compact review card first:

- What was extracted: company, filing metadata, price basis, share basis, core financial facts, raw segment candidate tables and rows, and source provenance.
- What looks usable: source-backed fields with units, scale, period, row labels, and table titles.
- What needs review: missing fields, ambiguous units/scale, conflicting share counts, pro forma basis, weak provenance, and extraction issues.
- Recommended next action: one of the numbered choices below, with one plain sentence explaining why.

Choose `approve_extracted_packet` only when required fields are present, source-backed, and internally consistent. For an empty packet, missing revenue, missing share count, missing units/scale, missing filing metadata, or unresolved extraction issues, recommend `stop` or `correct_packet`, not approval.

Show these numbered human choices:

```text
1. Approve and continue
   Use this only if the filing metadata, revenue, share count, units/scale, and source labels look correct.

2. Correct the packet
   Use this if a value is wrong or missing and you can provide the correction.

3. Add sources
   Use this if another filing, amendment, or primary source should be checked before valuation.

4. Stop
   Use this if the packet is empty, unclear, missing key fields, or not trustworthy.
```

Map the user's number to the internal action before continuing:

- `1` -> `approve_extracted_packet`
- `2` -> `correct_packet: ...`
- `3` -> `add_sources: ...`
- `4` -> `stop`

If the user chooses 2 or 3 without details, ask one short follow-up for the correction or source. Do not ask humans to type internal action names unless they are using automation.

## Allowed action

- Use only SEC EDGAR Archives HTML URLs accepted by the MCP schema.
- Use `stockvaluation.extract_prospectus` for extraction and review metadata.
- Stop at `prospectus_extraction_review_required`, show the compact review card, and ask the user to choose numbered option 1, 2, 3, or 4.
- Call `stockvaluation.value_prospectus` only after `reviewStatus` is `reviewed`. Prefer `review_reference` from the extraction result plus `review_status = reviewed`; do not rebuild a compact packet from the review summary.
- After `stockvaluation.value_prospectus`, continue into the normal researched workflow. Build and review evidence, run baseline plausibility, ask guided valuation refinement questions when material, and only then write the final educational report unless the user explicitly requested a bypass.
- After guided answers or accepted defaults, call `stockvaluation.apply_guided_answers` when available. If it returns supported prospectus scenario inputs, call `stockvaluation.value_prospectus` again with the reviewed packet and `prospectusScenarioCandidate.scenario` before the final report. If it returns `candidate_values_required`, resolve those candidate values or mark that no user-refined scenario was calculated.
- Label provenance as `primary_filing` / `sec-edgar-prospectus` when returned.
- Label the price basis as `offering_price` in the report snapshot and source summary.
- Keep unsupported accounting and capital-claim topics report-only unless the service returns a governed path.

## Do not

- Do not paste raw HTML into MCP arguments.
- Do not call `stockvaluation.value_prospectus` on a packet with `reviewStatus = review_required`, missing, or any value other than `reviewed`.
- Do not reconstruct the prospectus packet by hand when `prospectus.reviewReference` is available. Hand reconstruction often drops cash, debt, book equity, cash-flow, or segment-candidate snapshots.
- Do not use `stockvaluation.value_ticker`, Yahoo Finance, yfinance, market-data revenue estimates, or a trading market price for the prospectus path unless the user explicitly leaves prospectus mode.
- Do not infer missing units, table scale, pro forma share basis, or offering terms when the extracted packet flags ambiguity.
- Do not convert `offering_price` into recommendation language such as buy, sell, hold, target price, or should invest.
