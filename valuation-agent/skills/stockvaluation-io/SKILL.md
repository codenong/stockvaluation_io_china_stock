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
2. Run segment discovery using `{baseDir}/references/segment-discovery.md` before constructing the researched mechanical baseline. If company name, website, or industry context is unavailable, use `stockvaluation.value_ticker` only as a preflight company-context lookup and do not treat that first company-level output as the researched base.
3. Build and validate the segment package. When credible segment revenue weights exist, construct the segment-aware mechanical baseline through the governed recalculation path with only `segments` plus researched-baseline request policy metadata before any discretionary researched overrides. When no valid segment package exists, use `stockvaluation.value_ticker` as the single-industry fallback mechanical baseline.
4. If the baseline payload has `ok: false`, call `stockvaluation.explain_failure`, explain the classified failure plainly, and do not invent a valuation.
5. Extract the live baseline contract first: baseline quality, baseline use status, segment awareness, segment coverage, mapped industries, weighted baseline assumptions, baseline warnings, unsupported baseline drivers/adjustment fields, target operating margin source/status, AccountingAndClaims statuses, DCF, company, industry, country, currency, assumptions, growth anchor, warnings, and valuation output.
6. Build an evidence packet using `{baseDir}/references/search-and-evidence.md`. For full researched valuations, run source-heavy searches in fresh-context subagents when available and have them return compact evidence summaries only. Then classify driver-specific evidence with `{baseDir}/references/driver-specific-evidence.md`.
7. Unless the user explicitly requested quick valuation, no questions, skip questions, one-shot report, automation, or smoke-test, stop at the human evidence review gate in `{baseDir}/references/evidence-review-gate.md`. Show source quality, sources checked with dates, driver-specific evidence, segment evidence/limitations, latest material context, conflicts, data gaps, and supported/report-only/unsupported treatment. Require the user to approve, correct, add sources, or continue with caveats before continuing. User approval is not financial advice; user corrections are not external evidence unless source-backed and processed through evidence rules.
8. Run the baseline plausibility gate in `{baseDir}/references/baseline-plausibility.md` to distinguish the mechanical baseline, segment-aware mechanical baseline, evidence-constrained base, and market-implied diagnostics before judging assumptions.
9. Apply the method checks in `{baseDir}/references/damodaran-method.md`, `{baseDir}/references/damodaran-coverage-map.md`, `{baseDir}/references/damodaran-source-map.md`, and `{baseDir}/references/assumption-checks.md`.
10. Apply the focused decision guides that match the company and evidence: growth/reinvestment, terminal value, model/lifecycle, R&D, risk/currency/country, accounting cleanup, options/leases/claims, segment quality, and special-company stop rules.
11. Produce the strict `assumption_judgment` JSON block described in `{baseDir}/references/assumption-judgment.md`, using driver-specific evidence rather than generic source presence and incorporating baseline plausibility.
12. Auto-recalculate once with `stockvaluation.recalculate` using `request_policy.mode = "autonomous_researched"` when the baseline valuation succeeded and the governed evidence-constrained payload is supported. Do not hand-compute valuation math.
13. Unless the user explicitly requested quick valuation, no questions, skip questions, one-shot report, automation, or smoke-test, run guided refinement using `{baseDir}/references/guided-valuation-refinement.md`. Build a hidden guided question plan of company-specific bounded questions after the evidence review gate is cleared, baseline plausibility is checked, and the evidence-constrained base exists; the plan must be materiality-driven. Ask every material company-specific question up to a hard cap of 15 visible guided questions, with no forced minimum. If only one or two questions matter, ask only those. If none matter, explain and do not invent filler. Ask one question at a time by default. Do not ask a batch of 4-6 questions unless the user explicitly requests batch mode. Do not treat a plain "value COMPANY using stockvaluation.io" request as a one-shot path.
14. Accumulate answered choices into a distinct `user_judgment` package. User answers are user judgment, not evidence. Recalculate once, after guided refinement is complete, with `stockvaluation.recalculate` using `request_policy.mode = "user_refined_scenario"` and attach `user_judgment` as metadata. Keep unsupported or report-only answers out of the service payload.
15. For explicitly requested quick/no-questions/one-shot/automation/smoke-test paths, label the evidence review and guided-refinement bypasses, do not fabricate a user-refined scenario, and write the one-shot educational report after the evidence-constrained workflow when available.
16. Build and read the Scenario Book using `{baseDir}/references/scenario-book.md` and returned `structuredContent.scenarioBook` when present. Use it to separate the evidence-constrained base, user-refined scenario, explicit scenario, market-implied diagnostics, and internal mechanical baseline references.
17. Write the final educational report using `{baseDir}/references/report-template.md` as the canonical controlling structure. Use `{baseDir}/references/narrative-report-style.md` only as subordinate prose guidance, summarizing the judgment in prose and tables rather than printing raw JSON by default.
18. Apply `{baseDir}/references/no-advice-policy.md` before finalizing.

## Tool Rules

- Use the MCP tools documented in `{baseDir}/references/mcp-tools.md`.
- Treat MCP JSON as the source of truth for valuation output.
- Do not invent missing service fields, missing financial data, growth-anchor confidence, or scenario math.
- If a tool returns `ok: false`, use `stockvaluation.explain_failure` and explain the failure plainly.
- If reference data is missing, stale, weak, or low confidence, say so in the report.
- For financial-sector companies, unsupported companies, or insufficient data, stop and explain the limitation. Do not produce a synthetic valuation.
- Keep MCP tools atomic. Do not look for or request a high-level researched valuation tool.
- Treat segment weighting as researched mechanical baseline construction, not as a discretionary researched override.
- Treat `marketImpliedExpectations`, `pricedInExpectations`, frontier, grid, and scenario data as report inputs, not autonomous model changes.
- Treat guided-refinement answers as `user_judgment` scenario inputs, not external evidence.
- Treat Scenario Book as the validated scenario artifact. The mechanical baseline is internal-only, market-implied diagnostics are diagnostic-only, and explicit scenario mode is distinct from guided user-refined mode.
- Keep `request_policy.mode = "autonomous_researched"` strict. Use `request_policy.mode = "user_refined_scenario"` only for bounded user-judgment scenario inputs.
- Do not create break-even, priced-in, sensitivity, terminal composition, or accounting-adjustment values when MCP/service output did not return them.
- Treat the first successful `stockvaluation.value_ticker` output as the mechanical baseline. If `baseline.baselineUseStatus` is not `validated_segment_weighted` or the baseline plausibility gate flags an optimistic assumption stack, do not call it the rational researched base.

## Report Rules

- Frame the report as educational use only and not financial advice.
- Avoid buy, sell, hold, target-price, and personalized recommendation language.
- Use `{baseDir}/references/report-template.md` as the controlling final report structure. Section order and required summaries come from the report template; narrative style is subordinate and cannot remove or reorder required sections.
- Separate market price, model intrinsic value, and assumptions. Do not turn model output into an instruction.
- Explain key drivers: growth, margins, reinvestment, cost of capital, terminal value, tax rate, and accounting adjustments.
- Include data-quality notes and service/version metadata when returned.
- Use clear uncertainty language when Yahoo Finance coverage or reference-data matching is weak.
- Make evidence review status and guided-refinement status visible: approved, caveated, corrected, bypassed by explicit quick/no-questions/automation/smoke-test request, or not run because of an unsupported/failed workflow.
- Do not print raw `assumption_judgment`, `valuation_audit_packet`, hidden guided question plan, or raw Scenario Book JSON by default.
- In guided refinement, make the user-refined scenario the main scenario when it exists. Keep the mechanical baseline internal by default; expose mechanical baseline details only when the user explicitly asks for audit/debug detail.
- Keep supported adjustments separate from supported explanations, explain-only topics, future-support gaps, unsupported-stop cases, and out-of-scope topics.
- Do not count "10-K found", "earnings release found", or other generic source presence as evidence. Evidence must name a valuation driver and the relevant fact.
- When the baseline is challenged, mention baseline quality and unsupported blockers in the main narrative, but put mechanical baseline value/detail only in explicit audit/debug output.

## References

- `{baseDir}/references/mcp-tools.md`
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
