# StockValuation.io

A local-first MCP valuation workflow for people who want AI to help them think through a business, not blindly hand them a stock pick.

StockValuation.io grew out of my own practice with Damodaran-style valuation. I wanted to take the structured way valuation connects story, assumptions, and numbers, and adapt it to an AI-assisted workflow where research can be accelerated but the math remains deterministic and auditable.

> Educational use only. This is not financial advice.

## Demo video

[![GOOGL Codex Valuation Demo](docs/media/googl-codex-valuation-demo-preview.gif)](docs/media/googl-codex-valuation-demo.mp4)

Real Codex CLI run valuing GOOGL with the local StockValuation.io workflow and guided default answers.

In practice, this repo installs a `stockvaluation.io` skill for Codex and Claude, exposes local MCP tools, and runs a local valuation service stack. The agent researches, explains, critiques, and asks questions. The local tools calculate. The user owns the final judgment.

## Why I built this

I have been practicing Damodaran-style valuation for a while, and the part I enjoy most is not the final "fair value" number. It is the discipline of the process.

A good valuation forces me to slow down and ask better questions:

What kind of business is this?
Where does growth actually come from?
What margins are realistic?
How much reinvestment does the company need?
What risks deserve to be priced in?
Which assumptions would completely change the conclusion?

That structure is what I wanted to bring into an AI workflow.

Earlier versions of this project did not always make that distinction clearly enough. The point is not the number by itself; it is the process that lets someone inspect why the number moved.

I do not want an AI agent to secretly invent numbers and hand me a confident stock recommendation. I want the agent to help with research, evidence, explanation, and critique, while the actual valuation math stays deterministic, local, and auditable.

StockValuation.io is my attempt to turn the valuation process I wanted for myself into a tool others can inspect, run, challenge, and improve.

## The problem

DCF is not hard because the formula is mysterious. It is hard because the assumptions are judgment-heavy.

Growth, margins, reinvestment, risk, and terminal value all require a view of the business. Small changes can move the result meaningfully. If those assumptions are hidden, the valuation becomes difficult to trust.

Many valuation tools hide assumptions. Many AI tools blend research, judgment, and math into one confident answer. That makes it too easy to confuse a generated valuation with investment advice.

LLMs can help with reading, summarizing, comparing, source gathering, and explanation. They are dangerous when they invent numbers or perform hidden valuation math.

StockValuation.io is built around a simple idea: let the agent help with research and narrative, but make the valuation math explicit, deterministic, and recalculable. The goal is to connect the business story to the numbers in a way that can be audited.

## The core idea: separate the brain from the calculator

There are three roles in the workflow.

The user agent handles:

- research
- evidence gathering
- business summary
- segment discovery
- assumption judgment
- guided valuation questions
- the final educational report

The local MCP tools and deterministic valuation service handle:

- baseline valuation
- DCF math
- scenario recalculation
- growth anchors
- reference-data status
- effective assumptions
- clear failure explanations
- source policy, `sourceQualityGate` metadata, and SEC/Yahoo adapter provenance

The user:

- challenges assumptions
- answers guided valuation questions
- decides which scenario is reasonable
- owns the final judgment

The LLM should not silently hand-calculate valuation outputs. Scenario math must come from `stockvaluation.recalculate`.

## What you get

- A `stockvaluation.io` skill for Codex and Claude.
- MCP config exposing local `stockvaluation.*` tools.
- Local Docker services: `postgres`, `yfinance`, and `valuation-service`.
- Deterministic DCF math through `valuation-service`.
- Structured JSON for assumptions, baseline value, recalculated scenarios, growth anchors, reference-data status, and failures.
- A researched workflow that stops for evidence review, then asks guided valuation questions before producing the final educational report.
- A process designed to make assumptions visible and challengeable.

MCP means Model Context Protocol. In this repo, it is the local bridge between Codex or Claude and the valuation tools.

## What this is / what this is not

| This is | This is not |
|---|---|
| A local-first valuation workflow | Financial advice |
| A way to audit DCF assumptions | A buy/sell/hold recommendation system |
| A Damodaran-inspired narrative-and-numbers workflow | A guaranteed fair-value engine |
| A tool for learning, research, and critique | A replacement for your judgment |
| An MCP toolchain for Codex / Claude-style agents | A black-box hosted stock-picking app |
| A way to connect business story and valuation math | A promise that the output is correct |
| A project you can inspect, run, break, and improve | A fully local LLM stack unless local provider support is explicitly added |

## Why Damodaran-style?

The Damodaran-style approach appeals to me because it treats valuation as a bridge between story and numbers.

A business story by itself can be too vague. A spreadsheet by itself can be too mechanical. A useful valuation forces the two to meet.

If the story says the company can grow quickly, the numbers should show what that means for revenue, margins, reinvestment, and risk. If the numbers imply unrealistic assumptions, the story has to be challenged.

The output is not "the truth." It is a structured argument that can be inspected and challenged. That is the kind of process I want AI to support.

This project is Damodaran-inspired. It is not affiliated with or endorsed by Aswath Damodaran.

## How the valuation flow works

The default flow is not a one-shot report.

1. The agent checks local service health.
2. The agent calls `stockvaluation.researched_baseline` for the default full researched baseline and source-policy decision.
3. If `sourceQualityGate` requires a decision, the agent stops or labels an explicit quick/no-questions/automation/smoke-test bypass.
4. The agent researches the company.
5. Source-heavy research can use subagents when supported.
6. The agent gathers and classifies driver-specific evidence.
7. The agent stops at a human evidence review gate before guided valuation refinement.
8. After the gate is cleared, the agent builds an evidence-constrained assumption judgment.
9. Any DCF math must come from `stockvaluation.recalculate`, not hand calculations.
10. The agent asks materiality-driven guided valuation questions before the final report.
11. The guided questions include bounded modeling defaults, not investment advice.
12. After the user answers, the agent maps those answers into a user-refined scenario, calls local MCP tools again, and writes the final educational report.

Use a quick or no-questions path only when the user explicitly asks for it.

## Quick start

Docker Desktop or a compatible Docker Engine with Compose is required. The v1 local runtime is the Docker Compose stack in `docker-compose.local.yml`; no native Java/Postgres/yfinance runtime is installed or supported for v1.

From a local checkout:

```bash
./install.sh setup
```

Or run the installer directly from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/stockvaluation-io/stockvaluation_io/main/install.sh | bash -s -- setup
```

Setup installs or updates the skill and MCP config, creates `.env` from `.env.example` if needed, checks the local environment, starts the local Docker services, and prints service status. By default it targets both Codex and Claude.

If `.env` already exists, setup does not overwrite it. Do not commit `.env`.

The curl installer clones the repo to `~/.local/share/stockvaluation_io` by default, then runs setup from that checkout. Set `STOCKVALUATION_INSTALL_DIR=/path/to/dir` to use a different path.

Useful commands:

```bash
./install.sh status
./install.sh start
./install.sh stop
./install.sh uninstall
```

The canonical local runtime starts:

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

To make the assumption-checking step explicit:

```text
Value NVDA using stockvaluation.io.
```

For the default researched flow, expect the agent to research first, build a mechanical baseline, build an evidence-constrained case, then stop and ask guided valuation questions. The final report comes after those answers unless you explicitly ask for a quick or no-questions run.

## MCP tools

- `stockvaluation.health`
- `stockvaluation.value_ticker`
- `stockvaluation.researched_baseline`
- `stockvaluation.recalculate`
- `stockvaluation.get_assumptions`
- `stockvaluation.get_growth_anchor`
- `stockvaluation.get_reference_data_status`
- `stockvaluation.explain_failure`

MCP tools return structured JSON. Agents should treat them as bounded deterministic tools, not as a hidden full valuation agent.

SEC/EDGAR and Yahoo are adapters into a common StockValuation financial schema. For supported SEC-covered researched valuations, the service tries SEC/EDGAR primary filing data first. Yahoo-normalized financials remain available as an explicit fallback or global normalized source, but they must not be labeled primary filing data. Canonical field definitions live in `valuation-service/src/main/resources/data/financial_field_definitions.json` and are mirrored in the installed skill reference. Frozen SEC/Yahoo fixtures are test-only and are not production support logic.

- `stockvaluation.health` checks the MCP adapter and local valuation service.
- `stockvaluation.value_ticker` creates the mechanical baseline valuation.
- `stockvaluation.researched_baseline` creates the default full researched baseline with source policy enabled and returns `sourceQualityGate` when the user must approve fallback, retry, stop, or cross-check.
- `stockvaluation.recalculate` is used for scenario math.
- `stockvaluation.get_assumptions` exposes effective assumptions.
- `stockvaluation.get_growth_anchor` gives context for growth assumptions.
- `stockvaluation.get_reference_data_status` helps users understand what external or reference data was available.
- `stockvaluation.explain_failure` should be used when the service refuses or cannot value a company.

## What runs locally?

Local:

- Skill files installed under the user's Codex or Claude skill directory.
- MCP config for the local `stockvaluation` server.
- Docker services from `docker-compose.local.yml`.
- Postgres data in a local Docker volume.
- DCF math in `valuation-service`.

Not fully local:

- US SEC primary financial data can come from public SEC EDGAR JSON APIs when `SEC_USER_AGENT` is configured.
- Market and company data can come from Yahoo Finance.
- Currency conversion uses the keyless Frankfurter provider by default.
- The agent may use web research for filings, investor relations pages, news, and other public sources.
- Hosted model providers may be used depending on the user's Codex, Claude, or agent setup.

## Provider support

This repo currently targets Codex and Claude skill / MCP workflows.

The local valuation services run on your machine, but that does not automatically mean the full LLM workflow is local. Depending on your agent setup, research and reasoning may still use hosted model providers.

The checked-in `.env.example` is for local service configuration. It does not configure OpenAI, Anthropic, Groq, Gemini, OpenRouter, Ollama, or any other model provider.

Fully local LLM support through Ollama is not implemented by this repo today. The valuation service is local and deterministic; the model runtime depends on your agent configuration.

## Limits

- The service uses live SEC/EDGAR companyfacts and submissions data for supported US SEC filers when `SEC_USER_AGENT` is configured.
- SEC access uses declared User-Agent headers, conservative rate limiting below the SEC fair-access maximum, and in-memory response caching.
- The service still depends on Yahoo Finance for company info, market data, revenue estimates, global coverage, and normalized fallback financial data.
- Research/news search is performed by the user's agent against public sources such as filings, investor relations pages, company newsrooms, news, and other web sources; it is not a local StockValuation data provider.
- US researched valuations prefer live SEC primary-filing financials when supported and configured.
- When SEC primary filing data is unavailable, incomplete, unsupported, disabled, or missing a declared User-Agent, the service falls back to Yahoo-normalized financials and reports that fallback in provenance.
- Non-US researched valuations may use Yahoo-normalized financials with explicit source-provenance and company-report cross-check caveats.
- Valuation can fail when upstream data is missing, unsupported, stale, or low quality.
- Historical coverage is limited.
- Financial-sector companies are not supported.
- Unsupported companies should produce a clear failure, not a synthetic valuation.
- Growth anchors and reference data are context for critique, not proof.
- DCF outputs are sensitive to assumptions and should be challenged.
- The tool does not know the user's financial situation, goals, risk tolerance, or portfolio.
- The output is educational and should not be treated as a recommendation.

A clear failure is better than a fake valuation.

## Security and no-advice notes

- Never commit `.env`, prompt dumps, or local runtime data.
- Never paste real secrets into chat.
- Local defaults are for one developer machine.
- Do not expose local services to the internet unless you know what you are doing.
- Reports are educational only.
- Do not use buy, sell, hold, target-price, or personalized recommendation language.
- Guided-question defaults are modeling defaults. They are not investment recommendations.

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

Core methodology and reference data are inspired by Aswath Damodaran's public valuation resources:

- https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html

This project is not affiliated with or endorsed by Aswath Damodaran. Educational use only.
