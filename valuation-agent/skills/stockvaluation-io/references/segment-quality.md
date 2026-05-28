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
- Revenue weights or revenue amounts before segment weighting. Segment names without revenue weights are report-only.
- At least 80% mapped revenue coverage by default before a segment package can drive a segment-aware mechanical baseline.
- Source name, source URL, source date, mapped industry, mapping confidence, and validation warnings for every segment used in the baseline.

## Allowed action

- Use official segment evidence qualitatively when disclosures are partial.
- Use governed sector-level revenue growth, operating margin, or sales-to-capital overrides only with disclosed evidence and a clean mapping.
- Mark undisclosed revenue shares, margins, or growth rates as unavailable.
- Preserve uncertainty in `assumption_judgment`.
- Use `segment_weighted_baseline` only when the segment package passes evidence, coverage, and mapping checks.
- Use `single_industry_fallback`, `segment_evidence_insufficient`, or `segment_mapping_blocked` when segment evidence cannot safely change the mechanical baseline.

## Do not

- Do not invent segment shares, margins, growth, or sector weights.
- Generic source presence is not segment evidence; a filing or presentation only matters when it contains driver-specific segment facts.
- Segment names without revenue weights must not enable segment weighting.
- Do not use snippets or undated summaries as segment evidence.
- Do not collapse geography and business-line segments unless the company does.
- Do not calculate missing valuation values outside MCP/service output.

## Report Guidance

The segment table should show claim, source, source date, driver affected, and whether the evidence supported a governed change or only explanation.

## QA Expectation

Segment-driven researched changes require direct source URLs and dates. Partial segment evidence usually supports explanation, not recalculation.
