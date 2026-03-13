#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8081}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE_DIR="${FIXTURE_DIR:-$SCRIPT_DIR/fixtures/company_matrix_segments}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/company-matrix.XXXXXX")}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need_cmd python3

mkdir -p "$ARTIFACT_DIR"

echo "== Company Matrix Smoke =="
echo "base url: $BASE_URL"
echo "fixtures: $FIXTURE_DIR"
echo "artifacts: $ARTIFACT_DIR"

export BASE_URL FIXTURE_DIR ARTIFACT_DIR
python3 - <<'PY'
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = os.environ["BASE_URL"].rstrip("/")
FIXTURE_DIR = Path(os.environ["FIXTURE_DIR"])
ARTIFACT_DIR = Path(os.environ["ARTIFACT_DIR"])
TIMEOUT_SECONDS = 240

BASELINE_TICKERS = ["KO", "COST", "MCD", "XOM", "NEE", "CAT", "PFE", "ORCL", "ASML", "SAP", "TM", "NVO"]
SEGMENT_TICKERS = ["AAPL", "MSFT", "AMZN", "GOOGL", "NVDA", "TSLA", "DIS", "UBER", "IBM", "SONY", "T", "VZ"]
EXPECTED_FAILURE_TICKERS = ["JPM", "BAC", "GS", "HSBC"]


def safe_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def load_fixture(ticker: str) -> dict[str, Any]:
    path = FIXTURE_DIR / f"{ticker}.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_artifact(case_key: str, status: int, raw_body: str) -> None:
    (ARTIFACT_DIR / f"{case_key}.body.json").write_text(raw_body, encoding="utf-8")
    (ARTIFACT_DIR / f"{case_key}.meta.json").write_text(
        json.dumps({"status": status}, indent=2),
        encoding="utf-8",
    )


def post_valuation(ticker: str, payload: dict[str, Any]) -> tuple[int, str]:
    url = f"{BASE_URL}/api/v1/automated-dcf-analysis/{ticker}/valuation"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.getcode(), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def unwrap_payload(raw_body: str) -> tuple[dict[str, Any] | None, str | None]:
    if "NaN" in raw_body or "Infinity" in raw_body:
        return None, "response contains NaN/Infinity"
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {exc}"
    if not isinstance(payload, dict):
        return None, "top-level payload is not an object"
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return None, "payload data is not an object"
    return data, None


def assert_positive_case(ticker: str, data: dict[str, Any], expects_segments: bool) -> list[str]:
    errors: list[str] = []
    company = data.get("companyDTO")
    financial = data.get("financialDTO")
    transparency = data.get("assumptionTransparency")

    if not isinstance(company, dict) or not company:
        return ["companyDTO missing or empty"]
    if not isinstance(financial, dict) or not financial:
        return ["financialDTO missing or empty"]
    if not isinstance(transparency, dict) or not transparency:
        return ["assumptionTransparency missing or empty"]

    price = safe_number(company.get("price"))
    intrinsic = safe_number(company.get("estimatedValuePerShare"))
    if intrinsic is None:
        errors.append("estimatedValuePerShare missing or non-finite")

    growth_pattern = data.get("growthPattern") or transparency.get("growthPattern")
    projection_years = data.get("projectionYears") or transparency.get("projectionYears")
    template_reason = data.get("templateSelectionReason") or transparency.get("templateSelectionReason")
    if not isinstance(growth_pattern, str) or not growth_pattern:
        errors.append("growthPattern missing")
    if not isinstance(projection_years, int):
        errors.append("projectionYears missing")
    if not isinstance(template_reason, str) or not template_reason.strip():
        errors.append("templateSelectionReason missing")

    if isinstance(growth_pattern, str) and isinstance(projection_years, int):
        expected_projection_years = 15 if growth_pattern == "THREE_STAGE" else 10
        if projection_years != expected_projection_years:
            errors.append(
                f"projectionYears mismatch for growthPattern={growth_pattern}: {projection_years}"
            )

    operating = transparency.get("operatingAssumptions") if isinstance(transparency.get("operatingAssumptions"), dict) else {}
    ebit_margin = financial.get("ebitOperatingMargin") if isinstance(financial.get("ebitOperatingMargin"), list) else []
    year_one_margin = safe_number(ebit_margin[1]) if len(ebit_margin) > 1 else None
    exposed_year_one_margin = safe_number(operating.get("operatingMarginNextYear"))
    if year_one_margin is None or exposed_year_one_margin is None:
        errors.append("year-one operating margin missing")
    elif abs(year_one_margin - exposed_year_one_margin) > 0.25:
        errors.append(
            f"year-one operating margin mismatch: model={year_one_margin:.2f} exposed={exposed_year_one_margin:.2f}"
        )

    target_margin = safe_number(operating.get("targetOperatingMargin"))
    if isinstance(projection_years, int) and target_margin is not None and len(ebit_margin) > projection_years:
        last_projection_margin = safe_number(ebit_margin[projection_years])
        terminal_margin = safe_number(ebit_margin[-1]) if ebit_margin else None
        if last_projection_margin is None or abs(last_projection_margin - target_margin) > 0.25:
            errors.append(
                f"final projected margin mismatch: model={last_projection_margin} exposed={target_margin}"
            )
        if terminal_margin is None or abs(terminal_margin - last_projection_margin) > 0.25:
            errors.append("terminal margin does not match the last projected margin")

    revenues = financial.get("revenues") if isinstance(financial.get("revenues"), list) else []
    invested_capital = financial.get("investedCapital") if isinstance(financial.get("investedCapital"), list) else []
    stc_1_5 = safe_number(operating.get("salesToCapitalYears1To5"))
    if len(revenues) > 0 and len(invested_capital) > 0 and stc_1_5 is not None:
        current_ratio = None
        revenue_0 = safe_number(revenues[0])
        capital_0 = safe_number(invested_capital[0])
        if revenue_0 and capital_0 and capital_0 > 0:
            current_ratio = revenue_0 / capital_0
        if current_ratio is not None and stc_1_5 + 0.05 < current_ratio:
            errors.append(
                f"salesToCapitalYears1To5 below current ratio: exposed={stc_1_5:.2f} current={current_ratio:.2f}"
            )

    if price is not None and intrinsic is not None and intrinsic > 0:
        ratio = (price / intrinsic) * 100.0
        if ratio > 150.0 or ratio < 67.0:
            if growth_pattern != "THREE_STAGE" or projection_years != 15:
                errors.append(
                    f"price/value gap {ratio:.2f}% should force THREE_STAGE but got {growth_pattern}/{projection_years}"
                )
            notes = transparency.get("notes") if isinstance(transparency.get("notes"), list) else []
            if isinstance(template_reason, str) and template_reason.startswith("Forced THREE_STAGE due to price/value gap") and not any(
                "Projection was upgraded to THREE_STAGE" in str(note) for note in notes
            ):
                errors.append("forced THREE_STAGE note missing")

    if expects_segments:
        revenues_by_sector = financial.get("revenuesBySector")
        growth_by_sector = financial.get("revenueGrowthRateBySector")
        if not isinstance(revenues_by_sector, dict) or not revenues_by_sector:
            errors.append("revenuesBySector missing for segment fixture case")
        if not isinstance(growth_by_sector, dict) or not growth_by_sector:
            errors.append("revenueGrowthRateBySector missing for segment fixture case")

    return errors


def assert_expected_failure_case(ticker: str, status: int, raw_body: str) -> list[str]:
    errors: list[str] = []
    if status == 200:
        return ["expected failure but received HTTP 200"]

    data, parse_error = unwrap_payload(raw_body)
    if parse_error:
        return [parse_error]

    reason = None
    for key in ("error", "message", "detail", "reason"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            reason = value.strip()
            break
    if not reason:
        errors.append("expected-failure payload missing explicit error/message/detail/reason")
    return errors


def run_case(ticker: str, payload: dict[str, Any], expects_segments: bool, expect_failure: bool) -> tuple[str, list[str]]:
    status, raw_body = post_valuation(ticker, payload)
    save_artifact(ticker, status, raw_body)

    if expect_failure:
        errors = assert_expected_failure_case(ticker, status, raw_body)
    else:
        if status != 200:
            errors = [f"expected HTTP 200, got {status}"]
        else:
            data, parse_error = unwrap_payload(raw_body)
            errors = [parse_error] if parse_error else assert_positive_case(ticker, data or {}, expects_segments)

    if errors:
        print(f"[FAIL] {ticker}: " + "; ".join(errors))
    else:
        status_label = "expected failure" if expect_failure else "ok"
        print(f"[OK] {ticker}: {status_label}")
    return ticker, errors


results: dict[str, list[str]] = {}

for ticker in BASELINE_TICKERS:
    ticker, errors = run_case(ticker, {}, expects_segments=False, expect_failure=False)
    results[ticker] = errors

for ticker in SEGMENT_TICKERS:
    ticker, errors = run_case(ticker, load_fixture(ticker), expects_segments=True, expect_failure=False)
    results[ticker] = errors

for ticker in EXPECTED_FAILURE_TICKERS:
    ticker, errors = run_case(ticker, {}, expects_segments=False, expect_failure=True)
    results[ticker] = errors

summary = {
    "base_url": BASE_URL,
    "artifact_dir": str(ARTIFACT_DIR),
    "positive_passed": sorted([ticker for ticker in BASELINE_TICKERS + SEGMENT_TICKERS if not results[ticker]]),
    "positive_failed": {ticker: results[ticker] for ticker in BASELINE_TICKERS + SEGMENT_TICKERS if results[ticker]},
    "expected_failure_passed": sorted([ticker for ticker in EXPECTED_FAILURE_TICKERS if not results[ticker]]),
    "expected_failure_failed": {ticker: results[ticker] for ticker in EXPECTED_FAILURE_TICKERS if results[ticker]},
}
(ARTIFACT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

positive_failures = summary["positive_failed"]
expected_failure_failures = summary["expected_failure_failed"]

print("\nSummary:")
print(f"  positive cases passed: {len(summary['positive_passed'])}/{len(BASELINE_TICKERS) + len(SEGMENT_TICKERS)}")
print(f"  expected failures passed: {len(summary['expected_failure_passed'])}/{len(EXPECTED_FAILURE_TICKERS)}")
print(f"  artifacts: {ARTIFACT_DIR}")

if positive_failures or expected_failure_failures:
    sys.exit(1)
PY
