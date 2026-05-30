# Narrative Report Style

Use this style guide when writing the final educational report. It translates the old high-quality analyst prompt behavior into skill guidance without restoring the old Python runtime.

This guide is subordinate to `report-template.md`; report-template.md controls the final report structure, section order, and required summaries. This guide improves prose quality only. It does not control section order, does not replace required template sections, and cannot justify the older loose story-and-numbers report shape.

## Core Style

- Publication-quality valuation writing.
- Professional, authoritative, restrained analysis.
- Confident, conversational, intellectually engaging prose.
- Setup -> tension -> insight -> resolution.
- Persuasive but factual; never hype.
- Clear separation between market price, model intrinsic value, assumptions, evidence, and unsupported topics.
- No personalized recommendation language.

Central prose rule: Combine story and numbers inside the canonical report template. Keep assumptions realistic and sector-consistent. Maintain numerical consistency between narrative and DCF data.

## Central Tension

When MCP JSON includes `marketImpliedExpectations` or `pricedInExpectations`, use them as the central tension:

- What growth is the market price implying?
- What operating margin is the market price implying?
- What sales-to-capital or reinvestment efficiency is required?
- What risk or cost-of-capital setting makes the price easier or harder to justify?
- Are those combinations believable given the evidence?

Market-implied and priced-in sections are report inputs, not autonomous model changes.

## Internal Narrative Completeness Check

The report should use prose-first sections supported by compact tables, but only within the structure controlled by `report-template.md`. Tables support the story; they do not replace required template sections.

```json
{
  "title": "string",
  "growth": {
    "title": "string",
    "narrative": "string"
  },
  "margins": {
    "title": "string",
    "narrative": "string"
  },
  "investment_efficiency": {
    "title": "string",
    "narrative": "string"
  },
  "risks": {
    "title": "string",
    "narrative": "string"
  },
  "key_takeaways": {
    "title": "string",
    "narrative": "string"
  }
}
```

Do not print this JSON by default. Use it as an internal completeness check.

## Section Guidance

### Growth

Explain revenue drivers, market expansion, scale advantages, pricing power, segment growth, growth-anchor context, and what growth would have to be true. Compare baseline growth to market-implied growth when returned.

### Margins

Explain current and target operating margins, operating leverage, cost structure, pricing power, competitive positioning, and what margin expansion would have to be true. Compare baseline margin to market-implied margin when returned.

### Investment Efficiency

Explain sales-to-capital, reinvestment discipline, return on capital, asset intensity, capital efficiency, and whether the growth story can be funded. Lower sales-to-capital means more reinvestment need; higher sales-to-capital means more capital efficiency.

### Risks

Explain operational, competitive, regulatory, macro, currency, cyclicality, cost-of-capital, and data-quality risks. Do not use risk language to justify unsupported autonomous WACC changes.

### Key Takeaways

Explain the central valuation tension, strongest assumption support, weakest assumption support, and what would change the model. Keep this educational and non-advisory.

## Tone Guardrails

- Do not say the user should buy, sell, hold, avoid, or invest.
- Do not call model output a target price.
- Do not hide uncertainty behind confident prose.
- Do not invent missing values to make the narrative feel complete.
- Do not let a story claim float without mapping it to growth, margin, reinvestment, risk, or terminal assumptions.
