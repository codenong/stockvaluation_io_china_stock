import sys
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_judge_uses_alternate_provider_when_multiple_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    for key in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "openai")
    monkeypatch.delenv("JUDGE_LLM_PROVIDER", raising=False)

    from shared.llm_models import get_provider_for_role

    assert get_provider_for_role("agent") == "openai"
    assert get_provider_for_role("judge") == "groq"


def test_judge_falls_back_to_agent_provider_when_single_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    for key in ("GROQ_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("JUDGE_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)

    from shared.llm_models import get_provider_for_role

    assert get_provider_for_role("agent") == "openai"
    assert get_provider_for_role("judge") == "openai"


def test_config_parses_cors_origins(monkeypatch):
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:4200, http://127.0.0.1:4200 ,http://localhost:3000",
    )

    import config as config_module

    Config = importlib.reload(config_module).Config

    assert Config.CORS_ORIGINS == [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://localhost:3000",
    ]


def test_rewrite_query_prompt_forbids_unsupported_multiples(monkeypatch):
    from services.llm_service import LLMService

    service = object.__new__(LLMService)
    service.default_provider = "claude"

    monkeypatch.setattr(LLMService, "_normalize_provider", lambda self, provider=None: "claude")
    monkeypatch.setattr(LLMService, "is_available", lambda self, provider=None: True)

    captured = {}

    def fake_invoke(self, prompt, provider, max_tokens, temperature=0.2, dump_agent_name=None, dump_metadata=None):
        captured["prompt"] = prompt
        return "rewritten question"

    monkeypatch.setattr(LLMService, "_invoke_text_completion", fake_invoke)

    result = LLMService.rewrite_query(
        service,
        message="Summarize the current MSFT valuation in one sentence using the current notebook context only.",
        context={"ticker": "MSFT", "company_name": "Microsoft Corporation"},
    )

    assert result == "rewritten question"
    assert 'Preserve hard constraints from the user such as "current notebook context only"' in captured["prompt"]
    assert "Do NOT introduce unsupported valuation frameworks or metrics such as P/E, P/S, EV/EBITDA" in captured["prompt"]


def test_rewrite_query_falls_back_when_llm_invents_unsupported_multiples(monkeypatch):
    from services.llm_service import LLMService

    service = object.__new__(LLMService)
    service.default_provider = "claude"

    monkeypatch.setattr(LLMService, "_normalize_provider", lambda self, provider=None: "claude")
    monkeypatch.setattr(LLMService, "is_available", lambda self, provider=None: True)
    monkeypatch.setattr(
        LLMService,
        "_invoke_text_completion",
        lambda self, prompt, provider, max_tokens, temperature=0.2, dump_agent_name=None, dump_metadata=None:
            'Provide a one-sentence valuation summary for MSFT relative to its key valuation multiples (P/E, P/S, EV/EBITDA).',
    )

    original = "Summarize the current MSFT valuation in one sentence using the current notebook context only."
    result = LLMService.rewrite_query(
        service,
        message=original,
        context={"ticker": "MSFT", "company_name": "Microsoft Corporation"},
    )

    assert result == original
