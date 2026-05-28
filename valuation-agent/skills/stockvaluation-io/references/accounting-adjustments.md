# Accounting Adjustments

Explain these items when the MCP JSON returns them. Do not invent them when absent.

Autonomous researched judgment may not change R&D capitalization, operating lease conversion, employee options, warrants, NOLs, tax schedules, one-time charges, restructuring, goodwill, or stock-based compensation. Use `{baseDir}/references/accounting-cleanup.md`, `{baseDir}/references/rd-capitalization-decision.md`, and `{baseDir}/references/options-leases-other-claims.md` for support-state decisions.

## R&D Capitalization

R&D capitalization treats some research spending like investment rather than a one-year operating expense. This can change operating income, invested capital, reinvestment, and return on capital.

Current action: explain/flag only unless the service returns a governed value or future MCP support is added and tested.

## Operating Lease Conversion

Operating lease conversion treats lease obligations as debt-like claims when the valuation service returns that adjustment. Explain the effect on operating assets, debt-like obligations, and cost of capital.

Current action: explain returned service adjustments only. Do not invent lease commitments.

## Options And Warrants

Employee options, warrants, or similar claims can reduce common-stock equity value when the service returns option value adjustments. Explain dilution and option value separately from operating performance.

Current action: explain returned service adjustments only. Do not invent option values.

## Tax And NOLs

Tax-rate and net-operating-loss assumptions can change free cash flow. Use service-returned effective assumptions and notes.

Current action: explain returned service values. Do not invent NOL schedules or tax shields.
