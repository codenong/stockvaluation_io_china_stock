# Segments: Discovery And Quality

Run segment discovery before constructing the researched mechanical baseline. The goal is a segment-aware mechanical baseline when credible revenue weights exist; discovery is mandatory to attempt, weighting is mandatory only when the package validates.

## Discovery

Source order: latest annual report/10-K/20-F or exchange filing; then 10-Q/earnings/investor presentation; then official IR pages. When you have sourced segment rows before the evidence-review gate, call `stockvaluation.propose_segment_mappings` so Java proposes sector mappings from the canonical service data. For prospectus mode start from `prospectus.segmentReview`, `prospectus.packet.segments`, and `prospectus.packet.segmentCandidateTables`: proposed mappings must exist before the first review gate when candidate tables are present. Treat titles, row labels, and values as filing facts, then review which rows are true model segments vs subrows or totals, and how each maps to a service sector key or explicit scenario segment. Never rely on service-side name matching after the review gate.

`prospectus.segmentReview` is the review starting point, not final judgment. It includes `revenueCoveragePct`, `materialGap`, `proposedMappings`, `unmappedRows`, `allowedActions`, and row-level `mappingScore`, `rationale`, `rowRole`, `components`, and `warnings`. Use the rationale and warnings to explain why a proposal should be approved, corrected, rejected, or left unmapped.

A segment package must carry, per segment: name, sourced revenue weight or amount, source name/url/date, mapped industry, service `sector_key` (display labels are not enough), mapping confidence, and validation warnings. Use product/business segments for operating economics; geography is risk context unless it is the actual reported operating structure.

Baseline quality statuses: `segment_weighted_baseline` (credible weights mapped and used), `single_industry_fallback` (no usable package), `segment_evidence_insufficient` (names/sources without weights or below coverage), `segment_mapping_blocked` (weights exist but mapping confidence/coverage blocks use).

## Hard Rules

- Never invent revenue shares, margins, growth, or sector weights.
- Generic source presence is not segment evidence; segment names without revenue weights are report-only and must not enable weighting.
- Default coverage threshold: at least 80% of revenue mapped before a package can drive a segment-aware baseline.
- Do not merge geography, product families, and reporting units unless the company does.
- Treat `rowRole=grand_total` as excluded, `rowRole=geography` as non-operating context unless management reports it as the operating structure, and `rowRole=residual` as unmapped unless the user supplies a reviewed sector mapping.
- Segment evidence must reference accepted evidence-packet items by exact driver, `source_url`, and `source_date`; blank references are rejected.

## Segment Economics Quality

Report `segment_economics_quality` before presenting segment-aware assumptions: `validated_full_economics`, `partial_economics`, `revenue_only_segments`, `segment_evidence_insufficient`, or `segment_mapping_blocked`. Show per-driver status for revenue mix, growth, margin, and reinvestment intensity. Revenue-only evidence cannot support growth, margin, or reinvestment changes; do not describe a revenue-only segment package as fully segment-modeled. Reinvestment intensity needs explicit capex, R&D, working-capital, or asset-intensity evidence.

Validator acceptance is requested/mapped status only — the effective baseline is confirmed by returned `baseline.segmentAware` and `baseline.baselineUseStatus`. If the service says `segmentAware=false`, describe segment evidence as report-only context. Treat `segment_mapping_material_gap` (unmapped revenue > 10%, or low-confidence mapped revenue > 5%) as a challenged user-facing baseline and never call it clean or fully segment-modeled.

## Prospectus Segment Scenarios

When material candidate rows exist, build the explicit `scenario.segments` package (name, sector_key, mapped industry, revenue path or target revenue, target margin, sales-to-capital, segment-specific terminal assumptions) and send it through `stockvaluation.value_prospectus`; keep source rationale in the evidence packet and report. Ask the actual story-to-numbers question — which disclosed businesses should be modeled separately and with what bounded assumptions — with source-backed defaults shown first; never ask vaguely for "segment mappings". Leave unmappable material segments unmapped and say a clean segment scenario is not ready; keep optional future businesses as explicit upside scenarios unless sourced evidence makes them base-case. Pass planner segments as compact structured rows (name, revenue amount/weight, reviewed mapping fields), never as a prose note.

When the service returns `driverAnchors` from mapped segments, use those low/base/high anchors for numeric guided choices. They are revenue-weighted Damodaran quantiles from the mapped industries, not agent-authored numbers. Describe them as "filing-based segment mix plus Damodaran industry quantiles" — never as simply "from the filing", and never as recommendations. Each anchor set carries `segment_breakdown` (per-segment industry, weight, Q1/median/Q3), `omitted_segments`, and `warnings`; show the question's `anchor_explanation` so the user sees which segments and industry rows produced the weighted anchors, and surface omitted material segments as an incomplete anchor, not a clean one.

The planner may add materiality-gated per-segment questions (`segment_scope` set) when at least two material segments share an anchor and one diverges. Their A/B/C values are that segment's own industry quantiles; answers stay segment-level and route into `prospectusScenarioCandidate.scenario.segments` so the service does the weighting. Per-segment custom D is structured: `{"choice":"D","value":[{"segment":"<name>","field":"target_operating_margin","value":12.0}]}` — never collapse per-segment values into one company number.
