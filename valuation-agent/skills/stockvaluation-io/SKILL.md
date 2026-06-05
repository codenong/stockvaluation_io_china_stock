---
name: stockvaluation-io
description: Use whenever the prompt mentions stockvaluation.io, StockValuation.io, stockvaluation, the local valuation MCP, or asks to value a public company with the StockValuation workflow. Runs local MCP valuation, stops for evidence review, and asks guided valuation-refinement questions before the final report by default.
version: 2.0.0-agent-native
homepage: https://github.com/stockvaluation-io/stockvaluation_io
---

# StockValuation.io Agent Valuation

Use this skill whenever the prompt mentions `stockvaluation.io`, `StockValuation.io`, `stockvaluation`, the local valuation MCP, or asks you to value a public company, critique DCF assumptions, build scenarios, explain valuation drivers, or troubleshoot the local StockValuation agent-native service.

The product surface is the user's agent. The deterministic valuation math comes from local MCP tools. You orchestrate the workflow, gather evidence, produce assumption judgment, and write the educational report from MCP JSON.

## Invocation And Stop Rules

- A plain request such as "value COMPANY using stockvaluation.io" is the default full researched valuation flow, not a quick valuation and not a one-shot report request.
- Do not infer a guided-refinement bypass from ordinary phrasing. Do not infer an evidence-review bypass from ordinary phrasing. Bypass either step only when the user explicitly says quick, no questions, skip questions, one-shot report, automation, smoke-test, or equivalent.
- In the default full researched valuation flow, the final report is blocked until the evidence review gate is cleared and until guided refinement is either completed from user answers or explicitly bypassed by the user.
- The final report is blocked until guided refinement is completed or explicitly bypassed; an evidence-review approval or caveated continuation alone is not permission to skip guided questions.
- If the user provides a SEC EDGAR HTML prospectus URL or asks for a prospectus-driven valuation, use prospectus mode in `{baseDir}/references/prospectus-mode.md`. Call `stockvaluation.extract_prospectus`, stop at `prospectus_extraction_review_required`, show a compact review card, and call `stockvaluation.value_prospectus` only after the packet `reviewStatus` is `reviewed`. Do not show the user only a bare list of allowed actions. Show four numbered human choices with plain explanations, then map the user's number to the internal action.
- After evidence gathering and driver-specific evidence classification, stop at the evidence review gate. Do not ask guided valuation questions or write the final report before the gate is cleared.
- After the evidence review gate is cleared and the evidence-constrained base case is built, build a hidden guided question plan that is materiality-driven, then ask every material company-specific question up to a hard cap of 15 visible guided questions. Ask one question at a time by default. Do not ask a batch of 4-6 questions unless the user explicitly requests batch mode.
- Each visible question must show "My analysis" or equivalent modeling-default language, why the default was selected, evidence used, business impact, model impact, and confidence. The default is educational modeling judgment, not financial advice.
- Do not write the final report in that same response as an unanswered guided question.

## Context Discipline

- In full researched valuations, delegate source-heavy research to fresh-context subagents when the client supports subagents or task delegation. Use separate research workers for filings/annual reports, earnings/IR materials, latest company news, and segment evidence when those sources are relevant.
- The main agent should keep MCP JSON, the compact evidence packet, assumption judgment, guided questions, and final report logic in its own context. Do not keep long filing text, article bodies, transcript excerpts, or broad search traces in the main context.
- Each research subagent must return a compact evidence summary with source URLs, source dates, driver tags, confidence, and conflicts. The main agent remains responsible for deciding whether evidence can affect assumptions.

## Default Workflow: Full Researched Valuation

1. Call `stockvaluation.health`.
2. Call `stockvaluation.researched_baseline` for the ticker. This is the default full researched baseline entrypoint and it enables researched source policy. If company name, website, or industry context is unavailable before this call, use `stockvaluation.value_ticker` only as a mechanical preflight lookup and do not treat that preflight output as the researched base. Keep `stockvaluation.value_ticker` mechanical.
3. Read `structuredContent.sourceQualityGate` immediately after `stockvaluation.researched_baseline`. If SEC was expected and fallback was used, for example `sec_http_error_yahoo_fallback`, stop immediately after source selection, before company-report cross-check, segment recalculation, assumption judgment, guided refinement, or final report. Say plainly that SEC primary source was expected but unavailable, Yahoo-normalized fallback is available, and ask the user to choose `continue_with_fallback`, `retry_primary_source`, or `stop`; do not show a visible `Source quality gate` heading or table row. If the status is `primary_adapter_not_supported_yahoo_normalized`, do not describe it as an SEC failure. Say plainly that no supported deterministic primary-filing adapter covers this listing, require company-report cross-check before researched claims, and ask the user to choose `continue_after_company_report_cross_check`, corrections/additional sources, or `stop`; do not show a visible `Source quality gate` heading or table row. Do not present a generic `approve` prompt as sufficient for either source-quality gate.
4. Run segment discovery using `{baseDir}/references/segment-discovery.md`, then build and validate the segment package. When credible segment revenue weights exist, construct the segment-aware mechanical baseline through the governed recalculation path with only `segments` plus researched-baseline request policy metadata before any discretionary researched overrides. When no valid segment package exists, keep the `stockvaluation.researched_baseline` result as the single-industry researched-source baseline.
5. If the baseline payload has `ok: false`, call `stockvaluation.explain_failure`, explain the classified failure plainly, and do not invent a valuation.
6. Extract the live baseline contract first: baseline quality, baseline use status, segment awareness, segment coverage, mapped industries, weighted baseline assumptions, baseline warnings, unsupported baseline drivers/adjustment fields, target operating margin source/status, AccountingAndClaims statuses, DCF, company, industry, country, currency, assumptions, growth anchor, warnings, sourceQualityGate, provenance, and valuation output.
7. Build an evidence packet using `{baseDir}/references/search-and-evidence.md`. For full researched valuations, run source-heavy searches in fresh-context subagents when available and have them return compact evidence summaries only. Then classify driver-specific evidence with `{baseDir}/references/driver-specific-evidence.md`.
8. Unless the user explicitly requested quick valuation, no questions, skip questions, one-shot report, automation, or smoke-test, stop at the human evidence review gate in `{baseDir}/references/evidence-review-gate.md`. Show source quality, sources checked with dates, driver-specific evidence, segment evidence/limitations, latest material context, conflicts, data gaps, and supported/report-only/unsupported treatment, but keep `sourceQualityGate` details as internal decision metadata and do not use visible headings/labels named `Source quality gate`, `Segment baseline`, `Segment-aware MCP value`, `Important caveat`, or `Caveats and data gaps`. Require the user to approve, correct, add sources, or continue with caveats before continuing. User approval is not financial advice; user corrections are not external evidence unless source-backed and processed through evidence rules.
9. Run the baseline plausibility gate in `{baseDir}/references/baseline-plausibility.md` to distinguish the mechanical baseline, segment-aware mechanical baseline, evidence-constrained base, and market-implied diagnostics before judging assumptions.
10. Apply the method checks in `{baseDir}/references/damodaran-method.md`, `{baseDir}/references/damodaran-coverage-map.md`, `{baseDir}/references/damodaran-source-map.md`, and `{baseDir}/references/assumption-checks.md`.
11. Apply the focused decision guides that match the company and evidence: growth/reinvestment, terminal value, model/lifecycle, R&D, risk/currency/country, accounting cleanup, options/leases/claims, segment quality, special-company stop rules, and `{baseDir}/references/financial-field-definitions.md`.
12. Produce the strict `assumption_judgment` JSON block described in `{baseDir}/references/assumption-judgment.md`, using driver-specific evidence rather than generic source presence and incorporating baseline plausibility.
13. Auto-recalculate once with `stockvaluation.recalculate` using `request_policy.mode = "autonomous_researched"` when the baseline valuation succeeded and the governed evidence-constrained payload is supported. Do not hand-compute valuation math.
14. Unless the user explicitly requested quick valuation, no questions, skip questions, one-shot report, automation, or smoke-test, run guided refinement using `{baseDir}/references/guided-valuation-refinement.md`. Build a hidden guided question plan of company-specific bounded questions after the evidence review gate is cleared, baseline plausibility is checked, and the evidence-constrained base exists; the plan must be materiality-driven. Ask every material company-specific question up to a hard cap of 15 visible guided questions, with no forced minimum. If only one or two questions matter, ask only those. If none matter, explain and do not invent filler. Ask one question at a time by default. Do not ask a batch of 4-6 questions unless the user explicitly requests batch mode. Do not treat a plain "value COMPANY using stockvaluation.io" request as a one-shot path.
15. Accumulate answered choices into a distinct `user_judgment` package. User answers are user judgment, not evidence. Recalculate once, after guided refinement is complete, with `stockvaluation.recalculate` using `request_policy.mode = "user_refined_scenario"` and attach `user_judgment` as metadata. Keep unsupported or report-only answers out of the service payload.
16. For explicitly requested quick/no-questions/one-shot/automation/smoke-test paths, label the evidence review, sourceQualityGate, and guided-refinement bypasses, do not fabricate a user-refined scenario, and write the one-shot educational report after the evidence-constrained workflow when available.
17. Build and read the Scenario Book using `{baseDir}/references/scenario-book.md` and returned `structuredContent.scenarioBook` when present. Use it to separate the evidence-constrained base, user-refined scenario, explicit scenario, market-implied diagnostics, source policy, sourceQualityGate, and internal mechanical baseline references.
18. Write the final educational report using `{baseDir}/references/report-template.md` as the canonical controlling structure. Use `{baseDir}/references/narrative-report-style.md` only as subordinate prose guidance, summarizing the judgment in prose and tables rather than printing raw JSON by default.
19. Apply `{baseDir}/references/no-advice-policy.md` before finalizing.

## Prospectus Workflow

Use this workflow when the input is a SEC EDGAR Archives HTML prospectus URL, especially for IPO or offering cases where an ordinary ticker and trading market price may not exist.

1. Call `stockvaluation.health`.
2. Call `stockvaluation.extract_prospectus` with `filing_url` and optional `expected_company` or `expected_symbol` only. Do not paste raw HTML into the MCP call.
3. Read `structuredContent.prospectus.packet`, `structuredContent.sourceQualityGate`, and `structuredContent.provenance`. The extraction must return `sourceQualityGate.reason = prospectus_extraction_review_required`, `sourceClass = primary_filing`, and provider `sec-edgar-prospectus` before it can support prospectus mode.
4. Stop and ask the user to review the extracted company identity, filing metadata, `offering_price`, share-count basis, financial statement facts, segment revenue weights, source table titles, and extraction issues. The review is educational modeling control and is not financial advice. Do not show the user only a bare list of allowed actions. Show a compact review card with what was extracted, what is missing or ambiguous, the recommended next action, and four numbered human choices: `1` approve and continue, `2` correct the packet, `3` add sources, or `4` stop. Map the number to the internal action names in `{baseDir}/references/prospectus-mode.md`; do not ask humans to type internal action names unless they are using automation.
5. If the user approves or corrects the packet, update only the reviewed/corrected packet fields and set `reviewStatus` to `reviewed`. If the user adds sources, process them before valuation. If the user stops, do not value the prospectus.
6. Call `stockvaluation.value_prospectus` with the reviewed packet. Use the returned `priceBasis = offering_price`; do not substitute Yahoo Finance, yfinance, market-data revenue estimates, or a live trading market price.
7. Prospectus extraction review is not the evidence review gate and does not replace guided valuation refinement. After `stockvaluation.value_prospectus`, continue into the normal researched workflow: build the evidence packet, stop at `{baseDir}/references/evidence-review-gate.md`, run baseline plausibility, and use `{baseDir}/references/guided-valuation-refinement.md` for material user-judgment questions unless the user explicitly requested quick/no-questions/automation/smoke-test.
8. If there is no prospectus-specific recalculation path, guided answers are report-only guided defaults. Do not call report-only prospectus guided answers a user-refined scenario unless a deterministic prospectus recalc actually happened. If the visible guided flow says "Question 1 of 3" and the user accepts defaults, all remaining default answers must be summarized; do not skip hidden questions silently.
9. SEC filing facts are primary. External news is report-only context and external news must not override filing facts from the prospectus.
10. Write the final report using `{baseDir}/references/report-template.md`, `{baseDir}/references/prospectus-mode.md`, and `{baseDir}/references/no-advice-policy.md`. Label provenance as `primary_filing` / `sec-edgar-prospectus` and keep recommendation language out of the report.

## Tool Rules

- Use the MCP tools documented in `{baseDir}/references/mcp-tools.md`.
- Treat MCP JSON as the source of truth for valuation output.
- Do not invent missing service fields, missing financial data, growth-anchor confidence, or scenario math.
- Use `stockvaluation.researched_baseline` as the full researched baseline entrypoint. Keep `stockvaluation.value_ticker` mechanical for preflight and mechanical diagnostics.
- Use `stockvaluation.extract_prospectus` and `stockvaluation.value_prospectus` only for the prospectus workflow. `stockvaluation.value_prospectus` requires a reviewed `ProspectusFinancialPacket`; do not bypass `prospectus_extraction_review_required`.
- For prospectus workflow output, label `offering_price`, `primary_filing`, and `sec-edgar-prospectus` exactly when returned. Do not use Yahoo Finance or yfinance as the source of prospectus financials or price basis.
- Do not describe `stockvaluation.value_ticker` as SEC primary-source backed unless returned provenance says `primary_filing`. When the service returns `sec_http_error_yahoo_fallback`, `sec_missing_user_agent_yahoo_fallback`, or another `sec_*_yahoo_fallback` status, label Yahoo-normalized financials as fallback and do not imply SEC support. When the service returns `primary_adapter_not_supported_yahoo_normalized`, require company-report cross-check before researched claims.
- Treat `sourceQualityGate.status = requires_user_decision` as a source-quality stop point unless the user explicitly selected quick, no-questions, automation, or smoke-test bypass. For SEC fallback, stop immediately after source selection. For non-US unsupported-primary-adapter fallback, the evidence review is the stop point after company-report cross-check; make the Yahoo-normalized source choice explicit and do not treat a generic approval as enough.
- If a tool returns `ok: false`, use `stockvaluation.explain_failure` and explain the failure plainly.
- If reference data is missing, stale, weak, or low confidence, say so in the report.
- For financial-sector companies, unsupported companies, or insufficient data, stop and explain the limitation. Do not produce a synthetic valuation.
- Keep MCP tools atomic. Do not use a hidden high-level valuation agent; `stockvaluation.researched_baseline` is the read-only researched source-policy baseline tool.
- Treat segment weighting as researched mechanical baseline construction, not as a discretionary researched override.
- Treat `marketImpliedExpectations`, `pricedInExpectations`, frontier, grid, and scenario data as report inputs, not autonomous model changes.
- Treat guided-refinement answers as `user_judgment` scenario inputs, not external evidence.
- Treat Scenario Book as the validated scenario artifact. The mechanical baseline is internal-only, market-implied diagnostics are diagnostic-only, and explicit scenario mode is distinct from guided user-refined mode.
- Keep `request_policy.mode = "autonomous_researched"` strict. Use `request_policy.mode = "user_refined_scenario"` only for bounded user-judgment scenario inputs.
- Codex and some other clients display MCP call arguments. Keep `stockvaluation.recalculate` arguments compact: send only contract-supported override fields plus the minimal metadata needed for validation. Do not place raw research logs, full source lists, full report-only evidence packets, hidden guided-question plans, raw `assumption_judgment`, raw Scenario Book JSON, raw audit packets, or long rationale text in MCP arguments.
- For autonomous researched recalculation, include only the minimal valid `evidence_packet` needed to validate requested governed changes: one source-family status per governed source family, one source-checked entry per governed evidence source, and the governed evidence items that directly support the requested override. Keep broader source quality, conflicts, data gaps, report-only evidence, and unused sources in the evidence review and report, not in MCP call arguments.
- Avoid duplicating the same material across `evidence_packet`, `evidence_used`, `rationale`, and `assumption_judgment`. If `evidence_packet` is present, `evidence_used` should be omitted or kept to short governed evidence references only.
- If `stockvaluation.recalculate` returns `UNSUPPORTED_OVERRIDES`, do not retry with a larger debug payload. Remove unsupported/report-only fields, keep only governed inputs, and retry once only when the remaining payload is valid.
- Do not create break-even, priced-in, sensitivity, terminal composition, or accounting-adjustment values when MCP/service output did not return them.
- Treat the first successful `stockvaluation.value_ticker` output as the mechanical baseline. If `baseline.baselineUseStatus` is not `validated_segment_weighted` or the baseline plausibility gate flags an optimistic assumption stack, do not call it the rational researched base.

## Report Rules

- Frame the report as educational use only and not financial advice.
- Avoid buy, sell, hold, target-price, and personalized recommendation language.
- Use `{baseDir}/references/report-template.md` as the controlling final report structure. Section order and required summaries come from the report template; narrative style is subordinate and cannot remove or reorder required sections.
- Render the final report with the report-template headings. Do not replace the template with a compressed memo, a paragraph that starts "Using stockvaluation.io...", a "Key assumptions" bullet list, a "Main caveats" bullet list, and a "Sources used" line.
- Separate market price, model intrinsic value, and assumptions. Do not turn model output into an instruction.
- Explain key drivers: growth, margins, reinvestment, cost of capital, terminal value, tax rate, and accounting adjustments.
- Include data-quality notes and service/version metadata when returned.
- Use clear uncertainty language when Yahoo Finance coverage or reference-data matching is weak.
- Make evidence review status and guided-refinement status visible: approved, caveated, corrected, bypassed by explicit quick/no-questions/automation/smoke-test request, or not run because of an unsupported/failed workflow.
- Do not print raw `assumption_judgment`, `valuation_audit_packet`, hidden guided question plan, or raw Scenario Book JSON by default.
- In guided refinement, make the user-refined scenario the main scenario when it exists. Keep the mechanical baseline internal by default; expose mechanical baseline details only when the user explicitly asks for audit/debug detail.
- Keep diagnostic scenarios diagnostic. Do not blend a user-refined scenario with a diagnostic no-segment, market-implied, or sensitivity run into a headline valuation range unless the user explicitly requested a range and the report labels each case under the template's scenario/diagnostic sections.
- Keep supported adjustments separate from supported explanations, explain-only topics, future-support gaps, unsupported-stop cases, and out-of-scope topics.
- Do not count "10-K found", "earnings release found", or other generic source presence as evidence. Evidence must name a valuation driver and the relevant fact.
- When the baseline is challenged, mention baseline quality and unsupported blockers in the main narrative, but put mechanical baseline value/detail only in explicit audit/debug output.

## References

- `{baseDir}/references/mcp-tools.md`
- `{baseDir}/references/financial-field-definitions.md`
- `{baseDir}/references/prospectus-mode.md`
- `{baseDir}/references/search-and-evidence.md`
- `{baseDir}/references/driver-specific-evidence.md`
- `{baseDir}/references/evidence-review-gate.md`
- `{baseDir}/references/baseline-plausibility.md`
- `{baseDir}/references/scenario-book.md`
- `{baseDir}/references/guided-valuation-refinement.md`
- `{baseDir}/references/segment-discovery.md`
- `{baseDir}/references/assumption-judgment.md`
- `{baseDir}/references/damodaran-method.md`
- `{baseDir}/references/damodaran-coverage-map.md`
- `{baseDir}/references/damodaran-source-map.md`
- `{baseDir}/references/growth-reinvestment-discipline.md`
- `{baseDir}/references/terminal-value-discipline.md`
- `{baseDir}/references/model-selection-and-lifecycle.md`
- `{baseDir}/references/rd-capitalization-decision.md`
- `{baseDir}/references/risk-currency-country.md`
- `{baseDir}/references/accounting-cleanup.md`
- `{baseDir}/references/options-leases-other-claims.md`
- `{baseDir}/references/segment-quality.md`
- `{baseDir}/references/special-company-stop-rules.md`
- `{baseDir}/references/narrative-report-style.md`
- `{baseDir}/references/report-template.md`
- `{baseDir}/references/no-advice-policy.md`
- `{baseDir}/references/assumption-checks.md`
- `{baseDir}/references/accounting-adjustments.md`
- `{baseDir}/references/troubleshooting.md`
