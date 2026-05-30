# Segment Quality

Segment evidence can improve assumption judgment, but only when the source discloses enough detail. Segment data must not be invented.

## When It Matters

- A diversified company has materially different businesses.
- Growth, margins, or capital intensity differ by segment.
- The user asks for a segment-aware case.
- Official filings disclose segment revenue, operating income, margins, or business mix.

## Evidence Required

- Latest annual report, 10-K, 20-F, 10-Q, earnings release, or investor presentation.
- Segment names, revenue shares, operating income, margins, and source dates when disclosed.
- Clear distinction between geography, product families, and reportable operating segments.
- Mapping rationale when using sector-level overrides.
- Service sector key (`sector_key` or `yahoo_industry_key`) for each modeled segment. Display labels such as mapped industry are not enough for the valuation service.
- Revenue weights or revenue amounts before segment weighting. Segment names without revenue weights are report-only.
- At least 80% mapped revenue coverage by default before a segment package can drive a segment-aware mechanical baseline.
- Source name, source URL, source date, mapped industry, mapping confidence, and validation warnings for every segment used in the baseline.

## Allowed action

- Use official segment evidence qualitatively when disclosures are partial.
- Use governed sector-level revenue growth, operating margin, or sales-to-capital overrides only with disclosed evidence and a clean mapping.
- Mark undisclosed revenue shares, margins, or growth rates as unavailable.
- Preserve uncertainty in `assumption_judgment`.
- Use `segment_weighted_baseline` only when the segment package passes evidence, coverage, and mapping checks.
- Treat SegmentEconomics validation as requested/mapped artifact status; the effective model baseline is confirmed only by service `segmentAware` and `baselineUseStatus` after recalculation.
- Use `single_industry_fallback`, `segment_evidence_insufficient`, or `segment_mapping_blocked` when segment evidence cannot safely change the mechanical baseline.

## Do not

- Do not invent segment shares, margins, growth, or sector weights.
- Generic source presence is not segment evidence; a filing or presentation only matters when it contains driver-specific segment facts.
- Segment names without revenue weights must not enable segment weighting.
- Do not use snippets or undated summaries as segment evidence.
- Do not collapse geography and business-line segments unless the company does.
- Do not use geography-only disclosure for SegmentEconomics baseline use unless the artifact explicitly marks it as the company's operating-segment basis and gives a mapping rationale.
- Do not calculate missing valuation values outside MCP/service output.

## SegmentEconomics Quality

When a `segment_economics` artifact is available, report `segment_economics_quality` before presenting segment-aware assumptions.

Valid quality labels:

- `validated_full_economics`: revenue mix, growth, margin, and reinvestment intensity have accepted driver-specific evidence for the modeled segments.
- `partial_economics`: at least one non-revenue segment driver is governed, but the segment record is incomplete.
- `revenue_only_segments`: sourced segment revenue mix is available, but growth, margin, and reinvestment intensity are unavailable or report-only.
- `segment_evidence_insufficient`: segment names or sources exist, but revenue weights or driver-specific evidence are insufficient.
- `segment_mapping_blocked`: evidence exists, but mapping confidence, coverage, disclosure level, or provenance blocks model use.

Show per-driver segment status for revenue mix, growth, margin, and reinvestment intensity. Revenue-only segment evidence cannot support growth, margin, or reinvestment changes. Reinvestment intensity must be tied to explicit capex, R&D intensity, working-capital need, sales-to-capital, or asset-intensity evidence.

SegmentEconomics acceptance does not prove the service used a segment-weighted baseline. In the final report, reconcile `segment_economics_quality` with returned `baseline.segmentAware` and `baseline.baselineUseStatus`; if the service says `segmentAware=false`, describe the segment evidence as requested or report-only context, not as effective segment weighting.

## Report Guidance

The segment table should show claim, source, source date, driver affected, and whether the evidence supported a governed change or only explanation.

## QA Expectation

Segment-driven researched changes require direct source URLs and dates. Partial segment evidence usually supports explanation, not recalculation.

Driver-specific SegmentEconomics evidence must reference an accepted EvidencePacket item by exact driver, `source_url`, and `source_date`; blank URL/date references are rejected rather than treated as wildcards.
