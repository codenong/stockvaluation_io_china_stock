# Report Builder Contract

The final report is assembled by code, not written from a template. Run `{baseDir}/scripts/build_report.py` with one JSON file containing the run's structured data plus the named model-written prose fields. The builder owns section order, data-populated tables, the single no-advice line, and the compact Audit block. Sections without underlying data are omitted entirely — the builder never writes "Unavailable" filler. The prose linter (`{baseDir}/scripts/prose_lint.py`) runs inside the builder and blocks rendering on error-level findings.

```bash
python3 {baseDir}/scripts/build_report.py --input report_data.json --out-dir tmp/valuation-reports/<slug>
```

Output: `report.md` and `index.html` (a faithful rendering of the markdown). Return the clickable `index.html` link to the user.

## Visible Spine (owned by the builder)

Valuation View (point or range), Business Story, Growth, Profitability, Reinvestment, Risk, What The Price Would Need (only when the service returned diagnostics), Key Assumptions (each value labeled `anchor:<label>`, `user_input`, or `service`), Guided Judgment, Data Limits, Bottom Line, Sources, Audit (gates from run state, evidence/guided status, source class, skill and service versions).

## What The Model Writes

Only the `prose` fields. Each is plain, company-specific educational analysis — analyze the company, never narrate the workflow:

| Field | Content |
| --- | --- |
| `business_story` | What the company does and the economic story the valuation rests on |
| `growth` | What the revenue path assumes and the evidence behind it |
| `profitability` | The margin path and what maturity looks like |
| `reinvestment` | Capital intensity and what growth costs |
| `risk` | Discount-rate context and company-specific risks |
| `bottom_line` | The compressed conclusion: what the value rides on and what remains unresolved |

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

Populate the structured fields only from MCP tool output and run state (`workflow_state`, `guidedAnswerRecord`, anchor sets, `valuationRange`, evidence items, sources). Use the range form of `valuation` whenever the last valuation response carried `valuationRange`; never collapse a range into a single number yourself.

## Judgment Rules That Remain With The Model

- The report is for an investor-reader, not an agent debugger: no internal terms such as `MCP`, `structuredContent`, `sourceQualityGate`, or `mechanical baseline` in prose unless the user explicitly asks for audit/debug detail.
- Do not show the internal mechanical model value in the default report; if no clean valuation case was produced, say so in `bottom_line` and explain the blockers in plain English.
- Diagnostic scenarios stay diagnostic: market-implied or sensitivity runs belong in `market_implied_diagnostics`, never blended into the headline valuation.
- Educational use only; the builder inserts the single no-advice line ("Educational analysis only. This is not financial advice and makes no buy, sell, or hold recommendation.") — do not add recommendation language anywhere.
