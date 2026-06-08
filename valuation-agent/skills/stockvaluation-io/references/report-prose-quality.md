# Report Prose Quality

Use this guide after the valuation report is complete and before creating the browser report artifact.

## Stop-Slop Pass

Use the `stop-slop` skill from Hardik Pandya (`https://github.com/hardikpandya/stop-slop`) as the prose cleanup lens.

Apply it after the report satisfies `report-template.md`. Do not remove required sections, evidence detail, guided questions, caveats, source dates, or valuation-driver explanations.

## What To Remove

- Throat-clearing phrases such as "here's the thing", "it's worth noting", "this matters because", and "at the end of the day".
- Generic AI report language such as "robust framework", "comprehensive analysis", "key takeaways", "moving forward", and "deep dive".
- Unsupported confidence words such as "clearly", "obviously", "undoubtedly", and "strongly" unless the evidence supports them.
- Repeated disclaimers. Keep one concise educational-use and no-financial-advice line near the start.
- Punchy one-line endings that sound like marketing copy.

## What To Keep

- Plain explanations of growth, margin, reinvestment, risk, terminal value, and accounting limits.
- Evidence review status and guided-refinement status.
- Every visible guided question, including accepted defaults, bypassed questions, unsupported questions, and report-only questions when they affect the conclusion.
- Source names, URLs when available, source dates, confidence, and data-quality limits.
- Specific caveats about mechanical fallback, Yahoo-normalized data, challenged baselines, unsupported fields, and missing evidence.

## Final Check

Before rendering HTML, verify:

| Check | Required outcome |
| --- | --- |
| Template completeness | All required report-template sections are present or explicitly marked unavailable |
| Question completeness | Guided Judgment lists all visible questions or says guided refinement was bypassed |
| Evidence specificity | Driver claims name the fact, source, date, and model action |
| Prose quality | No filler, no generic AI phrasing, no recommendation language |
| Reader clarity | A non-expert investor can tell what is model output, what is evidence, and what remains uncertain |
