import json
import re
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
        "search-and-evidence.md",
        "driver-specific-evidence.md",
        "baseline-plausibility.md",
        "guided-valuation-refinement.md",
        "segment-discovery.md",
        "assumption-judgment.md",
        "damodaran-method.md",
        "damodaran-coverage-map.md",
        "damodaran-source-map.md",
        "growth-reinvestment-discipline.md",
        "terminal-value-discipline.md",
        "model-selection-and-lifecycle.md",
        "rd-capitalization-decision.md",
        "risk-currency-country.md",
        "accounting-cleanup.md",
        "options-leases-other-claims.md",
        "segment-quality.md",
        "special-company-stop-rules.md",
        "narrative-report-style.md",
        "report-template.md",
        "no-advice-policy.md",
        "assumption-checks.md",
        "accounting-adjustments.md",
        "troubleshooting.md",
    }

    assert (skill_dir / "SKILL.md").exists()
    assert required.issubset({path.name for path in (skill_dir / "references").iterdir()})


def test_researched_reference_docs_govern_evidence_segments_and_judgment():
    references = bundled_skill_dir() / "references"

    search = (references / "search-and-evidence.md").read_text(encoding="utf-8").lower()
    segments = (references / "segment-discovery.md").read_text(encoding="utf-8").lower()
    judgment = (references / "assumption-judgment.md").read_text(encoding="utf-8")
    judgment_lower = judgment.lower()

    assert "company-domain-first" in search
    assert "source_url" in search
    assert "source_date" in search
    assert "evidence packet" in search
    assert "fresh-context research subagents" in search
    assert "filings_annual_report_research" in search
    assert "earnings_ir_research" in search
    assert "latest_news_research" in search
    assert "segment_evidence_research" in search
    assert "do not return full article text" in search
    assert "baseline_plausibility" in judgment
    assert "do not invent" in segments
    assert "revenue shares" in segments
    assert "latest annual report" in segments
    assert "sec" in segments
    assert "exchange" in segments
    assert '"baseline_assumptions"' in judgment
    assert '"evidence_used"' in judgment
    assert '"dcf_adjustment_instructions"' in judgment
    assert '"sector_adjustment_instructions"' in judgment
    assert "weak, mixed, stale, or uncited" in judgment_lower
    for prohibited in ["wacc", "terminal growth", "tax rate", "cash", "debt", "share count"]:
        assert prohibited in judgment_lower


def test_assumption_judgment_documents_recalculate_payload_mapping():
    judgment = (bundled_skill_dir() / "references" / "assumption-judgment.md").read_text(encoding="utf-8").lower()

    assert "`revenue_cagr` maps to `revenue_growth`" in judgment
    assert "`dcf_adjustment_instructions` map to `stockvaluation.recalculate` overrides" in judgment
    assert "`sector_adjustment_instructions` map to `sector_overrides`" in judgment
    assert "`evidence_used` stays attached to the recalculate metadata" in judgment


def test_main_skill_requires_mcp_json_and_agent_written_educational_report():
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")

    assert "stockvaluation.value_ticker" in skill_text
    assert "Do not hand-compute valuation math" in skill_text
    assert "educational" in skill_text.lower()
    assert "financial advice" in skill_text.lower()
    assert "BullBearGPT" not in skill_text
    assert "Angular" not in skill_text
    assert "sv value" not in skill_text


def test_main_skill_makes_full_researched_valuation_the_default_workflow():
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    lower = skill_text.lower()

    assert "full researched valuation" in lower
    assert "default workflow" in lower
    assert "stockvaluation.health" in skill_text
    assert "stockvaluation.value_ticker" in skill_text
    assert "segment discovery" in lower
    assert "evidence packet" in lower
    assert "assumption_judgment" in skill_text
    assert "auto-recalculate once" in lower
    assert "stockvaluation.recalculate" in skill_text
    assert lower.index("assumption_judgment") < lower.index("stockvaluation.recalculate")


def test_stockvaluation_io_reference_triggers_guided_refinement_by_default():
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
    lower = skill_text.lower()

    assert "whenever the prompt mentions `stockvaluation.io`" in lower
    assert "plain request such as \"value company using stockvaluation.io\"" in lower
    assert "not a quick valuation and not a one-shot report request" in lower
    assert "do not infer a guided-refinement bypass from ordinary phrasing" in lower
    assert "the final report is blocked until guided refinement" in lower
    assert "include a recommended bounded answer for each question" in lower
    assert "do not write the final report in that same response" in lower


def test_full_researched_valuation_delegates_source_heavy_search_to_subagents():
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    search = (bundled_skill_dir() / "references" / "search-and-evidence.md").read_text(encoding="utf-8").lower()

    assert "delegate source-heavy research to fresh-context subagents" in skill_text
    assert "filings/annual reports" in skill_text
    assert "earnings/ir materials" in skill_text
    assert "latest company news" in skill_text
    assert "compact evidence packet" in skill_text
    assert "main agent remains responsible for deciding whether evidence can affect assumptions" in search
    assert "if subagents are unavailable, emulate the same discipline" in search


def test_segment_aware_baseline_docs_define_workflow_statuses_and_schema():
    references = bundled_skill_dir() / "references"
    skill_text = (bundled_skill_dir() / "SKILL.md").read_text(encoding="utf-8").lower()
    segments = (references / "segment-discovery.md").read_text(encoding="utf-8").lower()
    quality = (references / "segment-quality.md").read_text(encoding="utf-8").lower()
    mcp = (references / "mcp-tools.md").read_text(encoding="utf-8").lower()
    report = (references / "report-template.md").read_text(encoding="utf-8").lower()

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
        assert status in report

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
        assert required_field in segments
        assert required_field in mcp

    assert "80%" in quality
    assert "generic source presence is not segment evidence" in quality
    assert "segment names without revenue weights" in quality


def test_report_template_has_no_advice_framing_without_recommendation_phrases():
    template = (bundled_skill_dir() / "references" / "report-template.md").read_text(encoding="utf-8")
    lower = template.lower()

    assert "educational use only" in lower
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


def test_report_template_summarizes_researched_judgment_without_raw_json_dump():
    template = (bundled_skill_dir() / "references" / "report-template.md").read_text(encoding="utf-8")
    lower = template.lower()

    assert "assumption judgment summary" in lower
    assert "evidence packet" in lower
    assert "source date" in lower
    assert "effective assumptions" in lower
    assert "do not print raw `assumption_judgment` json" in lower
    assert "| assumption | baseline | researched change | effective | rationale |" in lower


def test_researched_acceptance_matrix_covers_global_non_financial_workflow_behavior():
    matrix = json.loads(ACCEPTANCE_MATRIX.read_text(encoding="utf-8"))
    companies = matrix["companies"]

    assert matrix["purpose"] == "workflow_acceptance_not_valuation_baselines"
    assert len(companies) == 20
    assert all(company["sector"] != "Financial Services" for company in companies)
    assert all("expected_intrinsic_value" not in company for company in companies)
    assert all("target_price" not in company for company in companies)
    assert sum(company["listing_currency"] != "USD" for company in companies) >= 5
    assert sum(company["primary_listing_country"] != "United States" for company in companies) >= 5
    assert sum(company["segment_discovery"] == "expected" for company in companies) >= 5
    assert sum(company["segment_discovery"] == "simple_or_mostly_single_segment" for company in companies) >= 5

    categories = {category for company in companies for category in company["coverage_categories"]}
    assert {
        "us_large_cap_technology",
        "us_consumer_or_retail",
        "us_industrial_or_healthcare_non_financial",
        "europe_large_cap_industrial_or_consumer",
        "europe_technology_luxury_or_healthcare_non_financial",
        "united_kingdom_non_financial",
        "japan_technology_industrial_or_consumer_non_financial",
        "india_non_financial",
        "taiwan_or_korea_non_financial",
        "canada_australia_brazil_or_other_non_us_region",
    }.issubset(categories)

    required_expectations = {
        "health_check",
        "baseline_dcf_or_classified_failure",
        "segment_discovery",
        "evidence_packet",
        "assumption_judgment",
        "auto_recalculate_once_when_supported",
        "final_educational_report",
    }
    for company in companies:
        assert required_expectations.issubset(set(company["workflow_expectations"]))


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
    assumption_checks = (references / "assumption-checks.md").read_text(encoding="utf-8").lower()

    for term in [
        "segments",
        "sector_overrides",
        "growth_pattern_override",
        "rationale",
        "evidence_used",
        "requested",
        "mapped",
        "unsupported",
        "effective",
    ]:
        assert term in mcp_reference
    assert "auto-recalculate once" in assumption_checks
    assert "ask before recalculating with overrides" not in assumption_checks
    assert "ask the user before calling it" not in mcp_reference


def test_recalculate_reference_does_not_autonomously_change_growth_pattern():
    mcp_reference = (bundled_skill_dir() / "references" / "mcp-tools.md").read_text(encoding="utf-8").lower()

    assert "`growth_pattern_override`" in mcp_reference
    assert "do not use `growth_pattern_override` autonomously" in mcp_reference


def test_default_readme_documents_docker_only_agent_native_runtime():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    lower = readme.lower()

    assert "docker desktop or a compatible docker engine with compose" in lower
    assert "no native java/postgres/yfinance runtime is installed or supported for v1" in lower
    assert "bullbeargpt" not in lower
    assert "angular" not in lower
    assert "sv value" not in lower
    assert "bootstrap_local_secrets.sh" not in readme


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
