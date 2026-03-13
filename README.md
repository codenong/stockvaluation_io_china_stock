# StockValuation.io

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/softcane/spot-vortex-agent)

StockValuation.io is a local-first DCF valuation workspace that runs fully on your machine, with structured research and narrative output layered on top of core valuation calculations.

> **Warning: This project is for educational use and is not financial advice.**


## Fast Onboarding

### One-line startup

To install and run StockValuation.io on your machine using our automated script:

```bash
curl -fsSL https://raw.githubusercontent.com/stockvaluation-io/stockvaluation_io/main/install.sh | bash
```

> **Note:** The script will check prerequisites, download the project if needed, bootstrap local secrets, and interactively prompt for your API keys. It supports **Anthropic, OpenAI, Gemini, Groq, and OpenRouter** for LLM access, plus **`TAVILY_API_KEY`** and **`CURRENCY_API_KEY`** before starting up the containers.

Need these APIs?

- **Tavily (Web Search):** Create a free account at [tavily.com](https://tavily.com)
- **CurrencyBeacon (FX Rates):** Create a free account at [currencybeacon.com](https://currencybeacon.com)

## Product Video

<video controls width="100%">
  <source src="https://golpo-podcast-inputs.s3.amazonaws.com/files/3a92bf82-998d-432e-8297-8ec22343c726.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAZ3MGNKK4PFXK67XK%2F20260313%2Fus-east-2%2Fs3%2Faws4_request&X-Amz-Date=20260313T084056Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=75c284dccbaf5e405f6d9c07bcefc25a55c5c5f2f91557521a56327c78646b21" type="video/mp4">
  Your browser does not support the video tag.
  <a href="https://golpo-podcast-inputs.s3.amazonaws.com/files/3a92bf82-998d-432e-8297-8ec22343c726.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAZ3MGNKK4PFXK67XK%2F20260313%2Fus-east-2%2Fs3%2Faws4_request&X-Amz-Date=20260313T084056Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=75c284dccbaf5e405f6d9c07bcefc25a55c5c5f2f91557521a56327c78646b21">Watch the product video</a>.
</video>

![StockValuation.io Automated DCF Analysis](./assets/StockValuation-io-—-Automated-DCF-Analysis-03-05-2026_02_04_PM.png)


## What Runs Locally

| Service | Purpose | Local URL |
| :--- | :--- | :--- |
| `frontend` | Main UI | `http://localhost:4200` |
| `valuation-service` | Core valuation API | `http://localhost:8081` |
| `valuation-agent` | Orchestration/research API | `http://localhost:5001` |
| `bullbeargpt` | Notebook/chat API | `http://localhost:5002` |
| `postgres` | Local persistence | `localhost:4322` |

## Common Failure Reasons

- The system depends on Yahoo Finance data. If Yahoo Finance does not provide the required company data, valuation can fail.
- Historical coverage is limited because Yahoo Finance typically provides only about 5 years of history.
- Financial sector companies are not supported.

## Security

- Local-first defaults are meant for development on your machine.
- Do not deploy these defaults directly to internet-facing environments.
- Never commit `.env` with real credentials.

## Project Layout


- `frontend/` UI
- `valuation-service/` core valuation engine
- `valuation-agent/` orchestration layer
- `bullbeargpt/` notebook/chat
- `yfinance/` market data facade
- `docker/` local DB init/seed scripts
- `local_data/` runtime data generated locally

## Acknowledgments

Core methodology and reference data are based on Aswath Damodaran resources:

- https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html
