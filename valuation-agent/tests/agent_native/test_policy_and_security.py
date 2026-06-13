import json
import re
import subprocess
import sys
from pathlib import Path

from valuation_agent.installer import bundled_skill_dir
from valuation_agent.security import sanitize_for_agent

REPO_ROOT = Path(__file__).resolve().parents[3]
ACCEPTANCE_MATRIX = (
    REPO_ROOT / "valuation-agent" / "tests" / "agent_native" / "fixtures" / "researched_acceptance_matrix.json"
)


def test_skill_pack_contains_required_agent_native_references():
    skill_dir = bundled_skill_dir()
    required = {
        "mcp-tools.md",
        "workflow.md",
        "evidence-and-judgment.md",
        "valuation-method.md",
        "segments.md",
        "accounting-and-claims.md",
        "report.md",
        "no-advice-policy.md",
    }

    assert (skill_dir / "SKILL.md").exists()
    assert required == {path.name for path in (skill_dir / "references").glob("*.md")}
    assert (skill_dir / "scripts" / "render_report_html.py").exists()
    assert (skill_dir / "scripts" / "build_report.py").exists()
    assert (skill_dir / "scripts" / "prose_lint.py").exists()


def test_researched_reference_docs_govern_evidence_segments_and_judgment():
    references = bundled_skill_dir() / "references"
    evidence = (references / "evidence-and-judgment.md").read_text(encoding="utf-8").lower()
    segments = (references / "segments.md").read_text(encoding="utf-8").lower()

    assert "company domains first" in evidence
    assert "source_url" in evidence
    assert "source_date" in evidence
    assert "fresh-context subagents" in evidence
    assert "one per source family" in evidence
    assert "keep filing bodies, transcripts, and search logs out of the main context" in evidence
    assert "the main agent decides whether evidence can affect assumptions" in evidence
    assert "never invent revenue shares" in segments
    assert "latest annual report" in segments
    assert "`assumption_judgment`" in evidence
    assert "`evidence_used`" in evidence
    assert "`dcf_adjustment_instructions`" in evidence
    assert "`sector_adjustment_instructions`" in evidence
    for prohibited in ["wacc", "terminal growth", "tax", "cash", "debt", "share count"]:
        assert prohibited in evidence


def test_assumption_judgment_documents_recalculate_payload_mapping():
    evidence = (bundled_skill_dir() / "references" / "evidence-and-judgment.md").read_text(encoding="utf-8").lower()

    assert "`revenue_cagr` (→ `revenue_growth`)" in evidence
    assert "map only governed instructions into `stockvaluation.recalculate` overrides" in evidence
    assert "keep requested, mapped, unsupported, and effective assumptions separate" in evidence


def test_main_skill_requires_mcp_json_and_agent_written_educational_report():
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")

    assert "stockvaluation.value_ticker" in skill_text
    assert "Do not hand-compute valuation math" in skill_text
    assert "educational" in skill_text.lower()
    assert "financial advice" in skill_text.lower()
    assert "BullBearGPT" not in skill_text
    assert "Angular" not in skill_text
    assert "sv value" not in skill_text


def test_skill_docs_describe_browser_report_artifact():
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    report = (bundled_skill_dir() / "references" / "report.md").read_text(encoding="utf-8")

    assert "report.md" in skill_text
    assert "build_report.py" in report
    assert "Guided Judgment" in report
    assert "Bottom Line" in report
    assert "tmp/valuation-reports" in report
    assert "index.html" in report


def test_skill_docs_use_deterministic_prose_linter_gate():
    skill_dir = bundled_skill_dir()
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    report = (skill_dir / "references" / "report.md").read_text(encoding="utf-8")

    assert "prose linter" in skill_text
    assert "prose_lint.py" in report
    assert "prose_lint_rules.json" in report
    assert "blocks rendering on error-level findings" in report
    for text_blob in (skill_text, report):
        assert "stop-slop" not in text_blob


def test_html_report_renderer_creates_local_artifact(tmp_path):
    script = bundled_skill_dir() / "scripts" / "render_report_html.py"
    markdown = """# Microsoft Valuation Report

## How To Read This

Educational use only. This is not financial advice.

## Valuation View

| Field | Value |
| --- | --- |
| Company | Microsoft |
| Ticker | MSFT |

## Bottom Line

The conclusion depends most on growth and margin judgment.

## Guided Judgment

| Question | Driver | Baseline assumption | Evidence summary | User answer | Model action |
| --- | --- | --- | --- | --- | --- |
| Keep cloud growth above baseline? | Revenue growth | Baseline | Azure growth evidence | Accepted default | user scenario override |
"""

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--out-dir",
            str(tmp_path),
            "--ticker",
            "MSFT",
            "--company",
            "Microsoft",
            "--title",
            "Microsoft Valuation Report",
        ],
        input=markdown,
        text=True,
        capture_output=True,
        check=True,
    )

    match = re.search(r"HTML report: (.+)", result.stdout)
    assert match, result.stdout
    html_path = Path(match.group(1))
    markdown_path = html_path.parent / "report.md"

    assert html_path.exists()
    html_text = html_path.read_text(encoding="utf-8")
    assert markdown_path.read_text(encoding="utf-8") == markdown
    assert "<table>" in html_text
    assert "Guided Judgment" in html_text
    assert "Browser link: file://" in result.stdout


def test_main_skill_makes_full_researched_valuation_the_default_workflow():
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    lower = skill_text.lower()

    assert "full researched valuation" in lower
    assert "default workflow" in lower
    assert "stockvaluation.health" in skill_text
    assert "stockvaluation.value_ticker" in skill_text
    assert "segment discovery" in lower
    assert "evidence packet" in lower
    assert "evidence review gate" in lower
    assert "assumption_judgment" in skill_text
    assert "auto-recalculate once" in lower
    assert "stockvaluation.recalculate" in skill_text
    assert lower.index("evidence review gate") < lower.index("baseline plausibility")
    assert lower.index("assumption_judgment") < lower.index("guided refinement:")


def test_stockvaluation_io_reference_triggers_guided_refinement_by_default():
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    workflow = (bundled_skill_dir() / "references" / "workflow.md").read_text(encoding="utf-8")
    lower = skill_text.lower()

    assert "whenever the prompt mentions `stockvaluation.io`" in lower
    assert "plain request such as \"value company using stockvaluation.io\"" in lower
    assert "not a quick valuation and not a one-shot report request" in lower
    assert "never infer an evidence-review or guided-refinement bypass" in lower
    assert "gate_not_cleared" in lower
    assert "ask one question at a time" in lower
    assert '"My analysis"' in workflow
    assert "run guided refinement in every default flow" in workflow.lower()


def test_full_researched_valuation_delegates_source_heavy_search_to_subagents():
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    evidence = (bundled_skill_dir() / "references" / "evidence-and-judgment.md").read_text(encoding="utf-8").lower()

    assert "research subagents" in skill_text
    assert "delegate source-heavy research to fresh-context subagents" in evidence
    assert "one per source family" in evidence
    assert "the main agent decides whether evidence can affect assumptions" in evidence


def test_segment_aware_baseline_docs_define_workflow_statuses_and_schema():
    references = bundled_skill_dir() / "references"
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    segments = (references / "segments.md").read_text(encoding="utf-8").lower()
    mcp = (references / "mcp-tools.md").read_text(encoding="utf-8").lower()

    assert "segment-aware mechanical baseline" in skill_text
    assert skill_text.index("segment discovery") < skill_text.index("researched mechanical baseline")

    for status in [
        "segment_weighted_baseline",
        "single_industry_fallback",
        "segment_evidence_insufficient",
        "segment_mapping_blocked",
    ]:
        assert status in segments
        assert status in mcp

    for required_field in [
        "segment name",
        "revenue weight",
        "source name",
        "source date",
        "source url",
        "mapped industry",
        "mapping confidence",
        "validation warnings",
    ]:
        assert required_field in mcp

    assert "80%" in segments
    assert "generic source presence is not segment evidence" in segments
    assert "segment names without revenue weights" in segments


def test_report_reference_has_no_advice_framing_without_recommendation_phrases():
    report = (bundled_skill_dir() / "references" / "report.md").read_text(encoding="utf-8")
    lower = report.lower()

    assert "educational" in lower
    assert "not financial advice" in lower
    for phrase in [
        "you should invest",
        "target price is",
        "we recommend buying",
        "we recommend selling",
        "buy rating",
        "sell rating",
        "hold rating",
    ]:
        assert phrase not in lower


def test_report_reference_limits_model_writing_to_named_prose_fields():
    report = (bundled_skill_dir() / "references" / "report.md").read_text(encoding="utf-8")
    lower = report.lower()

    assert "what the model writes" in lower
    assert "only the `prose` fields" in lower
    assert "`business_story`" in lower
    assert "`bottom_line`" in lower
    assert "analyze the company, never narrate the workflow" in lower


def test_report_reference_keeps_mechanical_baseline_out_of_default_report():
    report = (bundled_skill_dir() / "references" / "report.md").read_text(encoding="utf-8")
    lower = report.lower()

    assert "no-advice line" in lower
    assert "no internal terms" in lower
    assert "do not show the internal mechanical model value" in lower
    assert "not financial advice" in lower


def test_mcp_reference_documents_compact_audit_packet_metadata():
    reference = (bundled_skill_dir() / "references" / "mcp-tools.md").read_text(encoding="utf-8")
    lower = reference.lower()

    assert "`auditpacket`" in lower
    assert "valuation_audit_packet.v1" in lower
    assert "visible text block" in lower
    assert "baseline_plausibility" in lower
    assert "assumption_judgment" in lower


def test_scenario_book_summary_documents_visibility_and_mode_boundaries():
    mcp = (bundled_skill_dir() / "references" / "mcp-tools.md").read_text(encoding="utf-8").lower()

    assert "scenario_book.v1" in mcp
    assert "`scenariobook`" in mcp
    assert "mechanical baseline internal-only" in mcp
    assert "market-implied diagnostics diagnostic-only" in mcp
    assert "exactly one user-refined scenario" in mcp


def test_mcp_tool_reference_documents_required_tool_names():
    reference = (bundled_skill_dir() / "references" / "mcp-tools.md").read_text(encoding="utf-8")

    for name in [
        "stockvaluation.health",
        "stockvaluation.value_ticker",
        "stockvaluation.recalculate",
        "stockvaluation.get_assumptions",
        "stockvaluation.get_growth_anchor",
        "stockvaluation.get_reference_data_status",
        "stockvaluation.explain_failure",
    ]:
        assert name in reference


def test_recalculate_reference_documents_researched_payload_contract():
    references = bundled_skill_dir() / "references"
    mcp_reference = (references / "mcp-tools.md").read_text(encoding="utf-8").lower()
    evidence = (references / "evidence-and-judgment.md").read_text(encoding="utf-8").lower()
    workflow = (references / "workflow.md").read_text(encoding="utf-8").lower()

    for term in [
        "segments",
        "sector_overrides",
        "growth_pattern_override",
        "rationale",
        "evidence_used",
    ]:
        assert term in mcp_reference
    assert "keep requested, mapped, unsupported, and effective assumptions separate" in evidence
    assert "auto-recalculate once" in workflow
    assert "ask the user before calling it" not in mcp_reference


def test_skill_docs_require_compact_client_visible_mcp_payloads():
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    mcp_reference = (bundled_skill_dir() / "references" / "mcp-tools.md").read_text(encoding="utf-8").lower()

    assert "keep mcp arguments compact" in skill_text
    assert "call argument hygiene" in mcp_reference
    assert "smallest valid `evidence_packet`" in mcp_reference
    assert "no research logs" in mcp_reference
    assert "never retry with a larger debug object" in mcp_reference


def test_recalculate_reference_does_not_autonomously_change_growth_pattern():
    mcp_reference = (bundled_skill_dir() / "references" / "mcp-tools.md").read_text(encoding="utf-8").lower()
    evidence = (bundled_skill_dir() / "references" / "evidence-and-judgment.md").read_text(encoding="utf-8").lower()

    assert "`growth_pattern_override`" in mcp_reference
    assert "growth pattern" in evidence  # listed in the autonomous explain-only boundary


def test_default_readme_keeps_runtime_guidance_user_facing():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    lower = readme.lower()

    assert "docker desktop or a compatible docker engine with compose" in lower
    assert "docs/runtime-and-data-details.md" not in readme
    assert "sourcequalitygate" not in lower
    assert "sec_user_agent" not in readme
    assert "bullbeargpt" not in lower
    assert "angular" not in lower
    assert "sv value" not in lower
    assert "bootstrap_local_secrets.sh" not in readme


def test_runtime_boundaries_are_documented_in_canonical_sources():
    compose = (REPO_ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")
    mcp_reference = (bundled_skill_dir() / "references" / "mcp-tools.md").read_text(encoding="utf-8")
    workflow_reference = (bundled_skill_dir() / "references" / "workflow.md").read_text(encoding="utf-8")
    method_reference = (bundled_skill_dir() / "references" / "valuation-method.md").read_text(encoding="utf-8")
    field_definitions = (
        REPO_ROOT
        / "valuation-service"
        / "src"
        / "main"
        / "resources"
        / "data"
        / "financial_field_definitions.json"
    )
    combined = "\n".join([compose, mcp_reference, workflow_reference, method_reference])
    lower = combined.lower()

    assert not (REPO_ROOT / "docs" / "runtime-and-data-details.md").exists()
    assert "postgres" in lower
    assert "yfinance" in lower
    assert "valuation-service" in lower
    assert "SEC_USER_AGENT" in compose
    assert "stockvaluation.researched_baseline" in mcp_reference
    assert "sourceQualityGate" in mcp_reference
    assert field_definitions.exists()
    assert "bullbeargpt" not in lower
    assert "angular" not in lower


def test_removed_legacy_product_directories_are_absent():
    for directory in ["frontend", "bullbeargpt", "shared"]:
        assert not (REPO_ROOT / directory).exists()


def test_removed_clawhub_sample_data_is_absent():
    for path in ["clawhub-skills", "assets", "data/stock.json"]:
        assert not (REPO_ROOT / path).exists()

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    for prohibited in ["clawhub", "clawhub-skills", "data/stock.json", "assets/"]:
        assert prohibited not in readme
        assert prohibited not in gitignore


def test_gitignore_keeps_internal_evaluation_outputs_local():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "internal_doc/" in gitignore
    assert "!internal_doc/" not in gitignore
    assert "valuation_skill_eval" not in gitignore


def test_agent_native_code_is_flat_under_valuation_agent_directory():
    package_dir = REPO_ROOT / "valuation-agent"

    assert (package_dir / "cli.py").exists()
    assert (package_dir / "mcp_server.py").exists()
    assert (package_dir / "skills" / "stockvaluation-io" / "SKILL.md").exists()
    assert not (package_dir / "valuation_agent").exists()


def test_valuation_service_source_has_no_legacy_story_runtime_helpers():
    source_root = REPO_ROOT / "valuation-service" / "src" / "main" / "java"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in source_root.rglob("*.java")
    )

    for prohibited in [
        "Python backend",
        "story endpoint",
        "getAuthTokenFromRequest",
        "getValuationOutputWithStory",
        "addStory",
        "NarrativeDTO",
        "CausalScenarioDTO",
        "CausalScenarioResponse",
        "CausalChainDTO",
        "ScenarioAdjustmentsDTO",
        "HeatMapDataDTO",
        "profitabilityStory",
        "riskStory",
        "investmentThesis",
        "WITH STORY",
        "BullBearGPT",
        "Angular",
        "prompt registry",
        "runtime orchestrator",
    ]:
        assert prohibited not in source


def test_compose_exposes_only_agent_native_runtime_services():
    compose = (REPO_ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")
    compose_env_names = set(re.findall(r"^\s+([A-Z][A-Z0-9_]+):", compose, flags=re.MULTILINE))
    compose_var_refs = set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)", compose))
    compose_config_names = compose_env_names | compose_var_refs

    assert "postgres:" in compose
    assert "yfinance:" in compose
    assert "valuation-service:" in compose
    assert "valuation-agent:" not in compose
    assert "bullbeargpt:" not in compose
    assert "frontend:" not in compose
    assert "frontend-node-modules" not in compose
    assert "legacy-orchestration" not in compose
    assert "legacy-bullbeargpt" not in compose
    assert "legacy-ui" not in compose
    assert compose_config_names == {
        "APPLICATION_PORT",
        "CURRENCY_PROVIDER_BASE_URL",
        "DATASOURCE_PASSWORD",
        "DATASOURCE_URL",
        "DATASOURCE_USERNAME",
        "DEFAULT_CONTACT",
        "DEFAULT_FIRSTNAME",
        "DEFAULT_LASTNAME",
        "DEFAULT_PASSWORD",
        "DEFAULT_USERNAME",
        "PORT",
        "POSTGRES_DB",
        "POSTGRES_PASSWORD",
        "POSTGRES_USER",
        "SEC_EDGAR_CACHE_TTL_SECONDS",
        "SEC_EDGAR_ENABLED",
        "SEC_EDGAR_REQUESTS_PER_SECOND",
        "SEC_USER_AGENT",
        "YFINANCE_BASE_URL",
    }
    assert not any(
        name.endswith("_KEY") or "SECRET" in name or "TOKEN" in name or "JWT" in name
        for name in compose_config_names
    )
    assert not any(name.startswith("CORS_") for name in compose_config_names)


def test_compose_uses_keyless_frankfurter_currency_provider():
    compose = (REPO_ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")

    assert "CURRENCY_PROVIDER_BASE_URL: ${CURRENCY_PROVIDER_BASE_URL:-https://api.frankfurter.dev/v2}" in compose
    assert "api.currencybeacon.com" not in compose


def test_env_example_lists_only_agent_native_required_secrets():
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    env_keys = {
        line.split("=", 1)[0]
        for line in env_example.splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    assert "POSTGRES_PASSWORD=" in env_example
    assert "POSTGRES_DB=stockvaluation_io" in env_example
    assert "DEFAULT_PASSWORD=" in env_example
    assert "CURRENCY_PROVIDER_BASE_URL=https://api.frankfurter.dev/v2" in env_example
    assert "bootstrap_local_secrets.sh" not in env_example
    assert env_keys == {
        "CURRENCY_PROVIDER_BASE_URL",
        "DEFAULT_CONTACT",
        "DEFAULT_FIRSTNAME",
        "DEFAULT_LASTNAME",
        "DEFAULT_PASSWORD",
        "DEFAULT_USERNAME",
        "POSTGRES_DB",
        "POSTGRES_PASSWORD",
        "POSTGRES_USER",
        "SEC_EDGAR_CACHE_TTL_SECONDS",
        "SEC_EDGAR_ENABLED",
        "SEC_EDGAR_REQUESTS_PER_SECOND",
        "SEC_USER_AGENT",
    }
    assert not any(
        name.endswith("_KEY") or "SECRET" in name or "TOKEN" in name or "JWT" in name
        for name in env_keys
    )
    assert not any(name.startswith("CORS_") for name in env_keys)

    for prohibited in [
        "api.currencybeacon.com",
        "CORS_ALLOW_ALL",
        "CORS_ORIGINS",
    ]:
        assert prohibited not in env_example


def test_yfinance_config_does_not_keep_stale_env_switches():
    config = (REPO_ROOT / "yfinance" / "config.py").read_text(encoding="utf-8")
    dockerfile = (REPO_ROOT / "yfinance" / "Dockerfile").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "yfinance" / "docker-compose.yml").read_text(encoding="utf-8")
    app = (REPO_ROOT / "yfinance" / "app.py").read_text(encoding="utf-8")
    requirements = (REPO_ROOT / "yfinance" / "requirements.txt").read_text(encoding="utf-8")

    for stale in [
        "CACHE_TTL_HOURS",
        "CORS_ALLOW_ALL",
        "CORS_ORIGINS",
        "ENABLE_REAL_OPTIONS",
        "FLASK_ENV",
        "LOG_LEVEL",
        "Flask-CORS",
        "FeatureFlags",
        "LoggingConfig",
        "flask_cors",
    ]:
        assert stale not in config
        assert stale not in dockerfile
        assert stale not in compose
        assert stale not in app
        assert stale not in requirements

    assert "CACHE_TYPE" in config
    assert "RATE_LIMIT_REQUESTS_PER_SECOND" in config
    assert "RATE_LIMIT_DURATION_SECONDS" in config


def test_sanitize_for_agent_redacts_env_and_nested_secret_values(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "postgres-live-secret")

    payload = {
        "error": "POSTGRES_PASSWORD=postgres-live-secret failed",
        "nested": {
            "password": "postgres-live-secret",
            "safe": "risk-free-rate",
        },
    }

    clean = sanitize_for_agent(payload)

    assert "postgres-live-secret" not in str(clean)
    assert clean["nested"]["password"] == "[REDACTED]"
    assert clean["nested"]["safe"] == "risk-free-rate"
