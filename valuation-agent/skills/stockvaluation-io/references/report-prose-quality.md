# Report Prose Quality

The prose-cleanup gate is the deterministic linter at `{baseDir}/scripts/prose_lint.py`. It runs every time: the report builder (`{baseDir}/scripts/build_report.py`) executes it automatically and refuses to render on error-level findings. You can also run it directly on any model-written prose:

```bash
python3 {baseDir}/scripts/prose_lint.py --file report.md
```

The rules live in `{baseDir}/scripts/prose_lint_rules.json`: banned generic-AI phrases, process-narration heuristics (the report analyzes the company, not the workflow), and empty-table detection (tables whose data cells are entirely filler such as "Unavailable").

## What To Write Instead

- Plain explanations of growth, margin, reinvestment, risk, terminal value, and accounting limits, specific to the company.
- Driver claims that name the fact, source, date, and model action.
- One concise educational-use and no-financial-advice line (the builder inserts it; do not repeat disclaimers).
- Uncertainty stated plainly: name the unresolved driver and what changing it does.
- Keep evidence detail, guided questions, caveats, and source dates: do not remove required sections, evidence detail, guided questions, caveats, or source dates while cleaning prose.

## What The Linter Catches

- Throat-clearing and generic AI phrasing ("it's worth noting", "in conclusion", "comprehensive overview").
- Process self-narration ("I called the tool", "this report was generated").
- Filler tables: any table whose data cells are all empty, "N/A", or "Unavailable" is an error — omit the section instead.
