# Guided Valuation Refinement

Use this reference for the default full researched valuation flow after the mechanical baseline, segment review, evidence packet, driver-specific evidence classification, evidence review gate, assumption judgment, and baseline plausibility gate are complete.

Guided refinement turns bounded user judgment into a clearly labeled `user_refined_scenario`. It does not replace the mechanical baseline or the autonomous evidence-constrained base. User answers are user judgment, not external evidence.

## When To Use

Default full researched valuation: use guided refinement.

Quick valuation, no-questions, automation, smoke-test, skip-questions, or explicit one-shot requests: bypass guided refinement, label the bypass, do not fabricate a user-refined scenario, and write the educational report from the evidence-constrained workflow and report-only diagnostics.

Default interactive mode: build a hidden guided question plan only after the evidence review gate is cleared, then ask one question at a time. Do not ask a batch of 4-6 questions unless the user explicitly requests batch mode. Batch mode only when explicitly requested.

Materiality-driven guided refinement: ask every material company-specific question the hidden plan identifies, subject to a hard cap of 15 visible guided questions. There is no forced minimum. If only one or two useful company-specific questions matter, ask only those. If no material company-specific questions exist, explain why and continue without inventing filler questions. Deep mode may broaden the materiality scan, but the same hard cap of 15 visible guided questions applies.

Prioritize questions by valuation materiality, evidence strength, uncertainty, model impact, and company-specificity. Do not ask generic checklist questions, do not ask what value the user wants, and do not fit assumptions to market price.

## Allowed Action

Generate a hidden materiality-driven guided question plan, ask every material company-specific question up to the cap, ask one question at a time, capture selected choices as `user_judgment`, and run one final user-refined recalculation after the dialogue is complete. Use `stockvaluation.plan_guided_questions` when available to build the plan from compact baseline, evidence, plausibility, segment, and diagnostic context. The planning tool does not compute valuation math. Use `stockvaluation.apply_guided_answers` when available after the user answers or accepts defaults, so selected choices are mapped from the plan rather than rebuilt by hand. For ticker workflows, send only supported mapped assumptions to `stockvaluation.recalculate` with `request_policy.mode = "user_refined_scenario"`. For prospectus workflows, send supported mapped assumptions through `stockvaluation.value_prospectus.scenario` using the reviewed packet.

## Do Not

Do not ask generic checklist questions, do not invent filler questions, do not use a preset question count, do not treat user answers as evidence, do not fit to market price, and do not send unsupported answers to MCP. Do not use investment recommendation language such as buy, sell, hold, target price, or should invest. You may provide a recommended bounded scenario answer as a modeling default when it is clearly labeled as educational scenario judgment and not financial advice.

Do not print the hidden guided question plan JSON by default. Show exact model mapping only when the user asks for audit/debug detail.

Do not hand-write replacement questions when `stockvaluation.plan_guided_questions` returns visible questions. The returned `questions` array is the source of truth for question order, choice meanings, default choice, `model_action`, and supported override mapping. The agent may simplify prose for readability, but it must not downgrade a `user scenario override` to report-only text or ask a different question that loses the mapping.

## Story-To-Driver Planner Tool

When available, call `stockvaluation.plan_guided_questions` after evidence review and baseline plausibility. The tool is read-only. It ranks candidate questions by materiality and labels each question as `supported`, `candidate-required`, `report-only`, or `unsupported`.

The planner input should stay compact:

- company, ticker, and workflow type,
- baseline assumptions,
- baseline plausibility,
- compact driver-specific evidence,
- segment evidence,
- market-implied diagnostics,
- whether prospectus recalculation is supported.

For prospectus segment evidence, pass each material segment in the planner `segments` array with `name`, either `revenue_weight`/`revenueShare` or `revenue_amount`/`revenue_2025`, and any reviewed `sector_key`, `mapped_industry`, or `candidate_mapping`. If revenue amounts are disclosed but weights are not, pass the amounts. The planner can build `prospectusScenarioCandidate.scenario.segments` from those compact rows after the user accepts the segment question. Do not pass only a prose note that "segment mapping is missing"; that makes the segment question report-only.

Every compact evidence item sent to the planner must include:

```json
{
  "driver": "revenue_growth|operating_margin|reinvestment_sales_to_capital|capital_claims|business_definition",
  "evidence_summary": "Driver-specific fact or data gap. The key `fact` is also accepted.",
  "source_url": "https://...",
  "source_date": "YYYY-MM-DD",
  "confidence": "medium|high"
}
```

Do not pass undated or uncited evidence to the planner. For SEC prospectus facts, repeat the SEC filing URL and filing date on each evidence item. The planner accepts common aliases such as `growth`, `margin`, `reinvestment`, `cash_share_basis`, and `segments`, but canonical driver names are preferred.

After calling the planner, inspect `guidedQuestionPlan.planner_warnings` and `guidedQuestionPlan.evidence_input_quality`. If any evidence was dropped, do not ask the truncated question set yet. Retry once with complete `source_url`, `source_date`, and driver-specific text from the evidence review. If evidence is still dropped, explain plainly why fewer questions are being asked.

Do not pass raw filing text, broad research logs, raw Scenario Book JSON, raw audit packets, or full hidden plans into the planner. Do not treat the planner output as evidence or valuation math.

When the returned `scenario_range.status` is `recommended`, the workflow has supported deterministic inputs. Do not end with a report-only final report until the selected/default mapped case or requested range has been sent to the deterministic service.

When `scenario_range.status = candidate_values_required`, the planner found material questions for governed service fields but did not receive numeric or structured `override_candidate` values. Do not treat those questions as harmless report-only defaults. Retry the planner once with source-backed candidate values for each listed `candidate_requirements.required_field`; if you cannot derive bounded candidates from cited evidence, ask the user the actual story-to-number question before final valuation.

## Hidden Guided Question Plan

Before asking the user anything, create an internal plan from the company evidence, baseline diagnostics, evidence-constrained base, and market-implied report-only diagnostics. The plan is hidden by default and must be auditable when the user asks.

```json
{
  "plan_id": "ticker_guided_refinement",
  "company": "Company name",
  "ticker": "TICKER",
  "source_type": "guided_question_plan",
  "planning_rule": "materiality_driven_cap_15_no_minimum",
  "planned_visible_question_count": 2,
  "question_count_rationale": "Ask every material company-specific question identified, capped at 15, with no filler.",
  "question_order": ["growth_durability", "margin_path"],
  "evidence_input_quality": {
    "received_evidence_item_count": 3,
    "usable_evidence_item_count": 3,
    "dropped_evidence_item_count": 0,
    "dropped_evidence_items": [],
    "planner_warnings": []
  },
  "planner_warnings": [],
  "questions": [
    {
      "id": "short_stable_id",
      "driver": "revenue_growth|operating_margin_next_year|target_operating_margin|margin_convergence_year|sales_to_capital|segment_revenue_growth|segment_operating_margin|segment_sales_to_capital|risk_wacc|terminal_value_mature_state|accounting_adjustments",
      "status": "supported|candidate-required|report-only|unsupported",
      "company_specific_rationale": "The company-specific business tension behind the question.",
      "business_tension": "Plain-language economic tradeoff.",
      "baseline_assumption": "Mechanical or evidence-constrained assumption being tested.",
      "evidence_basis": "latest earnings|filing|segment evidence|latest news|baseline diagnostics|data gap",
      "evidence_used": [
        {
          "claim": "Driver-specific fact, not generic source presence.",
          "source_title": "string",
          "source_url": "string",
          "source_date": "YYYY-MM-DD or unknown",
          "evidence_type": "filing|earnings|latest_news|segment|macro|data_gap",
          "driver": "string",
          "confidence": "low|medium|high"
        }
      ],
      "evidence_summary": "Brief driver-specific evidence or uncertainty summary.",
      "default_answer": {
        "choice_label": "A|B|C|D|none",
        "why_default_selected": "Why this bounded scenario answer is the modeling default.",
        "evidence_used": "Short evidence summary or explicit data gap.",
        "business_impact": "How the default changes the business story.",
        "model_impact": "Which DCF lever changes, or why it stays report-only.",
        "confidence": "low|medium|high"
      },
      "recommended_answer": {
        "choice_label": "A|B|C|D|none",
        "rationale": "Same modeling default in legacy-compatible form.",
        "confidence": "low|medium|high",
        "model_action": "user scenario override|report-only user judgment|unsupported"
      },
      "bounded_choices": [],
      "hidden_model_mapping": {
        "supported_override_field": "supported MCP field or null",
        "candidate_value": null,
        "send_to_mcp_by_default": false
      },
      "model_action": "user scenario override|report-only user judgment|unsupported",
      "mapping_notes": "How a selected choice maps to an override or why it stays report-only.",
      "unsupported_if_any": "Reason an answer cannot change the model.",
      "priority_reason": "Why this question earned one of the limited slots."
    }
  ],
  "not_evidence_statement": "User answers define a scenario; they are not independent evidence."
}
```

Each bounded choice must include:

```json
{
  "label": "A",
  "story": "Narrative-first answer choice.",
  "assumption_effect": "Direction or bounded range.",
  "override_candidate": {
    "field": "supported MCP field or null",
    "value": null
  },
  "model_action": "user scenario override|report-only user judgment|unsupported",
  "confidence": "low|medium|high",
  "report_label": "Short label for the final report"
}
```

Reject generic checklist questions. A valid question must name the company, a company-specific business-economics issue, the baseline or evidence-constrained assumption being tested, driver-specific evidence or an explicit data gap, bounded choices, the modeling default, hidden model mapping, confidence, and the model action.

Generic source presence is insufficient for a recommended default. "10-K found", "earnings release found", or "news searched" is not evidence unless the question names the valuation driver and the relevant fact.

## User-Facing Question Format

Ask only the next unanswered question. The visible question should be a Markdown question card. It must show the question number and total count, company-specific title, business tension, choices table, default marker, My analysis, Why this default, Evidence used, Business impact, Model impact, Confidence, and reply options. Do not expose exact override JSON unless the user asks for audit/debug detail.

```text
### Guided valuation refinement: Question 2 of 9 - Azure growth durability

Microsoft's cloud segment is still growing faster than the company average, but the model has to decide how quickly that advantage fades.

| Choice | Scenario | Assumption effect | Model action | Confidence |
| --- | --- | --- | --- | --- |
| A | Fade toward the company baseline | Lower years 2-5 growth premium | User scenario override | Medium |
| **B (default)** | Keep a modest cloud premium | Moderate years 2-5 growth premium | User scenario override | Medium |
| C | Keep a larger cloud premium | Higher years 2-5 growth premium | User scenario override | Low |

**My analysis:** B is my modeling default, not financial advice.

**Why this default:** Recent segment and earnings evidence supports a premium, but not an indefinite one.

**Evidence used:** FY annual report segment revenue mix and latest earnings cloud growth commentary.

**Business impact:** This assumes cloud remains the main growth engine while larger segments dilute total growth.

**Model impact:** Maps to a bounded revenue-growth scenario if selected.

**Confidence:** Medium.

**Reply options:** Reply with `A`, `B`, `C`, `default` for this question, `use defaults` for all remaining questions, or a short note.
```

Every user-facing question must include "My analysis" or equivalent modeling-default language, why this default was selected, evidence used, business impact, model impact, confidence, and reply options. The default marker must be visible in the choices table.

## Answer Handling

The user may answer with a choice letter, a short explanation, `default` for the current question, or `use defaults` to accept all remaining guided defaults. If the user asks for audit/debug detail, show the hidden model mapping for the relevant question.

After each answer, store it and ask the next unanswered question. Do not recalculate after each answer. After all questions are answered or defaults are accepted, call `stockvaluation.apply_guided_answers` when available with the hidden plan plus selected answers. If the user says `use defaults`, pass `use_defaults = true` so all remaining defaults are recorded.

Perform one final user-refined recalculation only when at least one answer maps to supported recalculation input. For ticker workflows, use `tickerOverridesCandidate.overrides` from `stockvaluation.apply_guided_answers` as the basis for `stockvaluation.recalculate`. For prospectus workflows, use `prospectusScenarioCandidate.scenario` as the basis for a second `stockvaluation.value_prospectus` call with the reviewed packet. If the prospectus also needs segment modeling and a reviewed explicit `scenario.segments` package exists, merge it into that scenario before calling the service.

If `stockvaluation.apply_guided_answers` returns `userJudgment.scenario_status = candidate_values_required`, do not write a final valuation report yet. Either retry `stockvaluation.plan_guided_questions` with source-backed `override_candidate` values for the listed `candidate_requirements`, or ask the user the missing numeric assumptions. If the user explicitly leaves them unresolved, report that no user-refined scenario was calculated.

The Scenario Book must then contain exactly one user-refined scenario for the completed guided path only when supported mapped assumptions exist and deterministic recalculation runs. If the user says `use defaults`, record the defaults as user judgment, not evidence. If all remaining defaults are report-only or unsupported, summarize them in the report and do not fabricate a user-refined scenario.

If the current workflow has no supported recalculation path, keep answers as report-only guided defaults. Prospectus mode has a deterministic explicit scenario path through `stockvaluation.value_prospectus.scenario`; use it whenever `stockvaluation.apply_guided_answers` returns a supported `prospectusScenarioCandidate`. Do not call report-only prospectus guided answers a user-refined scenario. If the visible question count says "Question 1 of 3", all remaining default answers must be summarized when `use defaults` is accepted; do not skip hidden questions silently.

## User Judgment Package

After the user answers, create a `user_judgment` package distinct from autonomous `assumption_judgment`:

```json
{
  "source_type": "user_judgment",
  "scenario_label": "user-refined scenario|report-only guided defaults|report-only guided judgment",
  "scenario_status": "recalculation_ready|candidate_values_required|report_only_or_unsupported",
  "answers": [
    {
      "question_id": "string",
      "selected_choice": "A|B|C|D|default|skipped",
      "recommended_choice": "A|B|C|D|none",
      "used_recommended_choice": true,
      "user_note": "string|null",
      "mapped_driver": "string",
      "model_action": "user scenario override|report-only user judgment|unsupported",
      "requested_override": {},
      "unsupported_or_report_only_reason": "string|null",
      "confidence": "low|medium|high"
    }
  ],
  "requested_assumptions": {},
  "mapped_assumptions": {},
  "report_only_assumptions": {},
  "unsupported_assumptions": {},
  "candidate_requirements": [],
  "not_evidence_statement": "User answers define a scenario; they are not independent evidence."
}
```

Send only supported mapped assumptions to `stockvaluation.recalculate` with `request_policy.mode = "user_refined_scenario"` and include the `user_judgment` package as metadata. Do not send unsupported or report-only answers.

## Supported User Scenario Fields

User-refined or explicit scenarios may map directly to:

- `net_proceeds` for prospectus workflows
- `revenue_growth`
- `operating_margin_next_year`
- `operating_margin` or `target_operating_margin`
- `margin_convergence_year`
- `sales_to_capital`
- `sales_to_capital_years_1_to_5`
- `sales_to_capital_years_6_to_10`
- `segments`
- `sector_overrides` for sector-level revenue growth, operating margin, and sales-to-capital

`margin_convergence_year` must be a finite projection year from 1 to 10. Sales-to-capital inputs must be finite positive multiples from 0.05x to 20x. Scalar fields such as `net_proceeds`, growth, margin, and sales-to-capital must be numbers, not nested objects.

Autonomous evidence-constrained recalculation remains stricter. Do not use user-refined scenario support to loosen `autonomous_researched` mode.

## Report-Only Or Unsupported Topics

Market-implied diagnostics are report-only and never evidence. Do not ask what value the user wants, do not fit to market price, and do not send market price as an override.

WACC, terminal growth, tax, growth pattern, accounting adjustments, R&D capitalization, leases, options, NOLs, cash, debt, share count, and direct valuation outputs must not be autonomous researched overrides. If the user explicitly requests a scenario field that the MCP contract supports, label it as explicit scenario judgment. Terminal growth must stay within mature-economy and risk-free-rate constraints; invalid values must be rejected rather than capped.

Never accept fair value, target price, equity value, terminal value, upside/downside, market-price calibration, or other direct valuation outputs as inputs.

## Report Requirements

The final report must make the user-refined scenario the main scenario when guided refinement was completed. State plainly that user answers are user judgment, not evidence. Avoid buy, sell, hold, target-price, and personalized advice language.

The mechanical baseline is internal scaffolding by default. Keep it available only in explicit audit/debug detail, and do not present it as a primary user-facing valuation case.

If guided refinement was bypassed for quick valuation, no questions, automation, smoke-test, skip-questions, or a one-shot report, the Scenario Book must record guided-refinement bypass and must not fabricate a user-refined scenario.

The final report must separate:

- User-refined scenario: deterministic recalculation from bounded user judgment.
- Evidence-constrained base: autonomous researched case after driver-specific evidence, plausibility gate, and governed recalculation if supported.
- Market-implied diagnostics: report-only implied assumptions and priced-in diagnostics. These are not evidence and not autonomous model changes.
- Mechanical baseline: first successful deterministic MCP valuation, visible only in explicit audit/debug detail by default.
