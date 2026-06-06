# Segment Discovery

Use this reference to identify reportable or business segments before constructing the researched mechanical baseline and before assumption judgment.

The goal is a segment-aware mechanical baseline when credible segment revenue weights exist. Segment discovery is mandatory to attempt; segment weighting is mandatory only when the evidence package passes validation.

## Source Order

1. Latest annual report, 10-K, 20-F, or equivalent exchange filing.
2. Latest 10-Q, interim report, earnings release, or investor presentation.
3. Official company IR, corporate, annual-report, SEC, exchange, and newsroom pages.

For prospectus mode, start from `prospectus.packet.segmentCandidateTables` returned by `stockvaluation.extract_prospectus`. Treat the table titles, candidate row labels, raw values, normalized values, source rows, and source tables as filing facts. Then use search and company/prospectus evidence to decide which rows are true model segments, which rows are subrows or totals, and how each material segment maps to a valuation-service sector key or to an explicit scenario segment. Do not rely on service-side hard-coded name matching for prospectus segments.

## Output

Summarize discovered segments with:

- Segment name or business-line name.
- Revenue weight, revenue share, or revenue amount when disclosed.
- Source name, source URL, and source date.
- Mapped industry row used by the valuation service.
- Mapping confidence.
- Validation warnings.
- Operating income, margin, or qualitative scale if disclosed.
- Notes on whether segment information is audited, management-reported, or directional.

## Segment Package Contract

A segment package used for a segment-aware mechanical baseline must preserve:

- `segment_name`: the reportable segment or business line.
- `revenue_weight` or `revenue_amount`: sourced, non-invented revenue mix evidence.
- `source_name`: annual report, 10-K, 20-F, 10-Q, earnings release, investor presentation, or official company source.
- `source_date`: filing, release, or presentation date.
- `source_url`: direct official or high-quality source URL or local source reference.
- `mapped_industry`: supported valuation-service industry row.
- `sector_key`: supported valuation-service sector key when the deterministic service call needs one.
- `mapping_confidence`: medium or high confidence for baseline use.
- `validation_warnings`: missing, partial, geographic, stale, or low-confidence evidence notes.

Use product/business segments for operating economics. Geography informs risk and exposure unless geography is the company’s actual reported operating segment structure.

## Baseline Quality Status

Classify the researched mechanical baseline as one of:

- `segment_weighted_baseline`: credible revenue-weighted segments were mapped and used.
- `single_industry_fallback`: no usable segment package was available, so the company-level industry mapping was used.
- `segment_evidence_insufficient`: segment names or sources were found, but revenue weights or revenue amounts were missing or below the coverage threshold.
- `segment_mapping_blocked`: segment revenue evidence exists, but industry mapping confidence or mapped coverage is insufficient.

## Rules

- Do not invent revenue shares, margins, or growth rates.
- Generic source presence is not segment evidence. "10-K found" or "investor presentation found" does not support segment weighting unless it contains segment revenue weights or amounts.
- If official sources disclose named segments without revenue shares, report the names and mark mix as undisclosed.
- Segment names without revenue weights are report-only and must not enable segment weighting.
- If no credible segment evidence is available, degrade to company-level DCF with `single_industry_fallback` unless the company is too complex to discuss responsibly.
- Treat geography, product families, and reporting units as different concepts; do not merge them unless the company does.
- Use segment evidence only to support bounded `assumption_judgment`; do not hand-compute segment valuation output.
