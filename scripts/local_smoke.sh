#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.local.yml}"
TICKER="${TICKER:-MSFT}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: ./scripts/local_smoke.sh [--agent-native] [--ticker SYMBOL]

Checks the Docker-backed agent-native product path only:
  - yfinance health inside the Docker network
  - valuation-service /{ticker}/valuation endpoint on host :8081
  - valuation-service prospectus challenged-basis quality gate on host :8081
  - MCP stockvaluation.health through stdio
  - MCP stockvaluation.value_ticker through stdio

Options:
  --agent-native  Accepted for compatibility; this is now the only smoke path
  --ticker        Ticker to use for functional checks (default: MSFT)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent-native)
      shift
      ;;
    --ticker)
      TICKER="${2:-}"
      if [[ -z "$TICKER" ]]; then
        echo "Missing value for --ticker" >&2
        exit 2
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

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

need_cmd curl
need_cmd docker
PYTHON_BIN="$(find_python)"
export PYTHONPATH="${ROOT_DIR}/valuation-agent${PYTHONPATH:+:$PYTHONPATH}"

json_status_check() {
  local name="$1"
  local payload_file="$2"
  "$PYTHON_BIN" - "$name" "$payload_file" <<'PY'
import json, sys
name, path = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
if isinstance(data, dict) and data.get("status") in {"healthy", "UP"}:
    print(f"[OK] {name}: status={data.get('status')}")
    sys.exit(0)
print(f"[FAIL] {name}: unexpected payload shape", file=sys.stderr)
print(json.dumps(data, indent=2)[:1000], file=sys.stderr)
sys.exit(1)
PY
}

run_yfinance_health() {
  echo "yfinance health (internal via docker exec)"
  tmp_yf="$(mktemp)"
  docker exec sv-local-yfinance curl -fsS --max-time 10 "http://localhost:5000/health" > "$tmp_yf"
  json_status_check "yfinance" "$tmp_yf"
  rm -f "$tmp_yf"
}

run_valuation_service_check() {
  echo "valuation-service /{ticker}/valuation API (host)"
  tmp_java="$(mktemp)"
  java_code="000"
  curl_rc=1
  for attempt in $(seq 1 30); do
    set +e
    java_code="$(
      curl -sS \
        -o "$tmp_java" \
        -w "%{http_code}" \
        --max-time 120 \
        -H "Content-Type: application/json" \
        -X POST "http://localhost:8081/api/v1/automated-dcf-analysis/${TICKER}/valuation" \
        -d '{}'
    )"
    curl_rc=$?
    set -e
    if [[ "$curl_rc" -eq 0 && "$java_code" == "200" ]]; then
      break
    fi
    if [[ "$attempt" -lt 30 ]]; then
      sleep 2
    fi
  done

  if [[ "$curl_rc" -ne 0 || "$java_code" != "200" ]]; then
    echo "[FAIL] valuation-service baseline DCF returned curl=$curl_rc HTTP $java_code" >&2
    cat "$tmp_java" >&2
    rm -f "$tmp_java"
    exit 1
  fi

  "$PYTHON_BIN" - "$tmp_java" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)
data = payload.get("data", payload)
if not isinstance(data, dict):
    raise SystemExit("[FAIL] valuation-service response missing object payload")
company = data.get("companyDTO") or {}
name = data.get("companyName") or company.get("companyName") or "unknown"
print(f"[OK] valuation-service baseline DCF response for: {name}")
PY
  rm -f "$tmp_java"
}

run_mcp_call_check() {
  local tool="$1"
  local arguments="$2"
  local tmp_mcp
  tmp_mcp="$(mktemp)"
  printf '%s\n' \
    "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"${tool}\",\"arguments\":${arguments}}}" \
    | "$PYTHON_BIN" -m valuation_agent.mcp_server > "$tmp_mcp"
  "$PYTHON_BIN" - "$tmp_mcp" "$tool" <<'PY'
import json, sys
path, tool = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as f:
    response = json.load(f)
result = response.get("result") or {}
structured = result.get("structuredContent") or {}
if structured.get("ok") is not True:
    raise SystemExit(f"[FAIL] {tool} did not return ok=true")
if tool == "stockvaluation.value_ticker":
    dcf = structured.get("dcf") or {}
    if dcf.get("estimatedValuePerShare") is None:
        raise SystemExit("[FAIL] MCP value_ticker missing DCF estimatedValuePerShare")
    print(
        f"[OK] MCP value_ticker ticker={structured.get('ticker')} "
        f"company={dcf.get('companyName')} intrinsic={dcf.get('estimatedValuePerShare')}"
    )
else:
    service = structured.get("service") or {}
    print(f"[OK] {tool}: service status={service.get('status')}")
PY
  rm -f "$tmp_mcp"
}

run_prospectus_quality_check() {
  echo "valuation-service prospectus challenged-basis quality gate (host)"
  local tmp_payload
  local tmp_response
  tmp_payload="$(mktemp)"
  tmp_response="$(mktemp)"
  "$PYTHON_BIN" - "$tmp_payload" <<'PY'
import json, sys

provenance = {
    "sourceClass": "primary_filing",
    "provider": "sec-edgar-prospectus",
    "sourceDate": "2026-06-03",
    "periodEnd": "2025-12-31",
    "retrievalStatus": "retrieved",
    "crossCheckStatus": "not_applicable",
    "sourcePolicyStatus": "prospectus_extracted",
    "warnings": [],
    "dataQualityWarnings": [],
}

def fact(field, label, value):
    return {
        "canonicalField": field,
        "sourceRowLabel": label,
        "originalColumnLabel": "Year Ended December 31, 2025",
        "tableTitle": "Smoke Prospectus Fixture",
        "periodEnd": "2025-12-31",
        "periodType": "annual" if field in {"revenue", "operating_income", "research_and_development"} else "point_in_time",
        "unit": "USD",
        "scale": "actual",
        "rawValue": str(value),
        "normalizedValue": value,
        "confidence": 0.95,
        "sourceProvenance": provenance,
    }

packet = {
    "schemaVersion": "prospectus_financial_packet.v1",
    "reviewStatus": "reviewed",
    "company": {
        "legalName": "Smoke Prospectus Issuer",
        "tickerOrExpectedSymbol": "SMOKE",
        "countryOfIncorporation": "United States",
        "currency": "USD",
        "industryKey": "aerospace-defense",
    },
    "filing": {
        "form": "S-1/A",
        "cik": "0000000000",
        "accession": "0000000000-26-000001",
        "filingDate": "2026-06-03",
    },
    "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm",
    "sourceProvenance": provenance,
    "financials": {
        "incomeStatement": [
            fact("revenue", "Revenue", 1_200_000_000.0),
            fact("operating_income", "Operating income", 120_000_000.0),
            fact("research_and_development", "Research and development", 250_000_000.0),
        ],
        "balanceSheet": [
            fact("cash_and_short_term_investments", "Cash and cash equivalents", 500_000_000.0),
            fact("total_debt", "Total debt", 300_000_000.0),
            fact("book_value_equity", "Total stockholders' equity", 700_000_000.0),
        ],
        "cashFlowOrCapex": [],
    },
    "offering": {
        "offeringPrice": 135.0,
        "offeringPriceBasis": "offering_price",
        "postOfferingShares": 400_000_000.0,
        "shareCountBasis": "pro_forma_post_offering",
    },
    "shareCounts": [
        {
            "basis": "pro_forma_post_offering",
            "sourceRowLabel": "Pro forma as adjusted shares",
            "originalColumnLabel": "Pro forma as adjusted",
            "tableTitle": "Smoke Prospectus Fixture",
            "rawValue": "400000000",
            "normalizedValue": 400_000_000.0,
            "confidence": 0.9,
            "sourceProvenance": provenance,
        }
    ],
    "segments": [],
    "extractionIssues": [],
}
json.dump({"packet": packet}, open(sys.argv[1], "w", encoding="utf-8"))
PY

  local http_code
  http_code="$(
    curl -sS \
      -o "$tmp_response" \
      -w "%{http_code}" \
      --max-time 180 \
      -H "Content-Type: application/json" \
      -X POST "http://localhost:8081/api/v1/prospectus/valuation" \
      -d @"$tmp_payload"
  )"
  if [[ "$http_code" != "200" ]]; then
    echo "[FAIL] prospectus valuation quality fixture returned HTTP $http_code" >&2
    cat "$tmp_response" >&2
    rm -f "$tmp_payload" "$tmp_response"
    exit 1
  fi

  "$PYTHON_BIN" - "$tmp_response" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
data = payload.get("data") if isinstance(payload, dict) else None
if not isinstance(data, dict):
    raise SystemExit("[FAIL] prospectus response missing data object")
basis = data.get("valuationBasisStatus")
case = data.get("valuationCaseStatus")
valuation = data.get("valuation") or {}
transparency = valuation.get("assumptionTransparency") or {}
baseline = transparency.get("baselineUseStatus")
if basis != "pro_forma_cash_missing" or case != "challenged_valuation_case":
    raise SystemExit(f"[FAIL] expected challenged pro-forma basis, got basis={basis} case={case}")
if baseline == "validated_segment_weighted":
    raise SystemExit("[FAIL] challenged prospectus fixture was labeled validated_segment_weighted")
print(f"[OK] prospectus quality gate basis={basis} case={case} baseline={baseline}")
PY
  rm -f "$tmp_payload" "$tmp_response"
}

echo "== Agent-Native Local Smoke Test =="
echo "compose file: $COMPOSE_FILE"
echo "ticker: $TICKER"
echo "[1/5] yfinance health"
run_yfinance_health
echo "[2/5] valuation-service baseline DCF"
run_valuation_service_check
echo "[3/5] prospectus challenged-basis quality gate"
run_prospectus_quality_check
echo "[4/5] MCP health"
run_mcp_call_check "stockvaluation.health" "{}"
echo "[5/5] MCP value_ticker"
run_mcp_call_check "stockvaluation.value_ticker" "{\"ticker\":\"${TICKER}\"}"
echo "Agent-native smoke test passed."
