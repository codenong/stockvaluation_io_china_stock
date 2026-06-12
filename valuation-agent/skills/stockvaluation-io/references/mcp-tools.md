# MCP Tools

All StockValuation tools return full MCP `structuredContent` JSON; read it first — the visible text block is intentionally compact and is not the full payload. Treat MCP JSON as the source of truth; do not invent missing fields. Input/output schemas come from `tools/list`; this file documents roles and judgment, not payload shapes.

## Workflow Run Tracking And Gate Enforcement

`stockvaluation.extract_prospectus`, `stockvaluation.researched_baseline`, and `stockvaluation.value_ticker` issue a `run_id` and `workflow_state` on success. Pass that `run_id` to `stockvaluation.value_prospectus`, `stockvaluation.plan_guided_questions`, `stockvaluation.apply_guided_answers`, and `stockvaluation.recalculate` — always, in the default flow.

- Tracked runs enforce the `evidence_review` and `guided_refinement` gates; run state persists on disk for 24 hours across MCP processes.
- Record gate outcomes with `gate_records`: `{"gate": "evidence_review", "outcome": "approved" | "corrected" | "caveated" | "bypassed", "reason": "quick" | "no_questions" | "automation" | "smoke_test"}` (reason required for bypasses). Record outcomes only after the user actually decided; bypasses are recorded, never inferred. `apply_guided_answers` with a `run_id` records `guided_refinement: applied` automatically.
- Scenario-bearing `value_prospectus`/`recalculate` before the evidence gate, or guided-flow `recalculate` (overrides containing `user_judgment`/`guided_refinement`) before answers are applied, is refused with `{"ok": false, "error": {"code": "GATE_NOT_CLEARED"}, "gate": "..."}`.
- Every tracked response carries `workflow_state` (`gates`, `gates_passed`, `gates_pending`). Untracked calls behave as before with `gate_enforcement: "untracked"`. Unknown/expired run ids return `UNKNOWN_RUN_ID`; invalid records return `INVALID_GATE_RECORD`.

## Deterministic Driver Anchors And Range Output

On tracked runs the server computes per-driver anchor sets `{driver, field, unit, anchors: {low, base, high}}` from deterministic inputs only (filing history, offering terms, service baseline), each anchor with a `provenance` string. The model never authors scenario numbers.

- `plan_guided_questions` with a `run_id` attaches anchors to every material numeric question: choices A/B/C carry low/base/high with `anchor_provenance`; the default is the base anchor. `requires_user_value: true` questions have no computable anchor — ask the user for a specific number.
- On tracked prospectus runs the server sets `prospectus_recalculate_supported` automatically.
- `apply_guided_answers` returns `guidedAnswerRecord` (per driver: value and `anchor:<label>` or `user_input`).
- A numeric driver value must be a recorded anchor, or declared in `value_sources` as `user_input`, or absent — otherwise `{"ok": false, "error": {"code": "UNANCHORED_SCENARIO_VALUE"}, "driver": "<field>"}`.
- While material anchored drivers are unresolved, scenario-bearing calls return `valuationRange` (`unresolved_drivers`, `spread_drivers`, `low`/`high` with `value_per_share`, `value_spread`) instead of a point estimate. Lead with the range and name the drivers; a point appears only when every material driver is pinned.

## Tool Roles

- `stockvaluation.health` — service, MCP, policy, and installed-skill metadata (version and sync status from the install manifest).
- `stockvaluation.value_ticker` — mechanical baseline only (preflight and mechanical diagnostics). Do not describe it as SEC primary-source backed unless provenance says `primary_filing`; `sec_http_error_yahoo_fallback` and other `sec_*_yahoo_fallback` statuses mean Yahoo-normalized fallback.
- `stockvaluation.researched_baseline` — the default full researched baseline entrypoint with source policy. Read `sourceQualityGate` immediately; `requires_user_decision` (SEC fallback or `primary_adapter_not_supported_yahoo_normalized`) is a stop point per `workflow.md`. Treat the first successful baseline as mechanical scaffolding until plausibility passes.
- `stockvaluation.propose_segment_mappings` — Java-backed deterministic segment mapping proposals for supplied segment rows before a human gate. Use it after sourced segment rows are found and before asking the user to approve/correct mappings. It returns `segmentReview` with scores, rationales, row roles, warnings, unmapped rows, coverage, and allowed actions.
- `stockvaluation.extract_prospectus` — SEC EDGAR Archives HTML URLs only (schema-enforced; never raw HTML). Returns a review-required packet (`prospectus_extraction_review_required`), `reviewReference`, and provenance (`primary_filing`, `sec-edgar-prospectus`).
- `stockvaluation.value_prospectus` — requires a reviewed packet: pass `review_reference` + `review_status=reviewed` (server refuses otherwise). Optional `scenario` for explicit/guided cases with `offering_price` basis. Basis statuses to read before showing any value: `valuationBasisStatus` (`clean_pro_forma_basis`, `pro_forma_cash_missing`, `gross_proceeds_estimate_only`) and `valuationCaseStatus` (`clean_valuation_case`, `challenged_valuation_case`). Educational output only — not financial advice.
- `stockvaluation.plan_guided_questions` — read-only materiality-ranked question planner; call only after evidence review and baseline plausibility; it plans questions, it is not a valuation engine.
- `stockvaluation.apply_guided_answers` — maps answers from the plan into `userJudgment`, `tickerOverridesCandidate`, and `prospectusScenarioCandidate`. On tracked runs the server uses its stored copy of the plan (`planSource: "run_state"`): pass just `run_id` + answers/`use_defaults` and never echo or rebuild the plan. `guidedAnswerRecord` lists only answers that actually mapped into the scenario.
- `stockvaluation.recalculate` — governed scenario overrides. Supported keys: `revenue_growth`, `operating_margin_next_year`, `operating_margin`/`target_operating_margin`, `margin_convergence_year` (1–10), `sales_to_capital` and the years_1_to_5 / years_6_to_10 variants (0.05–20), `wacc`, `terminal_growth`, `tax_rate`, `growth_pattern_override`, `segments`, `sector_overrides` (`sector_key`/`yahoo_industry_key` required), `segment_economics`, `rd_capitalization` (governed explicit scenario only), `leases` (report-only status), plus metadata (`request_policy`, `rationale`, `evidence_packet`, `evidence_used`, `user_judgment`, `baseline_plausibility`, `assumption_judgment`, `guided_refinement`). Keep `request_policy.mode = "autonomous_researched"` strict; `user_refined_scenario` is only for bounded guided judgment.
- `stockvaluation.get_assumptions`, `stockvaluation.get_growth_anchor`, `stockvaluation.get_reference_data_status` — transparency slices for reporting and reproducibility.
- `stockvaluation.explain_failure` — classify any `ok: false` payload before advising the user.

Returned artifacts: `auditPacket` (`valuation_audit_packet.v1`) and `scenarioBook` (`scenario_book.v1`) are validator-backed references for reproducibility and case selection — mechanical baseline internal-only, market-implied diagnostics diagnostic-only, exactly one user-refined scenario per completed guided path. Segment baseline statuses returned by the service: `segment_weighted_baseline`, `single_industry_fallback`, `segment_evidence_insufficient`, `segment_mapping_blocked` (fields per `segments.md`: segment name, revenue weight, source name, source date, source url, mapped industry, mapping confidence, validation warnings). Market-implied (`marketImpliedExpectations`, `pricedInExpectations`) fields: use these fields as report inputs, not autonomous model changes. Generic source presence is not evidence for any override, including accounting adjustments.

## Call Argument Hygiene

Some clients display MCP arguments. Keep payloads compact and inspectable: only the override fields needed for the call; one-sentence rationale; the smallest valid `evidence_packet` for the changed driver; no research logs, filing text, hidden plans, raw `assumption_judgment`, Scenario Book JSON, or audit packets as arguments. Do not duplicate evidence across `evidence_packet` and `evidence_used`. On `UNSUPPORTED_OVERRIDES`, remove unsupported/report-only fields and retry once with only governed fields — never retry with a larger debug object.

## Failure Recovery

Use `stockvaluation.explain_failure` first, then: missing local service → `sv service start`; missing configuration → `sv check-env` (never ask for secrets in chat); non-JSON response → `sv service status`; unsupported company or insufficient financial data → explain the limitation and do not invent a valuation; recalculation rejected → restate using supported override keys only. Skill install drift is visible in `stockvaluation.health` (`skill.syncStatus`) and fixable with `sv install skills` / `sv verify`.
