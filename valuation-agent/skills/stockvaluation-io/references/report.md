# Report: Builder, Linter, Artifact

The final report is assembled by code, not written from a template. Run `{baseDir}/scripts/build_report.py` with one JSON file containing the run's structured data plus the named model-written prose fields. The builder owns section order, data-populated tables, the single no-advice line ("Educational analysis only. This is not financial advice."), and the compact Audit block. Sections without underlying data are omitted entirely — the builder never writes "Unavailable" filler. The prose linter (`{baseDir}/scripts/prose_lint.py`, rules in `{baseDir}/scripts/prose_lint_rules.json`) runs inside the builder and blocks rendering on error-level findings: banned generic-AI phrases, process narration, prohibited recommendation language, and empty tables.

```bash
python3 {baseDir}/scripts/build_report.py --input report_data.json --out-dir tmp/valuation-reports/<slug>
```

Output: `report_data.json`, `report.md`, and `index.html`. The HTML artifact is a designed local report packet: it keeps the Markdown report intact while adding a thesis-led first screen, case-status value card, driver question cards, market-expectation context, weak-basis banner, and local visuals when structured data is available. By default, `build_report.py` opens `index.html` in the user's default browser after writing it. Use `--no-open` or `STOCKVALUATION_OPEN_REPORT=0` for CI, automation, or tests. Always return the clickable `index.html` link after the final report; skip the artifact only when local file creation is unavailable, and say so. The builder rejects model-written prose that contains numeric values not found in the structured report data, allowing normal rounding and compact units such as `$422.5B`, `$1.92T`, `30.4%`, and `3.55x`.

## Visible Spine (owned by the builder)

Valuation View (case status plus point or range, market price when returned), Investment Thesis, Framing Questions, Valuation Thesis, Business Story, Growth, Profitability, Reinvestment, Risk, What The Price Would Need (only when service diagnostics or priced-in expectations exist), Priced-In Expectations, Sensitivity Analysis from `pricedInExpectations.grid`, Projection Walk (when raw `financialDTO` arrays are supplied), Valuation Bridge and Terminal Value (when raw company/terminal DTOs are supplied), Key Assumptions (each value labeled `anchor:<label>`, `user_input`, `service`, or the segment-level forms `segments:anchor:<label>` / `segments:user_input` from `guidedAnswerRecord`), Guided Judgment, What Would Change The View, Basis Warnings, Data Limits, Bottom Line, Sources, Audit (gates from run state, evidence/guided status, source class, skill and service versions). When an assumption came from segment-quantile anchors, describe it in prose as filing-based segment mix plus Damodaran industry quantiles — not as a filing fact and not as a recommendation. Do not show peer comparisons unless the data exists and the user explicitly asks.

The HTML renderer follows the legacy StockValuation result-page grammar from the old frontend: dark surfaces, green `#20DF7F` accent, compact metric cards, story cards, data tables with right-aligned numeric cells, chart wrappers with fixed responsive heights, and sensitivity heatmaps from deterministic grid data. Charts are generated only from structured report data and must include title, unit label, year labels for paths, and a takeaway. If the run reports `segment_evidence_insufficient`, do not write segment-economics claims or named business-line margin/growth claims in model prose unless a validated segment package or explicit source-backed evidence is also present; the builder rejects known unsupported segment-economics prose patterns.

## What The Model Writes

Only the `prose` fields — plain, company-specific educational analysis; analyze the company, never narrate the workflow:

| Field | Content |
| --- | --- |
| `investment_thesis` | The concise story and tension behind the valuation; answer what must be true, not whether to buy or sell |
| `framing_questions` | Three to five company-specific questions tied to returned drivers, evidence, and unresolved judgment |
| `valuation_thesis` | The longer Damodaran-style narrative that connects business story to value drivers and the current price hurdle |
| `business_story` | What the company does and the economic story the valuation rests on |
| `growth` | What the revenue path assumes and the evidence behind it |
| `profitability` | The margin path and what maturity looks like |
| `reinvestment` | Capital intensity and what growth costs |
| `risk` | Discount-rate context and company-specific risks |
| `terminal_value` | How the terminal assumptions fit the business story when no terminal table is returned |
| `sensitivity_takeaway` | A short explanation of what the returned grid says about the drivers that matter most |
| `what_would_change_the_view` | Three to five metrics or events to monitor, without recommendation language |
| `bottom_line` | The compressed conclusion: what the value rides on and what remains unresolved |

Style: professional, restrained, prose-first with compact supporting tables; setup → tension → insight → resolution. Use the old analyst-prompt pattern: combine story and numbers, make market-implied/priced-in data the central tension when returned, and discuss growth, margins, capital efficiency, risk, and key takeaways. Every number in model-written prose must come from structured report data or a returned source artifact; the builder blocks unsupported numeric prose. No hype, no unsupported confidence words, no recommendation language, no internal terms (`MCP`, `structuredContent`, `sourceQualityGate`, `mechanical baseline`) unless the user asks for audit/debug detail.

## Input JSON Shape

```json
{
  "company": "...", "ticker": "...", "currency": "USD",
  "valuation": {"point": {"value_per_share": 0.0}}
               // or {"range": {"low": 0.0, "high": 0.0, "unresolved_drivers": ["..."]}},
  "case_status": "user_refined_scenario | evidence_constrained_base | diagnostic_baseline | unresolved_range",
  "market_price": 0.0,
  "prose": {"investment_thesis": "...", "framing_questions": ["..."],
            "valuation_thesis": "...", "business_story": "...", "growth": "...",
            "profitability": "...", "reinvestment": "...", "risk": "...",
            "terminal_value": "...", "sensitivity_takeaway": "...",
            "what_would_change_the_view": ["..."], "bottom_line": "..."},
  "market_implied_diagnostics": {"rows": [{"assumption": "...", "required_value": "...", "note": "..."}]},
  "key_assumptions": [{"driver": "...", "value": 0.0, "unit": "percent", "source": "anchor:base"}],
  "guided_judgment": [{"question": "...", "driver": "...", "answer": "...", "source": "anchor:base"}],
  "weak_basis_warnings": ["..."],
  "data_limits": ["..."],
  "sources": [{"title": "...", "url": "...", "date": "..."}],
  "audit": {"workflow_state": {"gates": {}}, "source_class": "primary_filing",
            "skill_version": "...", "service_version": "...", "mcp_version": "..."}
}
```

Populate the structured fields only from MCP tool output and run state (`workflow_state`, `guidedAnswerRecord`, anchor sets, `valuationRange`, evidence items, sources). Use the range form whenever the last valuation response carried `valuationRange`; never collapse a range into a single number yourself.

## Judgment Rules

- Choose the main case from the Scenario Book: the user-refined scenario when guided refinement completed; otherwise the evidence-constrained base with the bypasses stated; if no clean case exists, say so in `bottom_line` and explain the blockers in plain English.
- Do not show the internal mechanical model value in the default report; challenged diagnostic values appear only after the user continues with caveats or asks for detail, labeled as challenged and diagnostic.
- Diagnostic scenarios stay diagnostic: market-implied or sensitivity runs belong in `market_implied_diagnostics`, never blended into the headline valuation.
- Keep raw JSON (plans, audit packets, Scenario Book) out of the report unless the user asks for audit/debug detail.
- Educational use only; the builder inserts the single no-advice line — do not add recommendation language anywhere (`no-advice-policy.md` controls).
