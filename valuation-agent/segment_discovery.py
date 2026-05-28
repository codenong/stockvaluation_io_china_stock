"""Segment discovery helpers for agent-native researched valuations."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

OFFICIAL_SUBDOMAINS = (
    "investor",
    "investors",
    "ir",
    "investorrelations",
    "investor-relations",
    "corporate",
    "about",
    "company",
    "newsroom",
    "annualreport",
    "annualreports",
)

FALLBACK_SEGMENT_DOMAINS = [
    "sec.gov",
    "edgar.sec.gov",
    "annualreports.com",
    "nasdaq.com",
    "nyse.com",
]

GENERIC_SOURCE_MARKERS = ("found", "available", "captured")


def build_segment_search_plan(
    *,
    company_name: str,
    ticker: str = "",
    company_url: str = "",
    industry: str = "",
    description: str = "",
) -> dict[str, object]:
    """Build deterministic search inputs for official segment disclosure lookup."""
    company = company_name.strip()
    ticker = ticker.strip().upper()
    domains = company_domains(company_url, ticker)
    context_terms = [term for term in [company, ticker, industry.strip()] if term]
    exact_company = f'"{company}"' if company else ticker
    query = (
        f'{exact_company} ("segment revenue" OR "revenue by segment" OR '
        f'"reportable segments" OR "operating segments") ("10-K" OR "annual report" OR "segment information")'
    )
    if len(query) > 400:
        query = query[:397].rstrip() + "..."
    return {
        "company": company,
        "ticker": ticker,
        "industry": industry.strip(),
        "description": description.strip()[:500],
        "domains": domains,
        "fallback_domains": FALLBACK_SEGMENT_DOMAINS,
        "queries": [
            {
                "name": "official_segment_revenue",
                "query": query,
                "preferred_domains": domains,
                "fallback_domains": FALLBACK_SEGMENT_DOMAINS,
                "context_terms": context_terms,
            }
        ],
    }


def company_domains(company_url: str, ticker: str = "") -> list[str]:
    """Return company and IR domains in the priority order used for segment search."""
    base_domain = normalize_domain(company_url)
    if not base_domain:
        return []
    domains = [base_domain]
    domains.extend(f"{subdomain}.{base_domain}" for subdomain in OFFICIAL_SUBDOMAINS)
    ticker_lower = ticker.strip().lower()
    if ticker_lower and ticker_lower not in base_domain:
        domains.extend([f"{ticker_lower}.com", f"investor.{ticker_lower}.com", f"ir.{ticker_lower}.com"])
    return dedupe(domains)


def sanitize_segment_package(
    payload: dict[str, object],
    *,
    coverage_threshold: float = 0.80,
) -> dict[str, object]:
    """Validate a discovered segment package before it can affect the baseline."""
    raw_segments = payload.get("segments") if isinstance(payload, dict) else None
    warnings: list[str] = []
    sanitized: list[dict[str, object]] = []
    mapping_blocked = False

    if not isinstance(raw_segments, list) or not raw_segments:
        return segment_validation_result(
            "single_industry_fallback",
            [],
            0.0,
            ["No segment package was provided."],
        )

    for raw in raw_segments:
        if not isinstance(raw, dict):
            warnings.append("Invalid segment entry ignored.")
            continue
        source_name = str(raw.get("source_name") or raw.get("sourceName") or "").strip()
        if is_generic_source_presence(source_name):
            warnings.append("generic source presence is not segment evidence.")
            if parse_revenue_weight(raw) is None:
                warnings.append("Segment names without revenue weights are report-only; revenue weights or amounts are required.")
            continue
        source_date = str(raw.get("source_date") or raw.get("sourceDate") or "").strip()
        source_url = str(
            raw.get("source_url")
            or raw.get("sourceUrl")
            or raw.get("source_reference")
            or raw.get("sourceReference")
            or ""
        ).strip()
        if not source_name or not source_date or not source_url:
            warnings.append("Segment source metadata must include source name, source date, and source URL/reference.")
            continue
        revenue_weight = parse_revenue_weight(raw)
        if revenue_weight is None:
            warnings.append("Segment names without revenue weights are report-only; revenue weights or amounts are required.")
            continue
        segment_name = str(raw.get("segment_name") or raw.get("name") or raw.get("segment") or "").strip()
        mapped_industry = str(raw.get("mapped_industry") or raw.get("industry") or "").strip()
        if not segment_name or not mapped_industry:
            warnings.append("Segment name and mapped industry are required for baseline use.")
            mapping_blocked = True
            continue
        mapping_confidence = str(raw.get("mapping_confidence") or raw.get("mappingConfidence") or "").strip()
        mapping_score = numeric_or_none(raw.get("mapping_score") or raw.get("mappingScore"))
        if mapping_confidence.lower() not in {"medium", "high"} and (mapping_score is None or mapping_score < 0.55):
            warnings.append("Segment mapping confidence is too low for baseline use.")
            mapping_blocked = True
            continue
        sanitized.append(
            {
                "segment_name": segment_name,
                "revenue_weight": revenue_weight,
                "source_name": source_name,
                "source_date": source_date,
                "source_url": source_url,
                "mapped_industry": mapped_industry,
                "mapping_confidence": mapping_confidence,
                "validation_warnings": list(raw.get("validation_warnings") or raw.get("validationWarnings") or []),
            }
        )

    coverage = sum(float(segment["revenue_weight"]) for segment in sanitized)
    if coverage >= 1.5:
        coverage = coverage / 100.0
    if coverage < coverage_threshold:
        if mapping_blocked:
            return segment_validation_result("segment_mapping_blocked", [], coverage, warnings)
        return segment_validation_result("segment_evidence_insufficient", [], coverage, warnings)
    return segment_validation_result("segment_weighted_baseline", sanitized, coverage, warnings)


def segment_validation_result(
    baseline_quality: str,
    segments: list[dict[str, object]],
    coverage: float,
    warnings: list[str],
) -> dict[str, object]:
    return {
        "baseline_quality": baseline_quality,
        "segment_aware": baseline_quality == "segment_weighted_baseline",
        "segment_coverage_pct": round(max(0.0, coverage) * 100.0, 2),
        "segments": segments,
        "validation_warnings": dedupe(warnings),
    }


def parse_revenue_weight(raw: dict[str, object]) -> float | None:
    for key in ("revenue_weight", "revenueWeight", "revenue_share", "revenueShare"):
        value = raw.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number > 1.5:
            number = number / 100.0
        return number if number > 0 else None
    return None


def is_generic_source_presence(source_name: str) -> bool:
    lowered = source_name.lower()
    return any(marker in lowered for marker in GENERIC_SOURCE_MARKERS)


def numeric_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_domain(company_url: str) -> str:
    raw = (company_url or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlsplit(raw)
    domain = parsed.netloc or parsed.path
    domain = re.sub(r"^www\.", "", domain).strip("/")
    return domain


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
