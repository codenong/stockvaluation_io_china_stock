# StockValuation.io Context

StockValuation.io is an agent-native, local-first valuation product where the user's agent orchestrates researched valuation work and local services provide deterministic DCF math.

## Language

**User Agent**:
Claude Code, Codex, or another MCP-capable agent installed by the user that performs workflow orchestration, evidence search, judgment, and report writing.
_Avoid_: hosted agent, StockValuation agent, old valuation-agent runtime

**StockValuation Skill**:
The installed skill pack that teaches the **User Agent** how to perform the researched valuation workflow.
_Avoid_: prompt registry, UI workflow, runtime orchestrator

**Atomic MCP Tool**:
A deterministic local StockValuation tool that performs one bounded operation and does not orchestrate a full valuation.
_Avoid_: researched valuation tool, workflow tool

**Deterministic Valuation Service**:
The local service that owns Yahoo-backed financial-data retrieval and DCF math.
_Avoid_: agent math, skill math

**Baseline DCF**:
The first deterministic DCF output for a ticker before researched evidence adjustments.
_Avoid_: final valuation, researched valuation

**Full Researched Valuation**:
The default user-facing workflow that combines a **Baseline DCF**, **Segment Discovery**, an **Evidence Packet**, **Assumption Judgment**, one recalculation, and a **Final Educational Report**.
_Avoid_: baseline-only valuation, automated report API

**Evidence Packet**:
A cited and dated set of evidence gathered from company filings, investor-relations materials, earnings sources, trusted news, and macro sources.
_Avoid_: uncited research, prompt context

**Segment Discovery**:
The skill-led process for identifying reportable or business segments from the latest filings and official company materials.
_Avoid_: invented segment split, internal segment API

**Assumption Judgment**:
A strict intermediate JSON object that records baseline assumptions, cited evidence, proposed governed changes, confidence, and no-change rationale.
_Avoid_: free-form opinion, prompt analysis

**Auto-Recalculate Once**:
The default behavior where the **User Agent** calls `stockvaluation.recalculate` one time after producing **Assumption Judgment**.
_Avoid_: repeated autonomous recalculation, hidden scenario loop

**Effective Assumptions**:
The assumptions the **Deterministic Valuation Service** actually used after recalculation.
_Avoid_: requested assumptions, mapped assumptions

**Final Educational Report**:
The Markdown report written by the **User Agent** for educational use only and not financial advice.
_Avoid_: investment recommendation, target-price report

**Acceptance Matrix**:
A committed 20-company global, non-financial fixture set that verifies workflow behavior rather than exact valuation numbers.
_Avoid_: valuation baseline fixture, price target benchmark

## Relationships

- A **User Agent** uses the **StockValuation Skill** to run a **Full Researched Valuation**.
- A **Full Researched Valuation** starts with exactly one **Baseline DCF**.
- A **Full Researched Valuation** includes **Segment Discovery** and an **Evidence Packet** before **Assumption Judgment**.
- An **Assumption Judgment** may produce governed changes that trigger **Auto-Recalculate Once**.
- **Auto-Recalculate Once** uses the **Atomic MCP Tool** `stockvaluation.recalculate`.
- **Effective Assumptions** come from the **Deterministic Valuation Service**, not from the **User Agent**.
- A **Final Educational Report** summarizes the **Evidence Packet**, **Assumption Judgment**, recalculation output, **Effective Assumptions**, and data-quality notes.
- The **Acceptance Matrix** checks the workflow contract across diverse non-financial companies without locking exact DCF numbers.

## Example Dialogue

> **Dev:** "Should we add a tool that performs the whole researched valuation?"
> **Domain expert:** "No. The **User Agent** runs the **Full Researched Valuation** from the **StockValuation Skill**. StockValuation only exposes **Atomic MCP Tools** such as `stockvaluation.value_ticker` and `stockvaluation.recalculate`."

## Flagged Ambiguities

- "valuation agent" could mean the old deleted Python runtime or the user's MCP-capable client; resolved: use **User Agent** for Claude Code, Codex, or another user-installed MCP client.
- "final valuation" could mean raw recalculation JSON or the written Markdown artifact; resolved: use **Effective Assumptions** and recalculation output for service results, and **Final Educational Report** for the written educational artifact.
- "scenario assumptions" could mean requested, mapped, unsupported, or effective inputs; resolved: keep those categories separate and reserve **Effective Assumptions** for what the deterministic service actually used.
