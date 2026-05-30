# Evidence Review Gate

Use this reference in the default interactive researched valuation after source-heavy research, compact evidence gathering, segment discovery, driver-specific evidence classification, and source quality/provenance summary. The default interactive researched valuation must stop at this gate before baseline plausibility, final assumption judgment, guided valuation refinement, user-refined scenario recalculation, or final report writing.

The gate is a human-in-the-loop review point for the evidence base. It is not a recommendation, not financial advice, and not a request for the user to choose a valuation result.

## Allowed Action

Show a compact Markdown evidence review before guided valuation refinement. Ask the user to approve and continue to guided questions, provide corrections, provide additional sources, or continue with caveats. If the user explicitly requests quick valuation, no questions, skip questions, one-shot report, automation, smoke-test, or equivalent bypass language, label the evidence review bypass and guided-refinement bypass instead of fabricating a user-refined scenario.

User approval means the evidence summary is acceptable for this educational workflow. Approval is not financial advice. User corrections are not external evidence unless source-backed and processed through the same evidence rules. User-provided sources must be checked, dated when possible, classified by valuation driver, and added to the evidence packet before they affect assumptions.

## Do Not

Do not ask guided valuation refinement questions before the gate is cleared. Do not write the final report before the gate is cleared unless the user explicitly requested a quick/no-questions/automation/smoke-test bypass. Do not treat generic source presence as evidence. Do not treat user approval, corrections, or guided answers as external evidence without source-backed processing. Do not loosen no-advice, source-quality, or unsupported-field boundaries.

## Gate Contents

The gate must show these items when available, and must explicitly say unavailable, not checked, weak, stale, conflicting, report-only, or unsupported when that is the true status:

- Educational/no-advice framing.
- Company and ticker.
- Source quality summary.
- Sources checked, with source dates and source type.
- Driver-specific evidence for growth, margins, reinvestment, risk, terminal value, segments, and accounting issues when available.
- Segment evidence and segment limitations.
- Latest news or material business context.
- Data gaps.
- Conflicts or uncertainties.
- Supported model changes that may affect governed recalculation.
- Report-only evidence and explanations.
- Unsupported topics and unsupported model fields.
- Proposed workflow treatment and next step.

## Markdown Shape

Use this readable Markdown shape or a tighter equivalent. Keep it compact enough for Codex and cloud Codex.

```text
### Evidence review before guided valuation refinement

Educational use only. This is not financial advice. This review confirms the evidence base before scenario questions.

| Field | Summary |
| --- | --- |
| Company | ... |
| Ticker | ... |
| Core financial source | ... |
| Source quality summary | ... |
| Source quality status | ... |
| Segment evidence status | ... |
| Segment limitations | ... |
| Latest news or material context | ... |
| Material data gaps | ... |

#### Sources checked

| Source | Date | Type | Status | Used for |
| --- | --- | --- | --- | --- |

#### Driver-specific evidence

| Driver | Evidence | Source/date | Confidence | Proposed model use |
| --- | --- | --- | --- | --- |

#### Conflicts, caveats, and unsupported topics

| Topic | Issue | Workflow treatment |
| --- | --- | --- |
| Supported model changes | ... | Can support governed recalculation if accepted by evidence rules |
| Report-only | ... | Explain in report, do not send to MCP as an override |
| Unsupported topics | ... | Keep out of MCP payload; explain limitation |

Reply `approve` to continue to guided valuation refinement.
Reply with corrections if something is wrong.
Reply with additional sources if something important is missing.
Reply `continue with caveats` if the evidence is incomplete but acceptable for this educational scenario.
Reply with an explicit quick/no-questions request only if you want to bypass guided refinement.
```

## Reply Handling

- `approve`: record the evidence review status as approved for educational workflow use, then continue to baseline plausibility, assumption judgment, evidence-constrained recalculation when supported, and guided valuation refinement.
- Corrections: ask for source support when needed, update the evidence packet only after source-backed processing, then show the revised gate or summarize what changed before continuing.
- Additional sources: inspect and classify the sources through `{baseDir}/references/search-and-evidence.md` and `{baseDir}/references/driver-specific-evidence.md` before using them.
- `continue with caveats`: record evidence review status as caveated, preserve data gaps/conflicts in report guidance, and continue without pretending the evidence is stronger than it is.
- Explicit quick/no-questions/automation/smoke-test bypass: label the bypass, skip guided refinement, do not create a user-refined scenario, and write from the evidence-constrained workflow only when available.
