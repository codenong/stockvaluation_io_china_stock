# Scenario Book

Scenario Book is the validated Phase 6 artifact for labeled educational cases. Use it after EvidencePacket, ValuationAuditPacket, SourceProvenance, SegmentEconomics, AccountingAndClaims, and any guided user judgment are available.

The enforced schema is `scenario_book.v1`. The artifact is agent-native and validator-backed. It is not a hidden valuation workflow, hidden research service, or prose-only report policy.

## Allowed Action

- Build a small Scenario Book from governed upstream artifacts and deterministic MCP outputs.
- Use `scenarioBook.summary` and `scenarioBook.book` when returned by `stockvaluation.recalculate`.
- Present user-facing scenarios only when the validator marks them user-facing and eligible.
- Preserve requested, mapped, unsupported, metadata, and effective assumptions for every scenario.
- Preserve payload references, audit packet references, evidence/provenance references, segment economics status, and accounting/claims status.
- Preserve evidence review status: approved, corrected, caveated, bypassed, not run, or unavailable.
- Include market-implied diagnostics only under diagnostics.
- Record quick/no-questions evidence-review and guided-refinement bypass when the user requested it.
- Keep the report educational and not financial advice.

## Do Not

- Do not make the mechanical baseline a user-facing scenario or main scenario.
- Do not use market-implied diagnostics as evidence, autonomous model changes, or the main scenario.
- Do not create a user-refined scenario when evidence review or guided refinement was bypassed.
- Do not mix explicit scenario mode with guided user-refined mode.
- Do not reopen Phase 5 accounting paths. R&D capitalization remains the only governed Phase 5 accounting scenario path; leases, SBC/dilution, options/warrants, NOL/tax, cash, debt, and share count remain statused, report-only, or service-returned unless a future tested contract expands them.
- Do not send unsupported scenario inputs to MCP/service payloads.

## Core Cases

- Evidence-constrained base: researched case after evidence review, plausibility gate, and governed recalculation when supported.
- User-refined scenario: bounded user judgment after guided refinement completes or the user accepts defaults.
- Explicit scenario: supported scenario requested directly by the user outside guided refinement.
- Market-implied diagnostics: diagnostic-only expectations returned by the service.

Mechanical baseline is internal-only. It may appear as an internal reference for reproducibility, but mechanical baseline value/detail must not be in user-facing scenarios, visible MCP text, or default report cases.

Market-implied diagnostics are diagnostic-only. They cannot become evidence, autonomous changes, or the main scenario.

Guided refinement creates exactly one user-refined scenario after all questions are answered or accepted through use defaults. User answers are user judgment, not external evidence.

Quick/no-questions path records evidence-review bypass and guided-refinement bypass and must not fabricate a user-refined scenario.

Explicit scenario mode is distinct from user-refined guided mode. Explicit scenarios require explicit user intent, supported scenario inputs, and `request_policy.mode = "explicit_scenario"`.

## Scenario Entry Contract

Each user-facing scenario must preserve:

- Scenario ID, label, type, status, visibility, and source.
- Assumption deltas from the evidence-constrained base when available.
- Requested, mapped, unsupported, metadata, and effective assumptions.
- Payload reference and deterministic service output reference.
- Audit packet reference and EvidencePacket reference.
- SourceProvenance references and data-quality warnings.
- Evidence review status, caveats, source-backed corrections status, and bypass reason when applicable.
- SegmentEconomics status and limitations.
- AccountingAndClaims status and Phase 5 support labels.

Unsupported or report-only inputs must be preserved in unsupported/metadata/report sections and excluded from mapped MCP/service payloads.

## Report Guidance

Use the Scenario Book to choose the main report case. If a user-refined scenario exists, it is the main scenario. If guided refinement was bypassed, lead with the evidence-constrained base and state the evidence-review and guided-refinement bypasses. If evidence is insufficient, explain the blocker without promoting the mechanical baseline.

Market-implied diagnostics, priced-in frontiers, scenario grids, and sensitivity data belong in diagnostics or comparison sections. They are not evidence and not recommendations.

Avoid buy, sell, hold, target-price, upside/downside recommendation language, or personalized advice.
