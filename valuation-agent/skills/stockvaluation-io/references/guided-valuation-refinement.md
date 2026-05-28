# Guided Valuation Refinement

Use this reference for the default full researched valuation flow after the mechanical baseline, segment review, evidence packet, driver-specific evidence classification, assumption judgment, and baseline plausibility gate are complete.

Guided refinement turns bounded user judgment into a clearly labeled `user_refined_scenario`. It does not replace the mechanical baseline or the autonomous evidence-constrained base. User answers are user judgment, not external evidence.

## When To Use

Default full researched valuation: use guided refinement.

Quick valuation, no-questions, automation, smoke-test, skip-questions, or explicit one-shot requests: bypass guided refinement and write the educational report from the evidence-constrained workflow and report-only diagnostics.

Default interactive mode: build a hidden guided question plan, then ask one question at a time. Do not ask a batch of 4-6 questions unless the user explicitly requests batch mode.

Deep mode: the hidden guided question plan may contain at most 8 questions. Otherwise keep the plan concise and prioritize the most company-specific drivers. If fewer than 3 useful company-specific questions can be built, explain the limitation and continue without inventing generic questions.

## Allowed Action

Generate a hidden guided question plan, ask one question at a time, capture selected choices as `user_judgment`, and run one final user-refined recalculation after the dialogue is complete. Send only supported mapped assumptions to `stockvaluation.recalculate` with `request_policy.mode = "user_refined_scenario"`.

## Do Not

Do not ask generic checklist questions, do not treat user answers as evidence, do not fit to market price, and do not send unsupported answers to MCP. Do not use investment recommendation language such as buy, sell, hold, target price, or should invest. You may provide a recommended bounded scenario answer as a modeling default when it is clearly labeled as educational scenario judgment and not financial advice.

Do not print the hidden guided question plan JSON by default. Show exact model mapping only when the user asks for audit/debug detail.

## Hidden Guided Question Plan

Before asking the user anything, create an internal plan from the company evidence, baseline diagnostics, evidence-constrained base, and market-implied report-only diagnostics. The plan is hidden by default and must be auditable when the user asks.

```json
{
  "plan_id": "ticker_guided_refinement",
  "company": "Company name",
  "ticker": "TICKER",
  "source_type": "guided_question_plan",
  "question_order": ["growth_durability", "margin_path"],
  "questions": [
    {
      "id": "short_stable_id",
      "driver": "revenue_growth|operating_margin_next_year|target_operating_margin|margin_convergence_year|sales_to_capital|segment_revenue_growth|segment_operating_margin|segment_sales_to_capital|risk_wacc|terminal_value_mature_state|accounting_adjustments",
      "status": "supported|report-only|unsupported",
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

Ask only the next unanswered question. The visible question should be compact and should not expose exact override JSON unless the user asks for audit/debug detail.

```text
Question 2 of 4 - Azure growth durability

Microsoft's cloud segment is still growing faster than the company average, but the model has to decide how quickly that advantage fades.

A. Fade toward the company baseline
B. Keep a modest cloud premium for years 2-5
C. Keep a larger cloud premium for years 2-5

My analysis: B is my modeling default, not financial advice.
Why this default: recent segment and earnings evidence supports a premium, but not an indefinite one.
Evidence used: FY annual report segment revenue mix and latest earnings cloud growth commentary.
Business impact: this assumes cloud remains the main growth engine while larger segments dilute total growth.
Model impact: maps to a bounded revenue-growth scenario if selected.
Confidence: medium

Reply with A, B, C, "default" for this question, "use defaults" for all remaining questions, or a short note.
```

Every user-facing question must include "My analysis" or equivalent modeling-default language, why this default was selected, evidence used, business impact, model impact, and confidence.

## Answer Handling

The user may answer with a choice letter, a short explanation, `default` for the current question, or `use defaults` to accept all remaining guided defaults. If the user asks for audit/debug detail, show the hidden model mapping for the relevant question.

After each answer, store it and ask the next unanswered question. Do not recalculate after each answer. Perform one final user-refined recalculation after all questions are answered or defaults are accepted.

## User Judgment Package

After the user answers, create a `user_judgment` package distinct from autonomous `assumption_judgment`:

```json
{
  "source_type": "user_judgment",
  "scenario_label": "user-refined scenario",
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
  "unsupported_assumptions": {},
  "not_evidence_statement": "User answers define a scenario; they are not independent evidence."
}
```

Send only supported mapped assumptions to `stockvaluation.recalculate` with `request_policy.mode = "user_refined_scenario"` and include the `user_judgment` package as metadata. Do not send unsupported or report-only answers.

## Supported User Scenario Fields

User-refined or explicit scenarios may map directly to:

- `revenue_growth`
- `operating_margin_next_year`
- `operating_margin` or `target_operating_margin`
- `margin_convergence_year`
- `sales_to_capital`
- `sales_to_capital_years_1_to_5`
- `sales_to_capital_years_6_to_10`
- `segments`
- `sector_overrides` for sector-level revenue growth, operating margin, and sales-to-capital

`margin_convergence_year` must be a finite projection year from 1 to 10. Sales-to-capital inputs must be finite positive multiples from 0.05x to 20x.

Autonomous evidence-constrained recalculation remains stricter. Do not use user-refined scenario support to loosen `autonomous_researched` mode.

## Report-Only Or Unsupported Topics

Market-implied diagnostics are report-only and never evidence. Do not ask what value the user wants, do not fit to market price, and do not send market price as an override.

WACC, terminal growth, tax, growth pattern, accounting adjustments, R&D capitalization, leases, options, NOLs, cash, debt, share count, and direct valuation outputs must not be autonomous researched overrides. If the user explicitly requests a scenario field that the MCP contract supports, label it as explicit scenario judgment. Terminal growth must stay within mature-economy and risk-free-rate constraints; invalid values must be rejected rather than capped.

Never accept fair value, target price, equity value, terminal value, upside/downside, market-price calibration, or other direct valuation outputs as inputs.

## Report Requirements

The final report must make the user-refined scenario the main scenario when guided refinement was completed. State plainly that user answers are user judgment, not evidence. Avoid buy, sell, hold, target-price, and personalized advice language.

The mechanical baseline is internal scaffolding by default. Keep it available only in explicit audit/debug detail, and do not present it as a primary user-facing valuation case.

The final report must separate:

- User-refined scenario: deterministic recalculation from bounded user judgment.
- Evidence-constrained base: autonomous researched case after driver-specific evidence, plausibility gate, and governed recalculation if supported.
- Market-implied diagnostics: report-only implied assumptions and priced-in diagnostics. These are not evidence and not autonomous model changes.
- Mechanical baseline: first successful deterministic MCP valuation, visible only in explicit audit/debug detail by default.
