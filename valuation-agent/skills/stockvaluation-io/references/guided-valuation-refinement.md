# Guided Valuation Refinement

Use this reference for the default full researched valuation flow after the mechanical baseline, segment review, evidence packet, driver-specific evidence classification, and baseline plausibility gate are complete.

Guided refinement turns bounded user judgment into a clearly labeled `user_refined_scenario`. It does not replace the mechanical baseline or the autonomous evidence-constrained base. User answers are user judgment, not external evidence.

## When To Use

Default full researched valuation: use guided refinement.

Quick valuation, no-questions, automation, smoke-test, or explicit one-shot requests: bypass guided refinement and write the educational report from the mechanical baseline, evidence-constrained base, and report-only diagnostics.

Deep mode: ask up to 8 questions. Otherwise ask 4-6 questions. If fewer than 3 useful company-specific questions can be built, explain the limitation and continue without inventing generic questions.

## Allowed Action

Generate a bounded company-specific question package, capture the user's selected choices as `user_judgment`, and send only supported scenario assumptions to `stockvaluation.recalculate` with `request_policy.mode = "user_refined_scenario"`.

## Do Not

Do not ask generic checklist questions, do not treat user answers as evidence, do not fit to market price, and do not send unsupported answers to MCP. Do not use investment recommendation language such as buy, sell, hold, target price, or should invest. You may provide a recommended bounded scenario answer for each question, as a modeling default, when it is clearly labeled as educational scenario judgment rather than financial advice.

## Required Question Shape

Each question must include:

```json
{
  "id": "short_stable_id",
  "driver": "revenue_growth|operating_margin_next_year|target_operating_margin|margin_convergence_year|sales_to_capital|segment_revenue_growth|segment_operating_margin|segment_sales_to_capital|risk_wacc|terminal_value_mature_state|accounting_adjustments",
  "company_specific_rationale": "The company-specific business tension behind the question.",
  "business_tension": "Plain-language economic tradeoff.",
  "why_this_matters": "How the answer affects DCF value.",
  "baseline_assumption": "Mechanical or evidence-constrained assumption being tested.",
  "evidence_summary": "Brief driver-specific evidence or uncertainty summary.",
  "bounded_choices": [],
  "recommended_answer": {
    "choice_label": "A|B|C|D|none",
    "rationale": "Why this bounded scenario answer is the default recommendation for modeling.",
    "confidence": "low|medium|high",
    "model_action": "user scenario override|report-only user judgment|unsupported"
  },
  "model_action": "user scenario override|governed evidence-constrained override|report-only user judgment|unsupported",
  "mapping_notes": "How a selected choice maps to an override or why it stays report-only.",
  "unsupported_if_any": "Reason an answer cannot change the model.",
  "priority_reason": "Why this question earned one of the limited slots."
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

Reject generic checklist questions. A valid question must name the company, a company-specific business economy issue, the baseline assumption, a driver-specific evidence summary, bounded choices, a recommended bounded answer, and the model action.

## User-Facing Question Format

When asking the user, show the recommended answer directly after the choices:

```text
1. Revenue growth, years 2-5
   Company-specific tension...
   A: ...
   B: ...
   C: ...
   Recommended: B - evidence-constrained base; medium confidence.
```

The recommendation is the agent's modeling default, not financial advice. Let the user answer with terse selections such as `1B 2C 3B`, or with `recommended` / `default` to accept all recommended choices.

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

The final report must separate:

- Mechanical baseline: first deterministic MCP output.
- Evidence-constrained base: autonomous researched case after evidence gates and governed recalculation, or no-change/blocked status.
- User-refined scenario: deterministic recalculation from bounded user judgment.
- Market-implied diagnostics: report-only implied assumptions and priced-in diagnostics.

State plainly that user answers are user judgment, not evidence. Avoid buy, sell, hold, target-price, and personalized advice language.
