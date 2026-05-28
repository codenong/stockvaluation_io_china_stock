# Special Company Stop Rules

Some companies should not receive a synthetic DCF report. Stop cleanly when the service or model fit cannot support the valuation.

## When It Matters

- Financial firms: banks, insurers, brokers, asset managers, lenders, exchanges, and similar firms.
- Private firms, unavailable tickers, unsupported securities, funds, trusts, or non-operating vehicles.
- Insufficient financial data, missing market price, missing statements, or currency conversion failure.
- Distressed, young, commodity, or cyclical companies where service output fails or warnings are severe.

## Evidence Required

- MCP failure payload or service exception.
- `stockvaluation.explain_failure` classification.
- Company sector/business model if the stop is model-fit driven.
- Service warnings and reference-data status.

## Allowed action

- Call `stockvaluation.explain_failure` for structured failures.
- Explain unsupported company type, insufficient data, missing configuration, stale reference data, non-JSON response, missing local service, currency conversion failure, or upstream service error.
- For financial firms, stop until a governed excess-return, DDM, or equity-model workflow exists.
- For private firms, state that the current public-ticker product is out of scope.

## Do not

- Do not produce a synthetic valuation when baseline MCP valuation failed.
- Do not manually fill missing financial data or market price.
- Do not manually convert currency after a service conversion failure.
- Do not calculate missing valuation values outside MCP/service output.

## Report Guidance

Failure reports should include failure category, plain-language message, recovery path, and the statement that no valuation was invented.

## QA Expectation

Negative cases must fail closed. A report with invented data is worse than a clear unsupported-company explanation.
