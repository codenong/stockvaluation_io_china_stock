# Prospectus Mode

Use prospectus mode when the user provides a SEC EDGAR HTML prospectus URL for an IPO, direct listing, confidential-submission follow-on, or other offering document where ordinary ticker market data is unavailable or inappropriate. This mode is educational use only and not financial advice.

Prospectus mode is a filing-first version of the normal researched valuation workflow. The valuation model and final guided refinement flow stay the same; the difference is that the base financial packet comes from a reviewed prospectus instead of ticker market-data endpoints.

1. Call `stockvaluation.extract_prospectus` with the SEC EDGAR Archives filing URL.
2. Stop for review when `sourceQualityGate.reason = prospectus_extraction_review_required`.
3. After the user approves or corrects the packet, set `reviewStatus` to `reviewed` and call `stockvaluation.value_prospectus`.
4. Continue into the normal researched workflow: build the evidence packet, stop at `evidence-review-gate.md`, run baseline plausibility checks, then use `guided-valuation-refinement.md` for material user-judgment questions unless the user explicitly requested quick/no-questions/automation/smoke-test.

The valuation result must identify `priceBasis = offering_price`, `sourceClass = primary_filing`, and `provider = sec-edgar-prospectus`. Do not describe the result as a live trading-price valuation. The `offering_price` is the prospectus price basis, not a recommendation, target price, buy/sell/hold view, or personalized investment instruction.

Prospectus extraction review is not the evidence review gate. It only checks whether the filing-derived packet is safe to use as model input. It also does not replace guided valuation refinement. User approval of the extracted packet is not permission to skip framing questions, evidence review, assumption judgment, or guided user questions in the default workflow.

## Scenario And Source Boundaries

Current prospectus mode has `stockvaluation.value_prospectus` for the reviewed packet. If there is no prospectus-specific recalculation path in the returned MCP tools, guided answers are report-only guided defaults. Do not call report-only prospectus guided answers a user-refined scenario, and do not say they changed the per-share value. A prospectus report may say user defaults were accepted for report context only; it may call the final case a user-refined scenario only when a deterministic prospectus recalc actually happened.

If a visible guided card says "Question 1 of 3", then ask all three questions one at a time, or when the user chooses `use defaults`, summarize all remaining default answers before the final report. All remaining default answers must be summarized. Do not skip hidden questions silently.

SEC filing facts are primary. External news is report-only context unless it is used only to confirm non-model background. External news must not override filing facts, offering price, share count, segment revenue, cash, debt, revenue, or operating results extracted from the SEC prospectus.

## Required review

Before calling `stockvaluation.value_prospectus`, review the extracted `ProspectusFinancialPacket` with the user:

- Company legal name, expected symbol, CIK, accession number, form type, filing date, and source URL.
- Offering price, offering-price unit, share-count basis, and post-offering share count.
- Revenue, operating income or operating loss, cash, debt, operating cash flow, capital expenditures, and source table titles.
- Segment revenue weights, mapped sector keys, mapping confidence, and any extraction issues.
- Any unresolved pro forma basis, missing units, ambiguous scales, or conflicting share-count facts.

User approval is a modeling-input review, not financial advice. User corrections are not external evidence unless they are backed by filing rows or additional cited primary sources.

Do not show the user only a bare list of allowed actions. Show a compact review card first:

- What was extracted: company, filing metadata, price basis, share basis, core financial facts, segments, and source provenance.
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
- Call `stockvaluation.value_prospectus` only after `reviewStatus` is `reviewed`.
- After `stockvaluation.value_prospectus`, continue into the normal researched workflow. Build and review evidence, run baseline plausibility, ask guided valuation refinement questions when material, and only then write the final educational report unless the user explicitly requested a bypass.
- Label provenance as `primary_filing` / `sec-edgar-prospectus` when returned.
- Label the price basis as `offering_price` in the report snapshot and source summary.
- Keep unsupported accounting and capital-claim topics report-only unless the service returns a governed path.

## Do not

- Do not paste raw HTML into MCP arguments.
- Do not call `stockvaluation.value_prospectus` on a packet with `reviewStatus = review_required`, missing, or any value other than `reviewed`.
- Do not use `stockvaluation.value_ticker`, Yahoo Finance, yfinance, market-data revenue estimates, or a trading market price for the prospectus path unless the user explicitly leaves prospectus mode.
- Do not infer missing units, table scale, pro forma share basis, or offering terms when the extracted packet flags ambiguity.
- Do not convert `offering_price` into recommendation language such as buy, sell, hold, target price, or should invest.
