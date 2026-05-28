# StockValuation.io

StockValuation.io lets Codex or Claude value public companies with local tools. It installs a `stockvaluation.io` skill and MCP config, starts local Docker services, and gives the agent deterministic DCF math to use in an educational report.

> Educational use only. This is not financial advice.

## What it does

- Installs the `stockvaluation.io` skill for Codex and Claude.
- Installs MCP config so the agent can call local `stockvaluation.*` tools.
- Runs local Docker services: `postgres`, `yfinance`, and `valuation-service`.
- Uses `valuation-service` for deterministic DCF math.
- Returns structured JSON for assumptions, baseline values, recalculated scenarios, growth anchors, reference-data status, and failures.
- Leaves research, judgment, questions, and report writing to the user's agent.

MCP means Model Context Protocol. In this repo, it is the local bridge between Codex or Claude and the valuation tools.

## How the valuation flow works

The default flow is not a one-shot report.

1. The agent checks local service health.
2. The agent researches the company.
3. Source-heavy research should use subagents when the client supports them. Each subagent should return a compact evidence summary, not long source dumps.
4. The agent builds a mechanical baseline from local MCP output.
5. The agent builds an evidence-constrained case. Any DCF math must come from `stockvaluation.recalculate`, not hand calculations.
6. The agent stops and asks guided valuation questions before the final report.
7. The guided questions include recommended bounded answers. These are modeling defaults, not investment advice.
8. After the user answers, the agent maps those answers into a user-refined scenario, calls local MCP tools again, and writes the educational report.

Use a quick or no-questions path only when the user explicitly asks for it.

## Install

From a local checkout:

```bash
./install.sh setup
```

This installs or updates the skill and MCP config, creates `.env` from `.env.example` if needed, checks the local environment, starts the local Docker services, and prints service status. By default it targets both Codex and Claude.

You can also run the installer directly from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/stockvaluation-io/stockvaluation_io/main/install.sh | bash -s -- setup
```

The curl installer clones the repo to `~/.local/share/stockvaluation_io` by default, then runs setup from that checkout. Set `STOCKVALUATION_INSTALL_DIR=/path/to/dir` to use a different path.

Docker Desktop or a compatible Docker Engine with Compose is required. No native Java/Postgres/yfinance runtime is installed or supported for v1.

If `.env` already exists, setup does not overwrite it. Do not commit `.env`.

The canonical local runtime is `docker-compose.local.yml`. It starts:

- `postgres`
- `yfinance`
- `valuation-service`

The valuation service is published on `http://localhost:8081`. In the main compose stack, `yfinance` is internal to Docker and is not published on `localhost:5000`.

## Use it from Codex or Claude

After setup, ask your agent for a valuation with the local workflow:

```text
Value MSFT using stockvaluation.io.
Value GOOGL using stockvaluation.io.
Value META using stockvaluation.io.
```

For the default researched flow, expect the agent to research first, build a mechanical baseline, build an evidence-constrained case, then stop and ask guided valuation questions. The final report comes after those answers unless you explicitly ask for a quick or no-questions run.

## MCP tools

- `stockvaluation.health`
- `stockvaluation.value_ticker`
- `stockvaluation.recalculate`
- `stockvaluation.get_assumptions`
- `stockvaluation.get_growth_anchor`
- `stockvaluation.get_reference_data_status`
- `stockvaluation.explain_failure`

MCP tools return structured JSON. Scenario math must come from `stockvaluation.recalculate`. Agents should not hand-compute valuation outputs.

## What is local

Local:

- Skill files installed under the user's Codex or Claude skill directory.
- MCP config for the local `stockvaluation` server.
- Docker services from `docker-compose.local.yml`.
- Postgres data in a local Docker volume.
- DCF math in `valuation-service`.

Not fully local:

- Market and company data can come from Yahoo Finance.
- Currency conversion uses the keyless Frankfurter provider by default.
- The agent may use web research for filings, investor relations pages, news, and other public sources.

## Limits

- The service depends on Yahoo Finance data.
- Valuation can fail when Yahoo Finance has missing, unsupported, or low-quality data.
- Historical coverage is limited.
- Financial-sector companies are not supported.
- Unsupported companies should produce a clear failure, not a synthetic valuation.
- Growth anchors and reference data are context for critique. They are not proof that a company will match an industry pattern.

## Security and no-advice notes

- Never commit `.env`, prompt dumps, or local runtime data.
- Never paste real secrets into chat.
- Local defaults are for one developer machine. Do not expose them to the internet.
- Reports are educational only.
- Do not use buy, sell, hold, target-price, or personalized recommendation language.
- Guided-question defaults are modeling defaults. They are not advice about what to invest in.

## Citation / acknowledgments

```text
@misc{stockvaluation_io,
  author = {Pradeep Singh},
  title = {StockValuation.io: Local stock valuation tools for Codex and Claude},
  year = {2026},
  publisher = {GitHub},
  url = {https://github.com/stockvaluation-io/stockvaluation_io}
}
```

Core methodology and reference data are based on Aswath Damodaran's resources:

- https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html
