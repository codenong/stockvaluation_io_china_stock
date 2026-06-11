# Evidence And Judgment

Research is performed by the agent; the MCP layer validates. This file owns what counts as evidence and how it becomes (or fails to become) a model change.

## Research Discipline

Delegate source-heavy research to fresh-context subagents when available, one per source family: filings/annual report, earnings/IR, latest news, segment evidence, macro/risk (only when driver-relevant). Search company domains first (IR, annual reports, filings), then trusted broader sources. Each subagent returns only a compact summary: sources checked (title, url, date, type, status) and evidence items. Keep filing bodies, transcripts, and search logs out of the main context. The main agent decides whether evidence can affect assumptions.

## What Counts As Evidence

Every evidence item ties to exactly one driver: `revenue_growth`, `operating_margin`, `reinvestment_sales_to_capital`, `risk_wacc`, `terminal_value_mature_state`, or `accounting_adjustments`. Each item preserves: driver, source name/title, direct `source_url` (never a search-result URL), `source_date` (`unknown` only when truly undated), factual `evidence_summary`, `direction`, `confidence`, `assumption_implication`, `allowed_to_affect_autonomous_recalculation`, and `model_action` (`governed assumption change` / `report explanation only` / `explain/flag only unsupported`).

- Generic source presence is not evidence: "10-K found", "earnings release found", "investor presentation available", "SEC filing source captured" support nothing. A source becomes evidence only when the item names the driver and the relevant fact.
- Do not cite search snippets as evidence; do not use uncited or undated evidence in judgment; do not bundle one source across all drivers; do not invent facts, numbers, or quotes.
- The evidence-packet validator is the boundary: governed vs report-only vs rejected evidence comes from its result, not your impression.

## Autonomous Boundary

Autonomous researched judgment may change only `revenue_cagr` (→ `revenue_growth`), `operating_margin` (target margin only), `sales_to_capital`, and sector-level versions of those three. Everything else — WACC, terminal growth, tax, growth pattern, R&D capitalization, leases, options, NOLs, one-time charges, cash, debt, share count, market price, and any direct valuation output — is explain/flag only; the server rejects unsupported payloads. `operating_margin_next_year` is scenario-only (guided or explicit); flag it as an unsupported blocker in autonomous mode.

A governed change requires all of: driver-specific dated cited evidence from a reliable source, clear direction and implication, conflicts addressed, a governed field, and a modest, explainable move relative to the baseline, growth anchor, segment mix, and data-quality warnings. Weak, mixed, stale, generic, or uncited evidence ⇒ no change, with the no-change reason stated.

## Assumption Judgment

Before the autonomous recalculation, produce a strict `assumption_judgment` object: baseline assumptions; `baseline_plausibility`; `evidence_used` (validated items only — never generic presence, never user answers); `dcf_adjustment_instructions` and `sector_adjustment_instructions` (empty arrays when no governed change, with `no_change_reason`); confidence; `assumptions_left_unchanged` with reasons. Map only governed instructions into `stockvaluation.recalculate` overrides with a short rationale; keep requested, mapped, unsupported, and effective assumptions separate afterward.

## Baseline Plausibility

Before treating any mechanical baseline as a researched base case:

- **Price/value gap**: flag when the model-vs-price gap exceeds 50% or the service forced a `THREE_STAGE` pattern. The flag means the assumption stack needs review, not that the price is right.
- **Growth**: flag growth above the growth-anchor p75 band, materially above market-implied growth, or resting on trailing growth with no cited forward evidence. Trailing growth alone is not a runway.
- **Margin path**: evaluate next-year and target margin separately; target-margin support is not proof the next-year path is supported.
- **Reinvestment**: flag high growth that depends on favorable sales-to-capital without capex/R&D/working-capital/segment support.
- **Optimistic stack**: several individually-defensible favorable assumptions together need stronger evidence than any one alone.
- A negative first-pass researched baseline with `market_calibrated_diagnostic` status stays a challenged baseline; market calibration is diagnostic, never a repair.

If no governed change is allowed, write an evidence-constrained no-change case that says why the baseline remains challenged; never silently promote the mechanical baseline to "rational researched base".

## Case Taxonomy

- **Evidence-constrained base** — autonomous researched case after the gates and any governed recalculation.
- **User-refined scenario** — the one scenario built from completed guided answers (or accepted defaults) and executed deterministically. User answers define a scenario; they are not independent evidence.
- **Explicit scenario** — user-requested supported scenario outside guided refinement (`explicit_scenario` mode).
- **Market-implied diagnostics** — report-only; never evidence, never the main scenario, never sent as overrides. Do not ask what value the user wants, fit to market price, or accept fair value / target price / equity value as inputs.
- **Mechanical baseline** — internal-only scaffolding; visible only in explicit audit/debug detail.

SEC filing facts are primary; external news is report-only context and must not override filing facts.
