# Search And Evidence

Use this reference when building the evidence packet for a full researched valuation. Search is performed by the user agent, not by StockValuation MCP tools. In full researched valuations, source-heavy search should run in fresh-context research subagents when the client supports subagents or task delegation. After collecting compact source summaries, classify every usable item with `{baseDir}/references/driver-specific-evidence.md`.

## Fresh-Context Research Delegation

Default to delegation for full researched valuations when subagents are available. The main valuation agent should keep only compact evidence summaries in context and remain responsible for assumption judgment, MCP calls, guided questions, and the final report. The main agent remains responsible for deciding whether evidence can affect assumptions; research subagents only gather and summarize evidence.

Use separate research subagents for distinct source families:

1. `filings_annual_report_research`: latest annual report, 10-K, 20-F, 10-Q, exchange filings, and audited segment notes.
2. `earnings_ir_research`: latest earnings release, investor presentation, guidance update, and earnings-call transcript.
3. `latest_news_research`: recent company news, regulatory developments, product/business updates, competitive events, and management actions.
4. `segment_evidence_research`: reportable segments, service lines, geography mix, revenue weights, and segment profitability when relevant.
5. `macro_risk_research`: country, currency, rate, commodity, or end-market context only when directly relevant to revenue, margins, reinvestment, or risk explanation.

Each subagent must return only a compact result:

```json
{
  "research_scope": "filings_annual_report_research|earnings_ir_research|latest_news_research|segment_evidence_research|macro_risk_research",
  "company": "string",
  "ticker": "string",
  "sources_checked": [
    {
      "source_title": "string",
      "source_url": "string",
      "source_date": "YYYY-MM-DD|unknown",
      "status": "checked|retrieved|used|not_used|missing|unavailable|not_applicable",
      "source_type": "filing|annual_report|earnings|presentation|transcript|company_news|macro|segment",
      "used": true
    }
  ],
  "evidence_items": [],
  "conflicts_or_uncertainties": [],
  "data_gaps": [],
  "suggested_driver_focus": []
}
```

Do not return full article text, full filing text, long transcripts, broad search logs, or raw snippets. If subagents are unavailable, emulate the same discipline in the main context: read sources, extract compact evidence items, and discard source bodies before continuing.

## Source Order

Use company-domain-first search before broad web search:

1. Official investor-relations, investors, IR, corporate, annual-report, press, and newsroom domains.
2. Latest annual report, 10-K, 20-F, 10-Q, earnings release, investor presentation, and exchange filing sources.
3. Earnings-call transcripts, guidance updates, and material company news from trusted sources.
4. Relevant macro context only when it directly affects the company's revenue, margins, reinvestment, or currency exposure.

## Evidence Packet Fields

Before assumption judgment or autonomous `stockvaluation.recalculate`, keep the researched artifact in this compact EvidencePacket shape:

```json
{
  "ticker": "string",
  "company": "string",
  "run_mode": "full_researched",
  "source_families": [],
  "sources_checked": [],
  "evidence_items": [],
  "conflicts_or_uncertainties": [],
  "data_gaps": []
}
```

The agent-native validator returns `ok`, `status`, `sanitized_packet`, `governed_evidence`, `report_only_evidence`, `rejected_evidence`, `source_family_status`, `validation_warnings`, and `unsupported_blockers`. Use that result as the boundary between research and model-change judgment.

For each item used in assumption judgment, preserve:

- `claim`: concise factual claim.
- `source_title`: page, filing, release, or article title.
- `source_url`: direct URL.
- `source_date`: release, filing, publication, or presentation date; use `unknown` only when no date is available.
- `status`: checked, retrieved, used, not_used, missing, unavailable, or not_applicable.
- `evidence_type`: `filing`, `earnings`, `company_news`, `macro`, or `segment`.
- `driver`: `revenue_growth`, `operating_margin`, `reinvestment_sales_to_capital`, `risk_wacc`, `terminal_value_mature_state`, or `accounting_adjustments`.
- `direction`: `supports higher assumption`, `supports lower assumption`, or `neutral/mixed`.
- `confidence`: `high`, `medium`, or `low`.
- `assumption_implication`: concise implication for the specific valuation assumption.
- `allowed_to_affect_autonomous_recalculation`: `true` only for strong governed evidence; otherwise `false`.
- `model_action`: `governed assumption change`, `report explanation only`, or `explain/flag only unsupported`.

## Rules

- Prefer dated primary sources over undated summaries.
- Use the latest available evidence, but do not ignore conflicting older evidence that explains cyclicality or segment mix.
- Do not cite search snippets as evidence.
- Do not use uncited evidence in `assumption_judgment`.
- Keep each evidence item tied to one valuation driver. Do not bundle a generic filing source across all drivers.
- Generic source presence is not evidence. "10-K found", "earnings release found", "investor presentation available", or "SEC filing source captured" is insufficient unless the item names the driver and the relevant fact.
- If evidence is weak, mixed, stale, or uncited, make no autonomous assumption change.
- Accounting adjustments, WACC/risk changes, and terminal-value changes are explain/flag only unless current governed MCP/service support explicitly permits the change and tests cover it.
