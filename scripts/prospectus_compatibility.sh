#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

find_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  echo "Missing required command: python3.11 or python3" >&2
  exit 1
}

PYTHON_BIN="$(find_python)"
cd "$ROOT_DIR"
"$PYTHON_BIN" - "$@" <<'PY'
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from urllib import error, parse, request


DEFAULT_LIMIT = 15
DEFAULT_FIXTURE = "valuation-service/src/test/resources/prospectus/spacex_s1a_trimmed.html"
PROSPECTUS_FORMS = ("S-1", "S-1/A", "424B3", "424B4", "424B5")
SEED_CIKS = [
    "1713445",  # Reddit
    "1579091",  # Maplebear / Instacart
    "1835830",  # Klaviyo
    "1973239",  # Arm Holdings
    "1639438",  # CAVA
    "1874178",  # Rivian
    "1315098",  # Roblox
    "1679788",  # Coinbase
    "1783879",  # Robinhood
    "1640147",  # Snowflake
    "1559720",  # Airbnb
    "1792789",  # DoorDash
    "1562088",  # Duolingo
    "1653482",  # GitLab
    "1650164",  # Toast
    "1607939",  # Udemy
    "1841666",  # Warby Parker
    "1843181",  # F45 Training
]


@dataclass(frozen=True)
class FilingCandidate:
    company: str
    cik: str
    form: str
    filing_date: str
    accession_number: str
    primary_document: str
    url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a compact prospectus extraction compatibility pass over SEC prospectus filings.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the deterministic 15-document report shape without network or service calls.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Number of prospectus documents to process; must be at least 15 for release use.")
    parser.add_argument("--service-url", default=os.getenv("STOCKVALUATION_PROSPECTUS_EXTRACT_URL", ""), help="Prospectus extraction endpoint. Defaults to the local service.")
    parser.add_argument("--sec-user-agent", default=os.getenv("SEC_USER_AGENT", ""), help="Declared SEC User-Agent for live SEC requests.")
    parser.add_argument("--cik", action="append", default=[], help="Additional CIK seed to search for S-1/S-1/A/424B filings.")
    parser.add_argument("--parser-bug", action="append", default=[], help="Parser bug fixed during this compatibility pass.")
    parser.add_argument("--fixture", action="append", default=[], help="Fixture added during this compatibility pass.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        print("limit must be positive", file=sys.stderr)
        return 2
    target = max(args.limit, DEFAULT_LIMIT)
    fixtures = args.fixture or [DEFAULT_FIXTURE]
    bugs = args.parser_bug or ["none recorded by script"]

    if args.dry_run:
        docs = dry_run_candidates(target)
        print_report(
            mode="dry-run",
            target=target,
            results=[{"candidate": doc, "ok": True, "status": "planned"} for doc in docs],
            parser_bugs=bugs,
            fixtures=fixtures,
            final="DRY_RUN",
        )
        return 0

    user_agent = args.sec_user_agent.strip()
    if not user_agent or user_agent.upper() in {"CHANGE_ME", "TODO"}:
        print("SEC_USER_AGENT is required for live SEC compatibility runs.", file=sys.stderr)
        return 2

    endpoint = args.service_url.strip() or derive_extract_endpoint(os.getenv("STOCKVALUATION_SERVICE_URL", ""))
    seeds = dedupe([*args.cik, *SEED_CIKS])
    candidates = discover_candidates(seeds, target, user_agent)
    results = [process_candidate(endpoint, candidate) for candidate in candidates[:target]]
    final = "PASS" if len(results) >= target and all(result["ok"] for result in results) else "FAIL"
    print_report(
        mode="live",
        target=target,
        results=results,
        parser_bugs=bugs,
        fixtures=fixtures,
        final=final,
    )
    return 0 if final == "PASS" else 1


def derive_extract_endpoint(configured: str) -> str:
    if configured:
        parsed = parse.urlsplit(configured.rstrip("/"))
        marker = "/api/v1"
        path = parsed.path or marker
        if marker in path:
            root = path[: path.index(marker) + len(marker)]
        else:
            root = marker
        return parse.urlunsplit((parsed.scheme, parsed.netloc, f"{root}/prospectus/extract", "", ""))
    return "http://localhost:8081/api/v1/prospectus/extract"


def dry_run_candidates(target: int) -> list[FilingCandidate]:
    docs: list[FilingCandidate] = []
    for index, cik in enumerate(SEED_CIKS[:target], start=1):
        accession = f"0000000000-26-{index:06d}"
        accession_path = accession.replace("-", "")
        primary = f"d{index:06d}ds1.htm"
        docs.append(
            FilingCandidate(
                company=f"planned prospectus seed {index}",
                cik=cik,
                form="S-1",
                filing_date="dry-run",
                accession_number=accession,
                primary_document=primary,
                url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{primary}",
            )
        )
    return docs


def discover_candidates(ciks: list[str], target: int, user_agent: str) -> list[FilingCandidate]:
    candidates: list[FilingCandidate] = []
    seen: set[str] = set()
    for cik in ciks:
        root = fetch_json(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", user_agent)
        company = str(root.get("name") or f"CIK {int(cik)}")
        collect_from_filing_block(candidates, seen, company, str(int(cik)), root.get("filings", {}).get("recent", {}))
        for file_ref in root.get("filings", {}).get("files", [])[:8]:
            name = file_ref.get("name") if isinstance(file_ref, dict) else None
            if not name:
                continue
            older = fetch_json(f"https://data.sec.gov/submissions/{name}", user_agent)
            collect_from_filing_block(candidates, seen, company, str(int(cik)), older)
            if len(candidates) >= target:
                break
        if len(candidates) >= target:
            break
    return candidates


def collect_from_filing_block(
    candidates: list[FilingCandidate],
    seen: set[str],
    company: str,
    cik: str,
    block: dict,
) -> None:
    forms = block.get("form") or []
    accession_numbers = block.get("accessionNumber") or []
    filing_dates = block.get("filingDate") or []
    primary_documents = block.get("primaryDocument") or []
    for index, form in enumerate(forms):
        form = str(form)
        if not is_prospectus_form(form):
            continue
        accession = safe_at(accession_numbers, index)
        primary = safe_at(primary_documents, index)
        if not accession or not primary.lower().endswith((".htm", ".html")):
            continue
        url = sec_archive_url(cik, accession, primary)
        if url in seen:
            continue
        seen.add(url)
        candidates.append(
            FilingCandidate(
                company=company,
                cik=cik,
                form=form,
                filing_date=safe_at(filing_dates, index) or "unknown",
                accession_number=accession,
                primary_document=primary,
                url=url,
            )
        )


def is_prospectus_form(form: str) -> bool:
    return form in PROSPECTUS_FORMS


def safe_at(values: list, index: int) -> str:
    try:
        value = values[index]
    except (IndexError, TypeError):
        return ""
    return str(value or "")


def sec_archive_url(cik: str, accession: str, primary: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{primary}"


def fetch_json(url: str, user_agent: str) -> dict:
    req = request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    time.sleep(0.12)
    with request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def process_candidate(endpoint: str, candidate: FilingCandidate) -> dict:
    body = json.dumps({"filing_url": candidate.url, "expected_company": candidate.company}).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        return {"candidate": candidate, "ok": False, "status": f"http_{exc.code}", "detail": exc.read().decode("utf-8", errors="replace")[:240]}
    except Exception as exc:
        return {"candidate": candidate, "ok": False, "status": "request_failed", "detail": str(exc)[:240]}

    data = payload.get("data") if isinstance(payload, dict) else None
    packet = data.get("packet") if isinstance(data, dict) else None
    status = data.get("status") if isinstance(data, dict) else "missing_data"
    review_status = packet.get("reviewStatus") if isinstance(packet, dict) else None
    fact_count = packet_fact_count(packet)
    issue_codes = packet_issue_codes(packet)
    valuation_ready = packet_is_valuation_ready(packet)
    provenance = packet.get("sourceProvenance") if isinstance(packet, dict) else {}
    source_class = provenance.get("sourceClass") if isinstance(provenance, dict) else None
    provider = provenance.get("provider") if isinstance(provenance, dict) else None
    provenance_ok = source_class == "primary_filing" and provider == "sec-edgar-prospectus"
    empty_packet = packet_is_empty(packet)
    silent_empty = empty_packet and not issue_codes
    has_packet_substance = fact_count > 0 or bool(issue_codes)
    ok = (
        status == "requires_review"
        and review_status == "review_required"
        and provenance_ok
        and has_packet_substance
        and not silent_empty
    )
    issue_summary = ",".join(issue_codes) if issue_codes else "none"
    detail = (
        f"facts={fact_count} issues={issue_summary} "
        f"valuation_ready={str(valuation_ready).lower()} "
        f"provenance={source_class or 'missing'}/{provider or 'missing'}"
    )
    reason = " silent_empty" if silent_empty else (" typed_empty" if empty_packet else "")
    return {"candidate": candidate, "ok": ok, "status": f"{status}/{review_status or 'missing_review'} {detail}{reason}"}


def packet_fact_count(packet: dict | None) -> int:
    if not isinstance(packet, dict):
        return 0
    financials = packet.get("financials") if isinstance(packet.get("financials"), dict) else {}
    count = 0
    for key in (
        "incomeStatement",
        "balanceSheet",
        "cashFlow",
        "cashFlowOrCapex",
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "cash_flow_or_capex",
    ):
        values = financials.get(key)
        if isinstance(values, list):
            count += len(values)
    return count


def packet_issue_codes(packet: dict | None) -> list[str]:
    if not isinstance(packet, dict):
        return ["missing_packet"]
    issues = packet.get("extractionIssues") or packet.get("extraction_issues") or []
    if not isinstance(issues, list):
        return ["invalid_issues"]
    codes: list[str] = []
    for issue in issues:
        if isinstance(issue, dict):
            code = issue.get("code")
            if code:
                codes.append(str(code))
    return codes


def packet_is_empty(packet: dict | None) -> bool:
    if not isinstance(packet, dict):
        return True
    offering = packet.get("offering") if isinstance(packet.get("offering"), dict) else {}
    share_counts = packet.get("shareCounts") or packet.get("share_counts") or []
    segments = packet.get("segments") or []
    return (
        packet_fact_count(packet) == 0
        and not share_counts
        and not segments
        and not offering.get("offeringPrice")
        and not offering.get("offering_price")
    )


def packet_is_valuation_ready(packet: dict | None) -> bool:
    if not isinstance(packet, dict):
        return False
    filing = packet.get("filing") if isinstance(packet.get("filing"), dict) else {}
    form = filing.get("form") or filing.get("formType") or filing.get("form_type")
    if form not in PROSPECTUS_FORMS:
        return False
    if not packet_has_fact(packet, "revenue"):
        return False
    offering = packet.get("offering") if isinstance(packet.get("offering"), dict) else {}
    if not (offering.get("offeringPrice") or offering.get("offering_price")):
        return False
    share_counts = packet.get("shareCounts") or packet.get("share_counts") or []
    if not share_counts and not (offering.get("postOfferingShares") or offering.get("post_offering_shares")):
        return False
    issues = packet.get("extractionIssues") or packet.get("extraction_issues") or []
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict) and issue.get("severity") == "blocking":
                return False
    return True


def packet_has_fact(packet: dict, canonical_field: str) -> bool:
    financials = packet.get("financials") if isinstance(packet.get("financials"), dict) else {}
    for key in (
        "incomeStatement",
        "balanceSheet",
        "cashFlow",
        "cashFlowOrCapex",
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "cash_flow_or_capex",
    ):
        values = financials.get(key)
        if not isinstance(values, list):
            continue
        for fact in values:
            if isinstance(fact, dict) and fact.get("canonicalField") == canonical_field:
                value = fact.get("normalizedValue")
                if isinstance(value, (int, float)) and value == value:
                    return True
    return False


def print_report(
    *,
    mode: str,
    target: int,
    results: list[dict],
    parser_bugs: list[str],
    fixtures: list[str],
    final: str,
) -> None:
    print("== Prospectus Compatibility Report ==")
    print(f"mode: {mode}")
    print(f"required minimum: {target}")
    print(f"documents tested: {len(results)}")
    print("extraction statuses:")
    for index, result in enumerate(results, start=1):
        candidate = result["candidate"]
        status = result["status"]
        marker = "OK" if result["ok"] else "FAIL"
        print(f"- [{marker}] {index:02d} {candidate.form} {candidate.cik} {candidate.filing_date} {status} {candidate.url}")
    print("parser bugs fixed:")
    for bug in parser_bugs:
        print(f"- {bug}")
    print("fixtures added:")
    for fixture in fixtures:
        print(f"- {fixture}")
    print(f"final: {final}")


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


if __name__ == "__main__":
    raise SystemExit(main())
PY
