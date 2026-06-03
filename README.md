# StockValuation.io

A local-first AI valuation workflow for people who want help thinking through a business, not a black-box stock pick.

StockValuation.io grew out of my own practice with Damodaran-style valuation. I wanted to take the structured way valuation connects story, assumptions, and numbers, and adapt it to an AI-assisted workflow where research can be accelerated but the math remains deterministic and auditable.

> Educational use only. This is not financial advice.

## Demo video

[![GOOGL Codex Valuation Demo](docs/media/googl-codex-valuation-demo-preview.gif)](docs/media/googl-codex-valuation-demo.mp4)

Codex CLI run valuing GOOGL with the local StockValuation.io workflow and guided default answers.

In practice, this repo installs a `stockvaluation.io` skill for Codex and Claude, exposes local valuation tools, and runs a local valuation service stack. The agent researches, explains, critiques, and asks questions. The local tools calculate. The user owns the final judgment.

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

The local tools and deterministic valuation service handle:

- baseline valuation
- DCF math
- scenario recalculation
- growth anchors
- reference-data status
- effective assumptions
- clear failure explanations
- source and data-quality checks

The user:

- challenges assumptions
- answers guided valuation questions
- decides which scenario is reasonable
- owns the final judgment

The LLM should not silently hand-calculate valuation outputs. Scenario math must come from the local valuation tools.

## What you get

- A `stockvaluation.io` skill for Codex and Claude.
- Local valuation tools exposed to the user's agent.
- Local Docker services for the valuation runtime.
- Deterministic DCF math and scenario recalculation.
- Structured assumptions, baseline value, growth anchors, reference-data status, and clear failures.
- A researched workflow that stops for evidence review, then asks guided valuation questions before producing the final educational report.
- A process designed to make assumptions visible and challengeable.

## What this is / what this is not

| This is | This is not |
|---|---|
| A local-first valuation workflow | Financial advice |
| A way to audit DCF assumptions | A buy/sell/hold recommendation system |
| A Damodaran-inspired narrative-and-numbers workflow | A guaranteed fair-value engine |
| A tool for learning, research, and critique | A replacement for your judgment |
| An agent toolchain for Codex / Claude-style agents | A black-box hosted stock-picking app |
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

1. The agent checks that the local valuation tools are running.
2. The agent builds a baseline from local deterministic output.
3. The agent researches the company and gathers evidence for the key valuation drivers.
4. The workflow pauses so you can review the evidence before assumptions are refined.
5. The agent asks guided valuation questions, recalculates scenarios through the local tools, and writes the final educational report.

Use a quick or no-questions path only when the user explicitly asks for it.

## Quick start

Docker Desktop or a compatible Docker Engine with Compose is required.

From a local checkout:

```bash
./install.sh setup
```

Or run the installer directly from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/stockvaluation-io/stockvaluation_io/main/install.sh | bash -s -- setup
```

Setup installs or updates the skill and local tool config, starts the Docker services, and prints service status. By default it targets both Codex and Claude.

The curl installer clones the repo to `~/.local/share/stockvaluation_io` by default, then runs setup from that checkout. Set `STOCKVALUATION_INSTALL_DIR=/path/to/dir` to use a different path.

Useful commands:

```bash
./install.sh status
./install.sh start
./install.sh stop
./install.sh uninstall
```

The installer runs the local valuation stack through `docker-compose.local.yml`.

## Use it from Codex or Claude

After setup, ask your agent for a valuation with the local workflow:

```text
Value MSFT using stockvaluation.io.
Value GOOGL using stockvaluation.io.
Value META using stockvaluation.io.
```

For the default researched flow, expect the agent to research, show you the evidence base, ask guided assumption questions, and then write the final report. The final report comes after those answers unless you explicitly ask for a quick or no-questions run.

## Local-first, not fully offline

This repo currently targets Codex and Claude workflows.

The valuation services and DCF math run on your machine. Market data, company filings, currency data, web research, and the model provider used by your agent may still be external. The repo does not provide a fully local LLM stack today.

For runtime, data-source, and tool details, see [Runtime and data details](docs/runtime-and-data-details.md).

## Limits

- Data coverage depends on public filings, market data, and provider availability.
- The workflow may use normalized fallback data when primary filing data is unavailable or unsupported.
- Valuation can fail when upstream data is missing, stale, low quality, or not suitable for the model.
- Historical coverage is limited.
- Non-US, ADR, IFRS, and unusual filing cases may need extra source review or may be unsupported.
- Financial-sector companies are not supported.
- Unsupported companies should produce a clear failure, not a synthetic valuation.
- Growth anchors and reference data are context for critique, not proof.
- DCF outputs are sensitive to assumptions and should be challenged.
- The tool does not know the user's financial situation, goals, risk tolerance, or portfolio.
- The output is educational and should not be treated as a recommendation.

A clear failure is better than a fake valuation.

## Security and no-advice notes

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
