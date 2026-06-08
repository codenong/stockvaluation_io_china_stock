# Browser Report Artifact

Use this guide when a valuation reaches the final report stage and the local client can create files. The goal is to give the user a clickable local HTML report while keeping the chat report as the source of truth.

## When To Create It

- Create the artifact after the final report is complete.
- Create it by default for normal valuation runs when local filesystem and shell access are available.
- Also create it whenever the user asks for a report link, browser report, visual report, HTML report, or clickable output.
- Skip it when the workflow stops before a final report, or when the client cannot write local files. Say plainly that only the chat report is available.

## Content Contract

- Render the same final Markdown report that follows `report-template.md` and has passed `report-prose-quality.md`. Do not replace the report-template sections with a shorter visual-only memo.
- Include the compressed conclusion in `Bottom Line`.
- Include every visible guided-refinement question in `Guided Judgment`: question, driver, baseline/default, evidence summary, user answer or accepted default, and model action.
- Include unanswered, bypassed, report-only, unsupported, and default-accepted questions when they are material to understanding the conclusion.
- Keep raw MCP JSON, hidden guided-question plans, raw Scenario Book JSON, and audit packets out of the visual report unless the user explicitly asks for audit/debug detail.
- Keep the concise educational-use and no-financial-advice line near the start.

## How To Render

Use the bundled renderer. It has no third-party dependencies.

```bash
python3 "{baseDir}/scripts/render_report_html.py" \
  --ticker TICKER \
  --company "Company Name" \
  --title "Company Name Valuation Report" <<'MARKDOWN'
# Company Name Valuation Report

...final report markdown...
MARKDOWN
```

By default the renderer writes to `tmp/valuation-reports/` when run from the StockValuation.io repo, or to the operating-system temp folder elsewhere. Set `STOCKVALUATION_REPORT_DIR=/absolute/path` or pass `--out-dir /absolute/path` to choose a different folder.

After rendering, show the user:

- The normal chat report or a concise note that the report was rendered from the final chat report.
- A clickable local file link to `index.html` when the client supports local file links.
- The `file://` browser link printed by the script when the client needs a browser URL.

If the user explicitly asks to open it and a browser-control tool is available, open the `file://` link after creating the artifact.
