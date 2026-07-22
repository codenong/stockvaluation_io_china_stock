---
name: stockvaluation-io
description: Use whenever the prompt mentions stockvaluation.io, StockValuation.io, stockvaluation, the local valuation MCP, or asks to value a public company with the StockValuation workflow. Runs local MCP valuation with server-enforced gates and anchored defaults, stops for evidence review, asks guided valuation-refinement questions, and builds the report with the bundled report builder and deterministic prose linter.
version: 3.0.0-workflow-consistency
homepage: https://github.com/stockvaluation-io/stockvaluation_io
---

# StockValuation.io Agent Valuation

Use this skill whenever the prompt mentions `stockvaluation.io`, `stockvaluation`, the local valuation MCP, or asks you to value a public company, critique DCF assumptions, build scenarios, or troubleshoot the local service. The deterministic valuation math comes from local MCP tools; you orchestrate the workflow, gather evidence, and supply judgment. Educational use only; this is not financial advice (`{baseDir}/references/no-advice-policy.md`).

A plain request such as "value COMPANY using stockvaluation.io" is the default full researched valuation flow — not a quick valuation and not a one-shot report request. Never infer an evidence-review or guided-refinement bypass from ordinary phrasing; bypass only when the user explicitly says quick, no questions, skip questions, one-shot report, automation, or smoke-test, and record the bypass through `gate_records`.

## Server-Enforced Gates

The MCP server tracks each run. Always pass the `run_id` returned by `stockvaluation.researched_baseline`, `stockvaluation.value_ticker`, or `stockvaluation.extract_prospectus` to every downstream call. On tracked runs the server refuses out-of-order calls:

- Scenario-bearing valuation before the evidence-review gate is recorded → `GATE_NOT_CLEARED`.
- Guided-flow recalculation before answers are applied or an explicit bypass is recorded → `GATE_NOT_CLEARED`.
- A numeric driver value that is neither a server-computed anchor nor a recorded guided answer with `source=user_input` → `UNANCHORED_SCENARIO_VALUE` or `UNVERIFIED_USER_INPUT`. Never author scenario numbers yourself.
- While material drivers are unresolved, scenario calls return a low/high `valuationRange`; lead with that range and name the unresolved drivers. A point estimate exists only when every material driver is pinned.

## Default Workflow (ticker)

1. `stockvaluation.health`, then `stockvaluation.researched_baseline` (keep `stockvaluation.value_ticker` mechanical). Keep the returned `run_id`.
2. Handle `sourceQualityGate` stops per `{baseDir}/references/workflow.md`.
3. Run segment discovery (`{baseDir}/references/segments.md`) before treating anything as the researched mechanical baseline; use a segment-aware mechanical baseline when a validated package exists.
4. Build the evidence packet with research subagents and classify driver-specific evidence (`{baseDir}/references/evidence-and-judgment.md`).
5. Stop at the evidence review gate (`{baseDir}/references/workflow.md`); record the outcome via `gate_records`.
6. Run baseline plausibility and the method checks (`{baseDir}/references/valuation-method.md`), produce `assumption_judgment`, and auto-recalculate once via `stockvaluation.recalculate` with `request_policy.mode = "autonomous_researched"` when a governed change is supported. Do not hand-compute valuation math.
7. Run guided refinement: `stockvaluation.plan_guided_questions` with the `run_id` and optional non-numeric `framing_forks` (the server validates exact evidence references and attaches anchored low/base/high choices), ask one question at a time, then `stockvaluation.apply_guided_answers` and one final recalculation with `request_policy.mode = "user_refined_scenario"`. See `{baseDir}/references/workflow.md`.
8. Build the report with `{baseDir}/scripts/build_report.py` per `{baseDir}/references/report.md`; the prose linter runs inside it and the generated `index.html` opens automatically unless disabled with `--no-open` or `STOCKVALUATION_OPEN_REPORT=0`. Return the clickable `index.html` link.

## Prospectus Workflow

For a SEC EDGAR HTML prospectus URL: `stockvaluation.extract_prospectus`, stop at the extraction review card, then `stockvaluation.value_prospectus` with `review_reference` and `review_status=reviewed` only after user review. Continue into the normal evidence review and guided refinement; the final scenario call carries `prospectusScenarioCandidate.scenario`. Details and basis-status rules: `{baseDir}/references/workflow.md`.

## Judgment Rules

- Treat MCP JSON as the source of truth; never invent missing service fields, financial data, or scenario math.
- Evidence must name a driver and a fact; generic source presence ("10-K found") is not evidence. User answers and approvals are user judgment, not evidence.
- Market-implied and priced-in data are report-only diagnostics, never evidence or autonomous changes.
- Financial firms, private companies, and insufficient-data cases stop cleanly (`{baseDir}/references/valuation-method.md`); use `stockvaluation.explain_failure` and do not invent a valuation.
- Accounting topics follow `{baseDir}/references/accounting-and-claims.md`: explain returned values; apply R&D capitalization only through the governed source-backed R&D path.
- Keep MCP arguments compact (`{baseDir}/references/mcp-tools.md`).

## References

- `{baseDir}/references/mcp-tools.md` — tool reference, run tracking, anchors, failure recovery
- `{baseDir}/references/workflow.md` — gates, guided refinement, prospectus mode
- `{baseDir}/references/evidence-and-judgment.md` — evidence rules, assumption judgment, plausibility
- `{baseDir}/references/valuation-method.md` — method checks, coverage boundary, stop rules
- `{baseDir}/references/segments.md` — segment discovery and quality
- `{baseDir}/references/accounting-and-claims.md` — accounting statuses and claims
- `{baseDir}/references/report.md` — report builder, prose linter, HTML artifact
- `{baseDir}/references/no-advice-policy.md` — policy (verbatim, controlling)
