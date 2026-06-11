# MCP Tools

All StockValuation tools return full MCP `structuredContent` with JSON. Read `structuredContent` first. The visible text block is intentionally compact for CLI clients and is not a serialized copy of the full structured payload.

When returned, `auditPacket` contains a `valuation_audit_packet.v1` packet reference, compact packet summary, and redacted machine-readable packet. Use it for reproducibility and report writing. Do not copy raw packet JSON into the visible report. The visible text block remains compact and must not expose the internal mechanical baseline value.

When returned, `scenarioBook` contains a `scenario_book.v1` artifact reference, compact summary, and validator-backed book. Use it to choose the main educational scenario and to separate evidence-constrained base, user-refined scenario, explicit scenario, market-implied diagnostics, and internal mechanical baseline references. Do not copy raw Scenario Book JSON into the visible report.

## Workflow Run Tracking And Gate Enforcement

`stockvaluation.extract_prospectus`, `stockvaluation.researched_baseline`, and `stockvaluation.value_ticker` issue a `run_id` and a `workflow_state` summary on success. Pass that `run_id` to `stockvaluation.value_prospectus`, `stockvaluation.plan_guided_questions`, `stockvaluation.apply_guided_answers`, and `stockvaluation.recalculate` so the server enforces workflow gates for the run. Always pass the `run_id` in the default full researched flow.

- Tracked runs enforce two gates: `evidence_review` and `guided_refinement`. Run state persists on disk for 24 hours, so enforcement survives across MCP processes.
- Record gate outcomes explicitly with the `gate_records` argument on any tracked downstream call: `{"gate": "evidence_review", "outcome": "approved" | "corrected" | "caveated" | "bypassed", "reason": "quick" | "no_questions" | "automation" | "smoke_test"}`. A `reason` is required when `outcome` is `bypassed`. Record a gate outcome only after the user actually made that decision; bypasses are recorded, never inferred.
- `stockvaluation.apply_guided_answers` with a `run_id` records the `guided_refinement` gate as `applied` automatically.
- On a tracked run, a scenario-bearing `value_prospectus` or `recalculate` call before the `evidence_review` gate is recorded is refused with `{"ok": false, "error": {"code": "GATE_NOT_CLEARED"}, "failureCategory": "gate_not_cleared", "gate": "evidence_review"}`. A guided-flow `recalculate` (overrides containing `user_judgment` or `guided_refinement`) before answers are applied (and with no bypass recorded) is refused with the same shape and `"gate": "guided_refinement"`.
- Every tool response on a tracked run includes `workflow_state`: `{run_id, gates, gates_passed, gates_pending}`. Calls without a `run_id` behave as before and carry `"gate_enforcement": "untracked"`.
- An unknown or expired `run_id` returns error code `UNKNOWN_RUN_ID`; start a new run from the baseline or extraction tool. Invalid `gate_records` return `INVALID_GATE_RECORD`.

## Deterministic Driver Anchors And Range Output

On a tracked run the server computes per-driver anchor sets `{driver, field, unit, anchors: {low, base, high}}` from deterministic inputs only (prospectus filing history, offering terms, or the service baseline). Each anchor carries a `provenance` string naming its source. The model never authors scenario numbers.

- `stockvaluation.plan_guided_questions` with a `run_id` attaches anchor sets to every material numeric question: bounded choices A/B/C carry the low/base/high anchor values with `anchor_label` and `anchor_provenance`; choice D asks the user to type their own number. "Accept the default" always means the base anchor. Questions whose driver has no computable anchor keep `candidate-required` status with `requires_user_value: true` — ask the user for a specific number; never invent one.
- On tracked prospectus runs the server sets `prospectus_recalculate_supported` automatically, so supplied or anchored candidates always map into bounded choices.
- `stockvaluation.apply_guided_answers` with a `run_id` records per driver which anchor or user value was chosen and returns it as `guidedAnswerRecord` (e.g. `{"revenue_growth": {"value": 34.08, "source": "anchor:base"}}`).
- Enforcement: on a tracked run, a numeric driver value in `value_prospectus.scenario` or `recalculate.overrides` must be one of that driver's recorded anchors, or be declared in `value_sources` as `user_input`, or be absent. Anything else is refused with `{"ok": false, "error": {"code": "UNANCHORED_SCENARIO_VALUE"}, "failureCategory": "unanchored_scenario_value", "driver": "<field>"}`.
- Range output: while material anchored drivers remain unresolved (no guided answer and not pinned in the call), a scenario-bearing call returns `valuationRange` — `{status: "unresolved_material_drivers", unresolved_drivers, spread_drivers, low: {value_per_share, ...}, high: {value_per_share, ...}, value_spread}` — instead of a point estimate. Lead the user-facing answer with this range and name the unresolved driver(s). A point estimate appears only when every material driver is pinned by an anchor choice or an explicit user value.

## Client-Visible Call Arguments

Some agent clients display MCP call arguments before execution. Keep input payloads compact enough to inspect:

- Do not send full research logs, full filing text, broad source lists, report-only evidence, hidden guided-question plans, raw `assumption_judgment`, raw Scenario Book JSON, or raw audit packets as MCP arguments.
- Send only the override fields needed for the current call. Do not use the documented examples as a single payload containing every supported key.
- Use short rationale text. Prefer one sentence.
- For autonomous researched recalculation with a governed assumption change, include the smallest valid `evidence_packet` that validates the requested changed driver: one checked source-family entry per governed source family, one checked source entry per governed evidence source, and only the governed evidence items directly supporting the override.
- Keep broader source quality, conflicts, data gaps, report-only evidence, and unused sources in the evidence review/report, not in the MCP call arguments.
- Avoid duplicating the same evidence in both `evidence_packet` and `evidence_used`. If `evidence_packet` is present, omit `evidence_used` unless a short reference list is necessary for audit clarity.
- If a call fails with `UNSUPPORTED_OVERRIDES`, remove unsupported/report-only fields and retry once only with governed fields. Do not retry by pasting a larger debug object.

## `stockvaluation.health`

Checks the local MCP adapter and valuation service.

Input:

```json
{}
```

Expected output:

```json
{
  "ok": true,
  "tool": "stockvaluation.health",
  "service": {
    "name": "stockvaluation-service",
    "status": "UP"
  },
  "mcp": {
    "name": "valuation-agent",
    "version": "0.1.0"
  }
}
```

## `stockvaluation.value_ticker`

Fetches the baseline local DCF JSON. This is the mechanical/default-provider baseline; do not describe core financials as SEC primary-source backed unless returned provenance says `primary_filing`. Keep `stockvaluation.value_ticker` mechanical. Use `stockvaluation.researched_baseline` for the default full researched source-policy baseline.

Input:

```json
{
  "ticker": "MSFT"
}
```

Use these output sections:

- `valuation`: full valuation-service payload.
- `dcf`: compact DCF summary for reporting.
- `baseline`: normalized live baseline contract for report writers.
- `assumptions`: grouped assumptions and rationales.
- `accountingAndClaims`: compact AccountingAndClaims statuses for accounting cleanup and capital-claim topics.
- `provenance`: compact core financial source metadata and source-policy status.
- `sourceQualityGate`: source-quality decision metadata when the workflow must stop, continue with an explicit bypass, retry, or require company-report cross-check.
- `growthAnchor`: Damodaran growth-anchor mapping, confidence, percentile band, source date, and warnings.
- `referenceData`: market-data and reference-data status.
- `warnings`: service and data-quality notes.
- `policy`: educational-use and no-advice guardrails.

Read `baseline` before presenting assumptions:

- `baseline.baselineQuality`: `segment_weighted_baseline`, `single_industry_fallback`, `segment_evidence_insufficient`, `segment_mapping_blocked`, or `not_calculated`.
- `baseline.baselineUseStatus`: `validated_segment_weighted`, `mechanical_only`, `segment_evidence_insufficient`, `challenged_baseline`, or `blocked`.
- `baseline.segmentAware`, `baseline.segmentCount`, `baseline.segmentCoveragePct`, `baseline.mappedIndustries`, and `baseline.weightedBaselineAssumptions`.
- `baseline.baselineWarnings`, `baseline.unsupportedBaselineDrivers`, and `baseline.unsupportedAdjustmentFields`.
- `baseline.targetOperatingMargin`, `baseline.targetOperatingMarginSource`, and `baseline.targetOperatingMarginStatus`.

If `baselineUseStatus` is `mechanical_only`, `segment_evidence_insufficient`, `challenged_baseline`, or `blocked`, do not present target operating margin as a validated researched or segment-weighted assumption. A single-industry fallback can be shown as deterministic mechanical output, but it is not evidence-constrained research.

Reportable rich-output fields are nested in `valuation` when the Java service returns them:

- `valuation.assumptionTransparency.sourceProvenance`: core financial source class, provider, source date, retrieval status, cross-check status, source policy status, and warnings.
- `valuation.assumptionTransparency.baselineQuality`: `segment_weighted_baseline`, `single_industry_fallback`, `segment_evidence_insufficient`, or `segment_mapping_blocked`.
- `valuation.assumptionTransparency.baselineUseStatus`: whether the baseline is validated for researched use or only mechanical/challenged.
- `valuation.assumptionTransparency.segmentCoveragePct`: percent of company revenue represented by accepted mapped segment evidence.
- `valuation.assumptionTransparency.mappedIndustries`: industry rows used for segment weighting.
- `valuation.assumptionTransparency.weightedBaselineAssumptions`: segment-weighted growth, target operating margin, sales-to-capital, and discount-rate assumptions used before researched overrides.
- `valuation.assumptionTransparency.baselineWarnings`, `unsupportedBaselineDrivers`, `unsupportedAdjustmentFields`, `targetOperatingMarginSource`, and `targetOperatingMarginStatus`.
- `valuation.assumptionTransparency.marketImpliedExpectations`: single-variable implied growth, margin, and sales-to-capital checks.
- `valuation.assumptionTransparency.pricedInExpectations`: priced-in expectation grid and scenario package.
- `valuation.assumptionTransparency.pricedInExpectations.frontier`: break-even or priced-in operating-margin vs implied-growth frontier.
- `valuation.assumptionTransparency.pricedInExpectations.scenarios`: scenario headline table with risk and capital-efficiency settings.
- `valuation.assumptionTransparency.pricedInExpectations.grid`: sensitivity grid when returned.
- `valuation.assumptionTransparency.accountingAndClaims`: status object for R&D capitalization, SBC/dilution, leases, options/warrants, NOL/tax, cash, debt, and share count.
- `valuation.companyDTO.pvTerminalValue`, `valuation.companyDTO.pvCFOverNext10Years`, `valuation.companyDTO.terminalCashFlow`, and `valuation.companyDTO.terminalValue`: terminal value and cash-flow composition.
- `valuation.financialDTO.fcff`, `valuation.financialDTO.reinvestment`, and `valuation.financialDTO.roic`: free-cash-flow, reinvestment, and return-on-capital trajectories.

Use these fields as report inputs, not autonomous model changes. Market-implied fields are not evidence. If a field is absent, say it is unavailable or omit the related table.

Source provenance rules:

- `primary_filing`, `yahoo_normalized`, `company_ir`, and `agent_researched` are the supported source classes.
- For US researched valuations, prefer `primary_filing` when SEC/EDGAR companyfacts or filing-derived data is returned. If the tool returns `sec_missing_user_agent_yahoo_fallback`, `sec_http_error_yahoo_fallback`, `sec_rate_limited_yahoo_fallback`, `sec_cik_not_found_yahoo_fallback`, `sec_unsupported_filer_yahoo_fallback`, `sec_unsupported_taxonomy_yahoo_fallback`, `sec_insufficient_facts_yahoo_fallback`, or `sec_parse_error_yahoo_fallback`, label Yahoo-normalized financials as a fallback and do not imply primary-source support.
- For non-US ordinary listings or unsupported deterministic primary adapters, `primary_adapter_not_supported_yahoo_normalized` means Yahoo-normalized financials are available but company-report cross-check is required before researched claims.
- `sec-edgar-companyfacts` means live SEC/EDGAR companyfacts/submissions data from the deterministic valuation service. `sec-xbrl-fixture` means fixture/test data and must not be described as broad live SEC support.
- For non-US researched valuations, `yahoo_normalized` is allowed when source date, retrieval status, and company-report or filing cross-check status are explicit.
- Treat provenance warnings and material mismatch warnings as data-quality limitations. They are not autonomous assumption evidence.

Field definitions:

- Use `{baseDir}/references/financial-field-definitions.md` for human-readable field meanings.
- The service-owned canonical contract is `valuation-service/src/main/resources/data/financial_field_definitions.json`.
- Field-level provenance is compact in ordinary output and detailed in audit/debug surfaces. Do not invent field meanings or thresholds.

## `stockvaluation.researched_baseline`

Fetches the default full researched baseline with researched source policy enabled. This tool is read-only and ticker-only. It does not accept arbitrary scenario overrides and it does not replace `stockvaluation.recalculate` for governed scenario math.

Input:

```json
{
  "ticker": "MSFT"
}
```

Use the same output sections as `stockvaluation.value_ticker`, plus the researched policy marker in `policy.baselineEntrypoint`.

Read `sourceQualityGate` before assumption judgment, guided refinement, or final report:

```json
{
  "sourceQualityGate": {
    "status": "requires_user_decision",
    "reason": "sec_http_error_yahoo_fallback",
    "primarySourceExpected": true,
    "fallbackSourceAvailable": true,
    "crossCheckRequired": true,
    "allowedActions": ["continue_with_fallback", "retry_primary_source", "stop"]
  }
}
```

Allowed gate statuses include `not_required`, `requires_user_decision`, `bypassed_by_quick_mode`, `bypassed_by_no_questions`, `bypassed_by_smoke_test`, `bypassed_by_automation`, `approved_continue_with_fallback`, `approved_continue_after_cross_check`, `retry_requested`, and `stopped_by_user`.

If SEC was expected and fallback was used, stop immediately after source selection. Say that SEC primary source was expected but unavailable, Yahoo-normalized fallback is available, and ask the user to choose `continue_with_fallback`, `retry_primary_source`, or `stop`.

If `primary_adapter_not_supported_yahoo_normalized` is returned, do not describe it as an SEC failure. Make the gate the first part of evidence review, say that no supported deterministic primary-filing adapter covers this listing, require company-report cross-check before researched claims, and ask the user to choose `continue_after_company_report_cross_check`, corrections/additional sources, or `stop`.

Do not present a generic `approve` prompt as sufficient for either source-quality gate. Quick, no-questions, smoke-test, and automation paths may bypass only when explicitly requested and must label the bypass.

## `stockvaluation.extract_prospectus`

Extracts a review-required `ProspectusFinancialPacket` from a SEC EDGAR Archives HTML prospectus filing. Use it for prospectus mode before any prospectus valuation. This is educational use only and not financial advice.

Input:

```json
{
  "filing_url": "https://www.sec.gov/Archives/edgar/data/1819994/000119312526123456/d123456ds1a.htm",
  "expected_company": "Space Exploration Technologies Corp.",
  "expected_symbol": "SPACE"
}
```

Rules:

- `filing_url` must be a SEC EDGAR Archives `.htm` or `.html` URL. Do not paste raw HTML, raw filing text, non-SEC URLs, local files, or search-result pages into this tool.
- The expected output has `prospectus.packet.reviewStatus = review_required`.
- The expected source gate has `sourceQualityGate.reason = prospectus_extraction_review_required` and internal allowed actions `approve_extracted_packet`, `correct_packet`, `add_sources`, or `stop`.
- The expected provenance is `sourceClass = primary_filing` and `provider = sec-edgar-prospectus`.

Use these output sections:

- `prospectus.packet`: the extracted `ProspectusFinancialPacket` for user review.
- `prospectus.reviewReference`: preferred input to `stockvaluation.value_prospectus` after approval, so the agent does not have to copy a large packet by hand.
- `prospectus.packet.segmentCandidateTables`: raw candidate tables and rows for agent-side segment selection, search, and mapping. These are not final model segments.
- `prospectus.company` and `prospectus.filing`: compact identity and filing metadata.
- `sourceQualityGate`: the review stop point.
- `provenance`: primary filing provenance.
- `policy`: educational-use and no-advice guardrails.

After this call, stop. Review company identity, form type, filing date, source URL, `offering_price`, share-count basis, extracted financial facts, raw segment candidate tables and rows, units, scale, and extraction issues. User approval is a packet-review control, not financial advice.

Do not show the user only a bare list of allowed actions. Show a compact review card with what was extracted, what is missing or ambiguous, source provenance, extraction issues, and the recommended next action. Then show numbered human choices with explanations:

1. Approve and continue - use the extracted packet as reviewed.
2. Correct the packet - provide source-backed fixes before valuation.
3. Add sources - provide another filing, amendment, or primary source before valuation.
4. Stop - do not value this packet.

Map the user's number to the internal action: `1` -> `approve_extracted_packet`, `2` -> `correct_packet: ...`, `3` -> `add_sources: ...`, and `4` -> `stop`. Do not ask humans to type internal action names unless they are using automation. If the user chooses 2 or 3 without details, ask one short follow-up for the correction or source. Choose `approve_extracted_packet` only when the required packet fields are present, source-backed, and internally consistent. For an empty packet, missing revenue, missing share count, missing units/scale, missing filing metadata, or unresolved extraction issues, recommend option 4 stop or option 2 correct the packet, not approval.

## `stockvaluation.value_prospectus`

Runs a local educational valuation from a user-reviewed `ProspectusFinancialPacket`. This tool is blocked unless the packet has `reviewStatus = reviewed`.

Prefer the review-reference path after approval. It keeps the full extracted packet inside the MCP session and avoids losing financial snapshots when the agent summarizes a large packet.

Input:

```json
{
  "review_reference": "prospectus_abc123...",
  "review_status": "reviewed",
  "scenario": {
    "net_proceeds": 75000000000
  }
}
```

Use the full packet path only when needed:

```json
{
  "packet": {
    "schemaVersion": "prospectus_financial_packet.v1",
    "reviewStatus": "reviewed"
  },
  "scenario": {
    "net_proceeds": 75000000000,
    "rd_capitalization": true,
    "rd_amortization_period_years": 5,
    "terminal_return_on_capital": 15,
    "terminal_cost_of_capital": 8.25,
    "terminal_growth_rate": 4.56,
    "segments": [
      {
        "name": "Launch",
        "base_revenue": 4086000000,
        "target_revenue": 40000000000,
        "target_operating_margin": 45,
        "sales_to_capital_years_1_to_5": 3,
        "sales_to_capital_years_6_to_10": 4
      }
    ]
  }
}
```

Do not reconstruct a compact packet from visible summaries. Use `prospectus.reviewReference` when the extracted packet is approved unchanged. Use `packet_overrides` with the review reference for source-backed corrections, or pass the full reviewed `prospectus.packet` if the MCP session reference is unavailable.

`scenario` is optional. Use it only for explicit story assumptions. Supported fields include `net_proceeds`, `rd_capitalization`, `rd_amortization_period_years`, `initial_cost_of_capital`, `terminal_cost_of_capital`, `terminal_growth_rate`, `terminal_return_on_capital`, company-level revenue/margin/sales-to-capital fields, and `segments`. Segment entries may include `name`, `sector_key`, `mapped_industry`, `base_revenue`, `target_revenue`, `projected_revenues`, `target_operating_margin`, `sales_to_capital_years_1_to_5`, and `sales_to_capital_years_6_to_10`. Use full currency units, not millions, unless the packet itself uses a different unit.

Use these output sections:

- `priceBasis`: must be `offering_price` for prospectus mode.
- `valuationBasisStatus`: service status for the cash/share footing. Expected values include `clean_pro_forma_basis`, `pro_forma_cash_missing`, and `gross_proceeds_estimate_only`.
- `valuationCaseStatus`: service status for whether the value can be shown as a clean case. Expected values include `clean_valuation_case` and `challenged_valuation_case`.
- `proceedsBasis` and `valuationBasisWarnings`: net-proceeds or gross-estimate handling and plain warnings.
- `prospectus.packet`: the reviewed packet used for valuation.
- `scenario`: the explicit prospectus scenario used for valuation, when supplied.
- `valuation`, `dcf`, `assumptions`, `baseline`, `growthAnchor`, and `accountingAndClaims`: valuation-service output derived from the reviewed prospectus packet. `baseline` also carries `valuationBasisStatus`, `valuationCaseStatus`, and `proceedsBasis` when returned by service transparency. For challenged prospectus cases, `dcf.valueVisibility = diagnostic_only` and `dcf.caseStatus = challenged_diagnostic`; this means `dcf.estimatedValuePerShare` is audit/debug detail, not a clean report value.
- `provenance`: should identify `primary_filing` / `sec-edgar-prospectus`.
- `sourceQualityGate`: should show the reviewed packet no longer needs the extraction review gate.

Do not use Yahoo Finance, yfinance, market-data revenue estimates, or a live trading market price for prospectus mode unless the user explicitly leaves prospectus mode. In reports, label the price basis as `offering_price`; do not translate it into buy, sell, hold, target-price, or should-invest language.

If `valuationCaseStatus = challenged_valuation_case` or `dcf.valueVisibility = diagnostic_only`, do not present `dcf.estimatedValuePerShare` as a clean investor-facing intrinsic value. This applies even when `valuationBasisStatus = clean_pro_forma_basis`; a clean cash/share basis does not make a material segment gap a clean valuation case. Say no clean user-facing valuation was produced and explain the returned basis or segment issue in plain words. Keep the value hidden before evidence review. After the user chooses `continue with caveats`, asks for valuation detail, or asks for audit detail, show it only as a challenged diagnostic value and keep the blockers next to the number.

Prospectus extraction review is not the evidence review gate and does not replace guided valuation refinement. After `stockvaluation.value_prospectus`, continue into the normal researched workflow: build evidence, stop at `evidence-review-gate.md`, run baseline plausibility, and use `guided-valuation-refinement.md` for material user-judgment questions unless the user explicitly requested quick/no-questions/automation/smoke-test.

## `stockvaluation.plan_guided_questions`

Builds a read-only story-to-driver guided-question plan from compact valuation context. This tool helps the agent generate many candidate questions internally, rank them by materiality, and show only the material company-specific questions. It does not compute valuation math and does not replace `stockvaluation.recalculate`.

Input:

```json
{
  "company": "Microsoft Corporation",
  "ticker": "MSFT",
  "workflow_type": "ticker",
  "baseline_assumptions": {
    "revenue_growth": 7.0,
    "operating_margin": 45.0,
    "sales_to_capital": 2.4
  },
  "baseline_plausibility": {},
  "evidence_packet": {
    "evidence_items": [
      {
        "driver": "revenue_growth",
        "evidence_summary": "Cloud revenue growth remained above the company average.",
        "source_url": "https://example.com/msft-earnings",
        "source_date": "2026-01-30",
        "confidence": "high"
      }
    ]
  },
  "segments": [],
  "market_implied_diagnostics": {},
  "deep_mode": false,
  "max_visible_questions": 15
}
```

Use the returned `guidedQuestionPlan`:

- `planned_visible_question_count`: how many questions passed the materiality filter.
- `question_count_rationale`: why that number was selected.
- `questions`: visible guided questions to ask one at a time.
- `hidden_candidate_questions`: lower-priority or report-only candidates for audit/debug use.
- `evidence_input_quality`: count of received, usable, and dropped compact evidence items.
- `planner_warnings`: warnings to inspect before asking questions.
- `model_action`: `user scenario override`, `report-only user judgment`, or `unsupported`.
- `hidden_model_mapping`: supported override field and candidate value when available.
- `scenario_range`: guided low/default/high cases when material supported inputs exist.
- `scenario_range.status = candidate_values_required`: material questions map to governed fields, but numeric or structured `override_candidate` values are missing.

Rules:

- Use after evidence review and baseline plausibility, not before.
- Keep planner input compact, but each evidence item must include `driver`, `evidence_summary` or `fact`, `source_url`, `source_date`, and non-low `confidence`.
- For SEC prospectus facts, repeat the SEC filing URL and filing date on each planner evidence item.
- If `planner_warnings` is not empty or `evidence_input_quality.dropped_evidence_item_count` is nonzero, retry once with complete dated/cited evidence before asking the user.
- If `scenario_range.status = candidate_values_required`, retry once with source-backed `override_candidate` values for each listed `candidate_requirements.required_field`; if no bounded candidate can be sourced or derived, ask the user for the missing numeric assumption before final valuation.
- Do not send planner output directly to `stockvaluation.recalculate`. After the user answers, use `stockvaluation.apply_guided_answers` when available.
- User answers remain `user_judgment`, not evidence.
- For prospectus mode without deterministic prospectus recalculation, planner questions must remain report-only or unsupported.
- Market-implied diagnostics may influence question priority, but they are not evidence.

## `stockvaluation.apply_guided_answers`

Converts selected guided-question choices into a structured `user_judgment` package and service-input candidates. Use this after the user answers all visible guided questions or accepts defaults. This tool is read-only; it does not run valuation math.

Input:

```json
{
  "guided_question_plan": {},
  "answers": {
    "revenue_runway_revenue_growth": "B"
  },
  "use_defaults": true
}
```

Output:

- `userJudgment`: selected answers, mapped assumptions, report-only assumptions, unsupported assumptions, candidate requirements, and the statement that user answers are not evidence.
- `tickerOverridesCandidate`: a compact candidate for `stockvaluation.recalculate` in ticker workflows.
- `prospectusScenarioCandidate`: a compact candidate for `stockvaluation.value_prospectus.scenario` in prospectus workflows.
- `scenarioRange`: the original planner range metadata for audit and range rendering.

Rules:

- If `userJudgment.scenario_status = recalculation_ready`, do not finish with a report-only final report until the deterministic service call has been attempted.
- If `userJudgment.scenario_status = candidate_values_required`, do not write a final valuation report yet. Retry the planner with candidate values or ask the user for the listed missing numeric assumptions.
- For ticker workflows, send `tickerOverridesCandidate.overrides` to `stockvaluation.recalculate`.
- For prospectus workflows, send `prospectusScenarioCandidate.scenario` to `stockvaluation.value_prospectus` with the reviewed packet. Merge any reviewed explicit `scenario.segments` package first.
- Keep report-only and unsupported assumptions in the report and metadata, not in the service payload.

## `stockvaluation.recalculate`

Recalculates deterministic DCF output with governed scenario overrides. In the default full researched valuation workflow, call it once after producing `assumption_judgment` when the payload is supported.

Compact input example:

```json
{
  "ticker": "MSFT",
  "overrides": {
    "revenue_growth": 8.5,
    "request_policy": {
      "mode": "autonomous_researched"
    },
    "rationale": "One sentence explaining the governed change.",
    "evidence_packet": {
      "ticker": "MSFT",
      "company": "Microsoft Corporation",
      "run_mode": "full_researched",
      "source_families": [
        {
          "family": "earnings_ir_research",
          "status": "checked",
          "source_title": "FY earnings release",
          "source_url": "https://example.com/msft-earnings",
          "source_date": "2026-01-30"
        }
      ],
      "sources_checked": [
        {
          "source_title": "FY earnings release",
          "source_url": "https://example.com/msft-earnings",
          "source_date": "2026-01-30",
          "status": "used",
          "source_type": "earnings",
          "used": true
        }
      ],
      "evidence_items": [
        {
          "driver": "revenue_growth",
          "source_title": "FY earnings release",
          "source_url": "https://example.com/msft-earnings",
          "source_date": "2026-01-30",
          "evidence_summary": "Cloud revenue growth remained above the company average.",
          "direction": "supports higher assumption",
          "confidence": "high",
          "assumption_implication": "Supports modestly higher revenue growth than the mechanical baseline.",
          "allowed_to_affect_autonomous_recalculation": true,
          "model_action": "governed assumption change"
        }
      ],
      "conflicts_or_uncertainties": [],
      "data_gaps": []
    }
  }
}
```

This example is intentionally minimal. For user-refined or explicit scenarios, send only the user-selected supported fields plus `request_policy.mode`; do not include autonomous evidence metadata unless it is needed for that call.

Supported override keys:

- `net_proceeds` for prospectus workflows
- `revenue_growth`
- `operating_margin_next_year` (scenario-only; rejected in autonomous researched mode)
- `operating_margin` (target operating margin only)
- `target_operating_margin`
- `target_pre_tax_operating_margin`
- `margin_convergence_year`
- `sales_to_capital`
- `sales_to_capital_years_1_to_5`
- `sales_to_capital_years_6_to_10`
- `wacc`
- `terminal_growth`
- `tax_rate`
- `segments`
- `sector_overrides`
- `segment_economics`
- `rd_capitalization` (explicit-scenario-only governed AccountingAndClaims path)
- `leases` or `operating_leases` (report-only AccountingAndClaims status; blocked as recalculation overrides)
- `growth_pattern_override`
- `request_policy`
- `rationale`
- `evidence_used`
- `evidence_packet`
- `user_judgment`
- `baseline_plausibility`
- `assumption_judgment`
- `guided_refinement`

Request policy modes:

- `mechanical_baseline`: no discretionary valuation judgment. Use for mechanical baseline context only.
- `autonomous_researched`: strict evidence-constrained mode. Only governed driver evidence may change supported autonomous fields.
- `user_refined_scenario`: bounded user-judgment scenario after guided refinement. User answers are scenario inputs, not evidence.
- `explicit_scenario`: user explicitly requests a scenario outside the default guided flow.

`segments` may be a list or an object with a `segments` list. Segment package fields required for baseline use are segment name, revenue weight or revenue amount, source name, source date, source URL or reference, service sector key, mapped industry display label, mapping confidence, and validation warnings. Use `sector_key` or `yahoo_industry_key` for the valuation-service sector mapping key, for example `software-infrastructure` or `advertising-agencies`; `mapped_industry` is display/context only. Revenue weights may be decimals that sum near `1.0` or percentages that sum near `100`; MCP maps them to service decimal weights. Segment names without revenue weights, generic source presence, missing source metadata, low mapping confidence, missing service sector keys, geography-only disclosure without explicit operating-segment basis, or less than 80% mapped coverage are rejected from segment weighting and reported as unsupported.

`segment_economics` is a validated SegmentEconomics artifact. MCP validates it agent-side, maps accepted revenue mix into the existing `segments` payload, maps governed segment growth, margin, or reinvestment decisions into `sector_overrides`, and preserves rejected/report-only economics in metadata. MCP does not send the raw `segment_economics` artifact to the valuation service. SegmentEconomics acceptance is not the effective baseline by itself; after recalculation, rely on the returned `baseline.segmentAware` and `baseline.baselineUseStatus` to say whether the service actually used a segment-weighted baseline.

Driver-specific SegmentEconomics entries must reference accepted EvidencePacket evidence by exact driver, `source_url`, and `source_date`. Blank URL/date references are not wildcards.

Phase 5 governed accounting scenario input is `rd_capitalization` only. MCP accepts it only when `request_policy.mode = "explicit_scenario"` and the AccountingAndClaims validator accepts the payload. R&D capitalization requires at least three positive dated R&D history records with direct source URLs, an amortization policy, and source provenance with source class, provider, source date, and retrieved status; MCP maps accepted R&D capitalization to `isExpensesCapitalize`, `rdAmortizationMethod`, and `rdAmortizationPeriodYears`. MCP preserves raw AccountingAndClaims decisions in `assumptions.metadata.accounting_and_claims` and `auditPacket.packet.accounting_decisions`. Autonomous researched mode must not toggle R&D capitalization, and lease conversion has no governed Phase 5 recalculation path.

SBC/dilution, options/warrants, NOL/tax, cash, debt, share count, and generic accounting adjustments are report-only, statused, or scenario-only unless a tested governed path accepts them. Direct cash, debt, share-count, option value, warrant value, NOL, tax, target-price, equity-value, and other claim overrides remain blocked.

Baseline quality values:

- `segment_weighted_baseline`: credible segment package was used.
- `single_industry_fallback`: no segment package was available.
- `segment_evidence_insufficient`: names or generic sources were found without enough revenue-weighted evidence.
- `segment_mapping_blocked`: revenue evidence exists but mapped industry coverage or confidence was insufficient.

For autonomous assumption judgment, only matching driver-specific evidence for `revenue_growth`, `operating_margin`, `reinvestment_sales_to_capital`, and sector-level `sector_overrides` for those same levers may change mapped assumptions. `reinvestment_sales_to_capital` evidence maps to the `sales_to_capital` override. `segments`, `rationale`, and `evidence_used` are context or metadata. Do not use `growth_pattern_override` autonomously; reserve it for explicit user-requested scenarios or supported payloads that are not autonomous judgment changes. Do not autonomously change `operating_margin_next_year`, WACC, terminal growth, tax rate, cash, debt, share count, market price, accounting adjustments, or direct valuation outputs.

`operating_margin_next_year` is scenario-only in autonomous researched mode. User-refined and explicit scenarios may send it directly, and it must not silently set `targetPreTaxOperatingMargin`.

User-refined scenario mode may send direct valid inputs for revenue growth, operating margin next year, target operating margin, margin convergence year, sales-to-capital years 1-5, sales-to-capital years 6-10, `segments`, and sector-level revenue growth, operating margin, and sales-to-capital. Sales-to-capital scenario inputs must remain auditable and must not be silently replaced by mechanical guards.

`margin_convergence_year` must be a finite projection year from 1 to 10. Sales-to-capital inputs must be finite positive multiples from 0.05x to 20x. Out-of-bounds values are rejected instead of silently capped.

`user_refined_scenario` must not send WACC, terminal growth, tax rate, or `growth_pattern_override`; those are explicit-scenario-only fields when the user asks for that specific scenario outside bounded guided refinement.

Terminal growth must remain within mature-economy and risk-free-rate constraints. If a requested terminal growth is unsafe, the service should reject it with an agent-readable error rather than silently accepting or capping it.

Generic source presence is not evidence. Do not attach "10-K found" or "SEC filing source captured" as support for a researched recalculate call.

`evidence_packet` is validated by the agent-native MCP layer before recalculation. It is preserved only in `assumptions.metadata.evidence_packet`; it is never sent to the deterministic valuation service as a valuation override. If validation rejects generic source presence, search-result URLs, missing source metadata, unsupported governed drivers, or no-governed-evidence support for requested autonomous changes, the recalculate call fails closed before service execution.

The response separates:

- `assumptions.requested`: what the user or agent requested.
- `assumptions.mapped`: fields sent to the valuation service.
- `assumptions.unsupported`: rejected fields.
- `assumptions.effective`: what the service actually used.
- `assumptions.metadata`: rationale, evidence, validated EvidencePacket metadata, SegmentEconomics metadata, and AccountingAndClaims metadata preserved for auditability but not sent to the valuation service except accepted governed fields.
- `baseline`: live baseline quality/use-status contract after validation or rejection.
- `auditPacket`: `reference`, compact `summary`, and redacted `packet` using schema `valuation_audit_packet.v1`. The packet preserves EvidencePacket status, rejected evidence, segment validation, accounting decisions, baseline plausibility, assumption judgment, requested/mapped/unsupported/metadata/effective buckets, recalculate payload status, guided-refinement status, final case type, data-quality limitations, and audit-safe MCP call references.
- `scenarioBook`: `reference`, compact `summary`, and redacted `book` using schema `scenario_book.v1`. The book preserves scenario visibility, main scenario eligibility, requested/mapped/unsupported/metadata/effective assumptions, payload references, audit/evidence/provenance references, SegmentEconomics status, AccountingAndClaims status, guided-refinement status, and diagnostics.

Allowed audit final case types are `evidence_constrained_no_change`, `evidence_constrained_governed_recalculation`, `user_refined_scenario`, and `insufficient_researched_evidence`. Mechanical baseline is internal-only and is not a user-facing final case, visible scenario, visible report case, or visible MCP text output.

Scenario Book invariants:

- Mechanical baseline is internal-only and cannot be the main scenario, a user-facing scenario, or visible MCP text output.
- Market-implied diagnostics are diagnostic-only and cannot become evidence, autonomous model changes, or the main scenario.
- Completed guided refinement produces exactly one user-refined scenario after answers are completed or defaults are accepted.
- Quick/no-questions runs record guided-refinement bypass and do not invent a user-refined scenario.
- Explicit scenario mode is distinct from user-refined guided mode and requires `request_policy.mode = "explicit_scenario"`.
- Scenario entries preserve requested, mapped, unsupported, metadata, and effective assumptions separately.

Do not pass debt, cash, share count, market price, option value, fair value, target price, terminal value, equity value, upside/downside, direct market-price calibration, or other direct valuation-output fields.

## `stockvaluation.get_assumptions`

Returns the current assumption transparency slice for a ticker.

Input:

```json
{
  "ticker": "MSFT"
}
```

Use it when the user asks for assumption critique without requiring the full valuation payload again.

## `stockvaluation.get_growth_anchor`

Returns the mapped growth anchor:

- mapped entity
- region
- year
- confidence
- percentile band
- source date
- warnings

## `stockvaluation.get_reference_data_status`

Returns service/reference-data status. With a ticker, it can include ticker-specific growth-anchor metadata.

## `stockvaluation.explain_failure`

Classifies structured errors into agent-readable categories:

- `unsupported_company`
- `insufficient_financial_data`
- `missing_local_service`
- `missing_configuration`
- `stale_reference_data`
- `non_json_service_response`
- `currency_conversion_failed`
- `upstream_service_error`
- `unknown_failure`

Use it before explaining failures to the user.
