# Workflow: Gates, Guided Refinement, Prospectus Mode

The server enforces ordering (run state, gate refusals, anchored values, range output). This file keeps the judgment: what to show the user at each stop and how to record decisions.

## Evidence Review Gate

After research, segment discovery, and driver-specific evidence classification, stop and show a compact human review before any guided question or report. The gate is a human review of the evidence base, not a recommendation and not financial advice.

Show, in plain investor-readable prose and compact tables: company and ticker, core financial source and quality, sources checked with dates, driver-specific evidence, segment evidence and limitations, material recent context, data gaps, conflicts, and which items are supported model changes vs report-only vs unsupported. Do not show internal labels (`Source quality gate`, `Segment baseline`, `Important caveat`), mechanical baseline values, or raw status names.

Ask the user to approve, correct, add sources, or continue with caveats. Record the outcome on the next tracked call via `gate_records` (`approved` / `corrected` / `caveated`; bypasses need an explicit user request and reason). User corrections are not external evidence unless source-backed and processed through the evidence rules.

### Source-Quality Stops

- `sec_*_yahoo_fallback`: stop immediately after source selection. Say SEC primary source was expected but unavailable and Yahoo-normalized fallback is available; ask the user to continue with Yahoo-normalized fallback, retry the primary source, or stop. Do not run anything further first.
- `primary_adapter_not_supported_yahoo_normalized`: not an SEC failure. Say no supported deterministic primary-filing adapter covers this listing; run the company-report cross-check, then ask the user to continue after company-report cross-check, correct/add sources, or stop.
- Do not present a generic `approve` prompt as sufficient for either source-quality decision.

## Guided Refinement

Run guided refinement in every default flow after the evidence gate clears. Plan with `stockvaluation.plan_guided_questions` (pass the `run_id`; the server attaches anchor sets so choices A/B/C are the server-computed low/base/high values and the default is always the base anchor).

- The returned plan is the source of truth: question order, choice meanings, default, and model action. Simplify wording only; never downgrade a `user scenario override` choice or substitute hand-written questions.
- Ask one question at a time; batch mode only when explicitly requested. Ask every material question (hard cap 15, no forced minimum, no filler). If none are material, say so and continue.
- Each question card shows: question number and total, company-specific title, business tension, choices table with the default marked, "My analysis" with why the default was selected, evidence used, business impact, model impact, confidence, and reply options (`A`–`D`, `default`, `use defaults`).
- Send the planner only dated, cited, driver-specific evidence items (driver, summary/fact, source_url, source_date, confidence). If the plan reports dropped evidence or `planner_warnings`, retry once with complete metadata before asking the user.
- A question with `requires_user_value: true` has no computable anchor: ask the user for a specific number and pass it with `value_sources=user_input`. Never invent the number.
- After answers (or `use defaults`), call `stockvaluation.apply_guided_answers` with just the `run_id` and the answers — do not echo the plan back; the server uses its stored copy (`planSource: "run_state"`). This records which anchor or user value actually mapped per driver and clears the guided gate. Then run exactly one final deterministic call: `stockvaluation.recalculate` with `request_policy.mode = "user_refined_scenario"` (ticker) or `stockvaluation.value_prospectus` with `prospectusScenarioCandidate.scenario` (prospectus).
- If the user leaves a material driver unresolved, the server returns a `valuationRange`; report the range and the responsible drivers honestly instead of a point.
- If a visible card says "Question 1 of N" and the user accepts defaults, summarize all remaining default answers; never skip them silently.

Bypass paths (explicit quick/no-questions/automation/smoke-test requests only): record the bypass via `gate_records` with the matching reason, do not fabricate a user-refined scenario, and write the report from the evidence-constrained workflow.

## Prospectus Mode

Use for SEC EDGAR Archives HTML prospectus URLs (IPOs, offerings). Filing-first version of the same workflow; the model and gates are unchanged.

1. `stockvaluation.extract_prospectus` with the filing URL only (never raw HTML).
2. Stop at the extraction review. Show a compact review card: what was extracted (company, filing metadata, offering price and basis, share counts, core financials, raw segment candidate tables), what looks usable, what needs review, and a recommended action. Offer four numbered choices: 1 approve and continue, 2 correct the packet, 3 add sources, 4 stop. Map the number to the internal action; recommend stop/correct for empty or ambiguous packets. Approval is a modeling-input review, not financial advice.
3. After approval/correction call `stockvaluation.value_prospectus` with `review_reference` and `review_status=reviewed`; never rebuild the packet by hand.
4. Read the basis fields before showing any value. `clean_pro_forma_basis` + `clean_valuation_case` is clean. `pro_forma_cash_missing`: post-offering shares require pro-forma cash and net proceeds were not resolved. `gross_proceeds_estimate_only`: only gross proceeds could be inferred — not a clean basis. `challenged_valuation_case`, `dcf.valueVisibility = diagnostic_only`, or `challenged_baseline`: say no clean user-facing valuation was produced; do not show the diagnostic value before evidence review. If the user later continues with caveats or asks for detail, show `dcf.estimatedValuePerShare` only as a clearly labeled challenged diagnostic value. Fallback-default drivers (`prospectus_default_used`, `rd_capitalization_source_missing`, …) mean the DCF ran on defaults — ask for the missing source before treating it as clean.
5. Extraction review is not the evidence review gate and does not replace guided refinement. Continue into the normal flow.
6. Label `priceBasis = offering_price`, source class `primary_filing`, provider `sec-edgar-prospectus`. Never substitute Yahoo/yfinance data or a trading price; the offering price is a price basis, not a recommendation. SEC filing facts are primary; external news cannot override them.
7. Pass material segment candidates to the planner as compact structured rows (name, revenue amount or weight, reviewed mapping fields) — see `segments.md`. After `apply_guided_answers`, verify `prospectusScenarioCandidate.scenario` contains what the user accepted before the final valuation call.

## Scenario Discipline

Auto-recalculate once after `assumption_judgment`; one final user-refined call after guided refinement. Ask before running extra user-requested scenarios. Explicit user scenarios outside guided refinement use `request_policy.mode = "explicit_scenario"` and only contract-supported fields.
