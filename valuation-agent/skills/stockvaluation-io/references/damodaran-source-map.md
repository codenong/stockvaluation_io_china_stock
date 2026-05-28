# Damodaran Source Map

This source map connects Damodaran-style principles to current StockValuation.io behavior. Use it to keep method guidance grounded in source URLs and product contracts.

Primary Damodaran sources:

- Data page: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html
- Spreadsheet page: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm

Product contract sources:

- MCP contract: `valuation-agent/mcp_tools.py`
- Service client boundary: `valuation-agent/service_client.py`
- Java input surface: `valuation-service/src/main/java/io/stockvaluation/form/FinancialDataInput.java`
- Java returned report fields: `valuation-service/src/main/java/io/stockvaluation/dto/ValuationOutputDTO.java`
- Assumption/priced-in DTO: `valuation-service/src/main/java/io/stockvaluation/dto/valuationoutput/AssumptionTransparencyDTO.java`
- Company composition DTO: `valuation-service/src/main/java/io/stockvaluation/dto/valuationoutput/CompanyDTO.java`
- Financial projection DTO: `valuation-service/src/main/java/io/stockvaluation/dto/valuationoutput/FinancialDTO.java`

## Principle To Product Map

| Principle | Damodaran source | Product support state | Allowed user-agent action | QA expectation |
| --- | --- | --- | --- | --- |
| FCFF model for supported operating companies | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm | `supported_explanation` | Explain service-selected FCFF model and model-fit limits. | Do not imply model switching without MCP/service support. |
| Financial firms need different models | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm | `unsupported_stop` | Stop for banks, insurers, brokers, asset managers, and similar firms. | No synthetic FCFF report for financial-sector firms. |
| Revenue growth must be evidenced | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html | `supported_adjustment` | Adjust only `revenue_growth` or sector revenue growth with strong cited evidence. | Weak evidence produces no autonomous change. |
| Margins need operating evidence | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html | `supported_adjustment` | Adjust only `operating_margin` or sector margin with strong cited evidence. | No unsupported margin normalization. |
| Growth requires reinvestment | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html | `supported_adjustment` | Use `sales_to_capital` as the governed reinvestment proxy. | High growth cannot ignore capital needs. |
| Terminal value needs mature-state discipline | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm | `supported_explanation` plus `explain_only` for autonomous terminal growth changes | Explain returned terminal fields, PV composition, and sensitivity. | Do not autonomously change terminal growth. |
| Risk, discount rates, and currency must be coherent | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html | `supported_explanation` plus `explain_only` for autonomous WACC changes | Explain returned risk-free rate, ERP source, WACC, country/currency limits. | Do not autonomously change WACC or country risk. |
| R&D and lease conversion can restate operating assets | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm | `future_support` for governed autonomous changes; `supported_explanation` when service returns adjustment output | Explain and flag materiality, but do not send unsupported adjustment payloads. | R&D and lease concepts never become silent model changes. |
| Employee options and warrants can dilute common equity | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm | `supported_explanation` when service returns option value; otherwise `explain_only` | Explain returned option value separately from operating performance. | Do not invent option values. |
| Taxes and NOLs affect free cash flow | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html | `supported_explanation`; autonomous changes are `explain_only` unless explicit supported scenario | Explain returned tax/NOL behavior. | Do not invent NOL schedules or tax shields. |
| Segment mix can change growth, margins, and reinvestment | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html | `supported_adjustment` for governed sector-level levers with disclosed evidence | Use official segment data; mark missing shares/margins unavailable. | Do not invent segment weights. |
| Multiples are driven by fundamentals | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html | `out_of_scope` for model output; `explain_only` for context | Keep relative valuation separate from DCF. | Multiples do not overwrite intrinsic value. |
| Acquisitions, synergy, and value enhancement are separate analyses | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm | `out_of_scope` | Mention only as outside current workflow. | Do not add synergy or control premiums. |
| Real options require an option model | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/spreadsh.htm | `out_of_scope` plus `explain_only` for context | Flag option-like assets qualitatively. | Do not invent real-option value. |

## Current Autonomous Support Boundary

Current autonomous `assumption_judgment` may only change:

- `revenue_cagr` mapped to `stockvaluation.recalculate` `revenue_growth`
- `operating_margin`
- `sales_to_capital`
- sector-level versions of revenue growth, operating margin, and sales-to-capital

Everything else is `supported_explanation`, `explain_only`, `future_support`, `unsupported_stop`, or `out_of_scope` unless the user explicitly asks for a scenario using a field already governed by `stockvaluation.recalculate`.

## Reportable Service Fields

Use returned values only:

- `valuation.assumptionTransparency.marketImpliedExpectations`
- `valuation.assumptionTransparency.pricedInExpectations`
- `valuation.assumptionTransparency.pricedInExpectations.frontier`
- `valuation.assumptionTransparency.pricedInExpectations.scenarios`
- `valuation.companyDTO.pvTerminalValue`
- `valuation.companyDTO.pvCFOverNext10Years`
- `valuation.companyDTO.terminalCashFlow`
- `valuation.companyDTO.terminalValue`
- `valuation.financialDTO.fcff`
- `valuation.financialDTO.reinvestment`
- `valuation.financialDTO.roic`

If any field is absent, say unavailable or omit the related table. Do not recreate the missing values in the user agent.
