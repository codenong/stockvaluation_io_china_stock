# Report: Builder, Linter, Artifact

The final report is assembled by code, not written from a template. Run `{baseDir}/scripts/build_report.py` with one JSON file containing the run's structured data plus the named model-written prose fields. The builder owns section order, data-populated tables, the single no-advice line ("Educational analysis only. This is not financial advice and makes no buy, sell, or hold recommendation."), and the compact Audit block. Sections without underlying data are omitted entirely — the builder never writes "Unavailable" filler. The prose linter (`{baseDir}/scripts/prose_lint.py`, rules in `{baseDir}/scripts/prose_lint_rules.json`) runs inside the builder and blocks rendering on error-level findings: banned generic-AI phrases, process narration, and empty tables.

```bash
python3 {baseDir}/scripts/build_report.py --input report_data.json --out-dir tmp/valuation-reports/<slug>
```

Output: `report.md` and `index.html` (a faithful rendering). Always return the clickable `index.html` link after the final report; skip the artifact only when local file creation is unavailable, and say so.

## Visible Spine (owned by the builder)

Valuation View (point or range), Business Story, Growth, Profitability, Reinvestment, Risk, What The Price Would Need (only when the service returned diagnostics), Projection Walk (when raw `financialDTO` arrays are supplied), Valuation Bridge and Terminal Value (when raw company/terminal DTOs are supplied), Scenario Cases (when a Scenario Book or scenario rows are supplied), Key Assumptions (each value labeled `anchor:<label>`, `user_input`, `service`, or the segment-level forms `segments:anchor:<label>` / `segments:user_input` from `guidedAnswerRecord`), Guided Judgment, Data Limits, Bottom Line, Sources, Audit (gates from run state, evidence/guided status, source class, skill and service versions). When an assumption came from segment-quantile anchors, describe it in prose as filing-based segment mix plus Damodaran industry quantiles — not as a filing fact and not as a recommendation.

## What The Model Writes

Only the `prose` fields — plain, company-specific educational analysis; analyze the company, never narrate the workflow:

| Field | Content |
| --- | --- |
| `business_story` | What the company does and the economic story the valuation rests on |
| `growth` | What the revenue path assumes and the evidence behind it |
| `profitability` | The margin path and what maturity looks like |
| `reinvestment` | Capital intensity and what growth costs |
| `risk` | Discount-rate context and company-specific risks |
| `bottom_line` | The compressed conclusion: what the value rides on and what remains unresolved |

Style: professional, restrained, prose-first with compact supporting tables; setup → tension → insight → resolution; the central tension comes from market-implied/priced-in data when returned. No hype, no unsupported confidence words, no recommendation language, no internal terms (`MCP`, `structuredContent`, `sourceQualityGate`, `mechanical baseline`) unless the user asks for audit/debug detail.

## Input JSON Shape

```json
{
  "company": "...", "ticker": "...", "currency": "USD",
  "valuation": {"point": {"value_per_share": 0.0}}
               // or {"range": {"low": 0.0, "high": 0.0, "unresolved_drivers": ["..."]}},
  "prose": {"business_story": "...", "growth": "...", "profitability": "...",
            "reinvestment": "...", "risk": "...", "bottom_line": "..."},
  "market_implied_diagnostics": {"rows": [{"assumption": "...", "required_value": "...", "note": "..."}]},
  "key_assumptions": [{"driver": "...", "value": 0.0, "unit": "percent", "source": "anchor:base"}],
  "guided_judgment": [{"question": "...", "driver": "...", "answer": "...", "source": "anchor:base"}],
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
