# Terminal Value Discipline

Terminal value often carries a large share of DCF value. The user agent may explain returned terminal assumptions and sensitivity, but must not autonomously change terminal growth.

## When It Matters

- PV terminal value is a large share of total present value.
- Terminal growth is close to or above mature-economy/risk-free-rate logic.
- Terminal cost of capital is low while growth remains high.
- The market-implied or priced-in grid depends on aggressive mature-state assumptions.

## Evidence Required

- Service-returned `terminalValueDTO.growthRate`, `terminalValueDTO.costOfCapital`, `terminalValueDTO.returnOnCapital`, and `terminalValueDTO.reinvestmentRate` when available.
- `companyDTO.pvTerminalValue`, `companyDTO.pvCFOverNext10Years`, `companyDTO.terminalCashFlow`, and `companyDTO.terminalValue` when available.
- `financialDTO.fcff`, `financialDTO.reinvestment`, and `financialDTO.roic` when used for discussion.
- Any returned service notes about growth pattern or template selection.

## Allowed action

- Explain terminal growth, terminal cost of capital, terminal ROIC, terminal reinvestment, and terminal value share when returned.
- Include terminal value and cash-flow composition tables only from service-returned fields.
- Use returned priced-in frontier or scenario grids to discuss terminal sensitivity qualitatively.
- Flag terminal growth as a model risk when it looks inconsistent with mature-state logic.

## Do not

- Do not autonomously change terminal growth.
- Do not create a terminal-value bridge, break-even table, or sensitivity table when service fields are absent.
- Do not make terminal growth exceed mature-economy logic without an explicit user scenario and supported MCP field.
- Do not calculate missing valuation values outside MCP/service output.

## Report Guidance

State whether terminal value dominates the DCF and which assumptions make that dominance more or less fragile. If data is missing, say the terminal composition is unavailable instead of filling it.

## QA Expectation

Every rich report should discuss terminal value when returned. No report should claim a researched terminal-growth change unless it came from an explicit supported scenario, not autonomous judgment.
