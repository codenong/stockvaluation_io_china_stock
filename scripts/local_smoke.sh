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

invalid_python_runtime() {
  echo "[FAIL] INVALID_PYTHON_RUNTIME: $1" >&2
  exit 1
}

validate_python_runtime() {
  local candidate="${STOCKVALUATION_PYTHON_BIN:-}"
  if [[ -z "$candidate" ]]; then
    invalid_python_runtime "STOCKVALUATION_PYTHON_BIN must name an absolute Python 3.11 executable"
  fi
  if [[ "$candidate" != /* ]]; then
    invalid_python_runtime "STOCKVALUATION_PYTHON_BIN must be absolute: $candidate"
  fi
  if [[ ! -e "$candidate" ]]; then
    invalid_python_runtime "runtime does not exist: $candidate"
  fi
  if [[ ! -x "$candidate" ]]; then
    invalid_python_runtime "runtime is not executable: $candidate"
  fi
  local version
  version="$("$candidate" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null || true)"
  if [[ ! "$version" =~ ^3\.11\. ]]; then
    invalid_python_runtime "expected Python 3.11.x from $candidate, got ${version:-unreadable}"
  fi
  PYTHON_BIN="$candidate"
  echo "[OK] Python runtime: $PYTHON_BIN ($version)"
}

validate_python_runtime
need_cmd curl
need_cmd docker
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

run_mcp_guided_reasoning_check() {
  echo "MCP semantic guided reasoning conformance"
  "$PYTHON_BIN" - "$TICKER" <<'PY'
import copy
import json
import os
import subprocess
import sys

from valuation_agent.conformance import build_conformance_record, diff_conformance_records
from valuation_agent.workflow_run_state import WorkflowRunStore

ticker = sys.argv[1]

EVIDENCE_ITEMS = [
    {
        "evidence_id": "demand",
        "driver": "revenue_growth",
        "source_title": "Customer cohort memo",
        "source_url": "https://example.com/demand",
        "source_date": "2026-05-01",
        "evidence_summary": "Renewal demand is recurring.",
        "confidence": "high",
    },
    {
        "evidence_id": "margin",
        "driver": "operating_margin",
        "source_title": "Margin bridge",
        "source_url": "https://example.com/margin",
        "source_date": "2026-05-02",
        "evidence_summary": "Margins are normalizing.",
        "confidence": "high",
    },
    {
        "evidence_id": "capital",
        "driver": "reinvestment_sales_to_capital",
        "source_title": "Capital plan",
        "source_url": "https://example.com/capital",
        "source_date": "2026-05-03",
        "evidence_summary": "Growth needs heavier reinvestment.",
        "confidence": "high",
    },
    {
        "evidence_id": "risk",
        "driver": "risk_wacc",
        "source_title": "Risk review",
        "source_url": "https://example.com/risk",
        "source_date": "2026-05-04",
        "evidence_summary": "Execution risk is elevated.",
        "confidence": "high",
    },
]


def framing_fork(fork_id, driver, question, refs, options):
    return {
        "schema_version": "framing_fork.v1",
        "fork_id": fork_id,
        "primary_driver": driver,
        "causal_question": question,
        "confidence": "high",
        "material": True,
        "supporting_evidence_refs": refs,
        "opposing_evidence_refs": [],
        "evidence_gaps": ["No direct falsifier data is disclosed."],
        "options": [{"label": label, "story": story, "falsifier": falsifier} for label, story, falsifier in options],
        "analysis_lean": "B",
    }


FRAMING_FORKS = [
    framing_fork(
        "growth_durability",
        "revenue_growth",
        "Is demand recurring or pulled forward?",
        ["demand"],
        [
            ("A", "Recurring demand expands.", "Renewals weaken."),
            ("B", "Demand normalizes.", "Backlog stalls."),
            ("C", "Demand was pulled forward.", "New workloads fail to replace churn."),
        ],
    ),
    framing_fork(
        "margin_path",
        "operating_margin",
        "Are margins normalizing or structurally capped?",
        ["margin"],
        [
            ("A", "Margins stay capped.", "Cost discipline appears."),
            ("B", "Margins normalize.", "Fixed costs rise again."),
            ("C", "Margins expand faster.", "Pricing pressure returns."),
        ],
    ),
    framing_fork(
        "reinvestment_intensity",
        "reinvestment_sales_to_capital",
        "Does growth need heavier reinvestment?",
        ["capital"],
        [
            ("A", "Capital efficiency improves.", "Capacity additions lag revenue."),
            ("B", "Reinvestment stays near base.", "Working capital absorbs growth."),
            ("C", "Growth needs heavier reinvestment.", "Asset turns improve."),
        ],
    ),
    framing_fork(
        "risk_discount",
        "risk_wacc",
        "Is base risk enough for execution uncertainty?",
        ["risk"],
        [
            ("A", "Base risk is enough.", "Launch failures increase."),
            ("B", "Risk needs a modest premium.", "Execution volatility falls."),
            ("C", "Risk needs a large premium.", "Delivery metrics stabilize."),
        ],
    ),
]

ANSWERS = {
    "semantic_growth_durability": "A",
    "semantic_margin_path": "B",
    "semantic_reinvestment_intensity": "C",
    "semantic_risk_discount": {"choice": "D", "value": 9.2},
}


class MCPStdioClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "valuation_agent.mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )
        self.next_id = 1

    def call(self, tool, args):
        request_id = self.next_id
        self.next_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }
        assert self.proc.stdin is not None
        assert self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            stderr = self.proc.stderr.read() if self.proc.stderr is not None else ""
            raise SystemExit(f"[FAIL] {tool} produced no JSON-RPC response: {stderr[:2000]}")
        response = json.loads(line)
        if response.get("error"):
            raise SystemExit(f"[FAIL] {tool} JSON-RPC error: {json.dumps(response['error'], sort_keys=True)}")
        result = response.get("result") or {}
        structured = result.get("structuredContent") or {}
        if result.get("isError") or structured.get("ok") is not True:
            raise SystemExit(f"[FAIL] {tool} failed: {json.dumps(structured, sort_keys=True)[:4000]}")
        return structured

    def close(self):
        if self.proc.stdin is not None:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)


def stable(value):
    return json.loads(json.dumps(value, sort_keys=True))


def run_replay(name):
    client = MCPStdioClient()
    try:
        baseline = client.call("stockvaluation.value_ticker", {"ticker": ticker})
        run_id = baseline.get("run_id")
        if not run_id:
            raise SystemExit("[FAIL] MCP value_ticker did not create a tracked run")
        plan_payload = client.call(
            "stockvaluation.plan_guided_questions",
            {
                "run_id": run_id,
                "gate_records": [{"gate": "evidence_review", "outcome": "approved"}],
                "company": baseline.get("dcf", {}).get("companyName") or ticker,
                "ticker": ticker,
                "workflow_type": "ticker",
                "evidence_items": EVIDENCE_ITEMS,
                "framing_forks": FRAMING_FORKS,
            },
        )
        plan = plan_payload["guidedQuestionPlan"]
        accepted = plan.get("framing_fork_validation", {}).get("accepted_forks", [])
        accepted_drivers = [fork.get("primary_driver") for fork in accepted]
        expected_drivers = ["revenue_growth", "operating_margin", "reinvestment_sales_to_capital", "risk_wacc"]
        if accepted_drivers != expected_drivers:
            raise SystemExit(f"[FAIL] semantic framing forks not accepted: {accepted_drivers}")
        apply_payload = client.call(
            "stockvaluation.apply_guided_answers",
            {"run_id": run_id, "answers": copy.deepcopy(ANSWERS)},
        )
        coherence = apply_payload.get("coherenceReview") or {}
        challenge_count = int(apply_payload.get("challenge_count") or 0)
        if coherence.get("status") not in {"clean", "resolved_by_changed_answers", "caveat_accepted"}:
            if challenge_count > 1:
                raise SystemExit(f"[FAIL] coherence required more than one challenge: {coherence}")
            apply_payload = client.call(
                "stockvaluation.apply_guided_answers",
                {
                    "run_id": run_id,
                    "answers": copy.deepcopy(ANSWERS),
                    "accept_coherence_caveat": True,
                    "coherence_caveat_reason": "Accepted for deterministic smoke replay.",
                },
            )
            coherence = apply_payload.get("coherenceReview") or {}
            challenge_count = int(apply_payload.get("challenge_count") or 0)
        if coherence.get("status") not in {"clean", "resolved_by_changed_answers", "caveat_accepted"}:
            raise SystemExit(f"[FAIL] coherence not resolved: {coherence}")
        if challenge_count > 1:
            raise SystemExit(f"[FAIL] too many coherence challenges: {challenge_count}")
        guided_record = apply_payload.get("guidedAnswerRecord") or {}
        expected_fields = {"revenue_growth", "target_operating_margin", "sales_to_capital", "wacc"}
        if set(guided_record) != expected_fields:
            raise SystemExit(f"[FAIL] guided answer record fields differ: {sorted(guided_record)}")
        for field, record in guided_record.items():
            if record.get("selected_choice") is None or record.get("value") is None:
                raise SystemExit(f"[FAIL] guided answer record missing choice/value for {field}: {record}")
        recalc_overrides = copy.deepcopy(apply_payload["tickerOverridesCandidate"]["overrides"])
        if "wacc" in guided_record:
            recalc_overrides["request_policy"] = {"mode": "explicit_scenario"}
        recalc_payload = client.call(
            "stockvaluation.recalculate",
            {
                "run_id": run_id,
                "ticker": ticker,
                "overrides": recalc_overrides,
            },
        )
    finally:
        client.close()

    run = WorkflowRunStore().get_run(run_id)
    if not isinstance(run, dict):
        raise SystemExit(f"[FAIL] persisted run not found: {run_id}")
    record = build_conformance_record(run, value_per_share=recalc_payload["dcf"]["estimatedValuePerShare"])
    thesis = stable(apply_payload["revealedThesis"])
    thesis_copies = [
        ("run.revealed_thesis", run.get("revealed_thesis")),
        ("recalculate.structuredContent.revealedThesis", recalc_payload.get("revealedThesis")),
        (
            "recalculate.structuredContent.auditPacket.packet.revealed_thesis",
            recalc_payload.get("auditPacket", {}).get("packet", {}).get("revealed_thesis"),
        ),
        (
            "recalculate.structuredContent.scenarioBook.book.revealed_thesis",
            recalc_payload.get("scenarioBook", {}).get("book", {}).get("revealed_thesis"),
        ),
        ("record.revealed_thesis", record.get("revealed_thesis")),
    ]
    for label, value in thesis_copies:
        if stable(value) != thesis:
            raise SystemExit(f"[FAIL] revealed thesis copy mismatch at {label}")
    if record.get("schema_version") != "conformance_record.v1":
        raise SystemExit(f"[FAIL] conformance record schema mismatch: {record.get('schema_version')}")
    if stable(record["revealed_thesis"]) != thesis:
        raise SystemExit("[FAIL] conformance record omitted revealed thesis")
    if record.get("coherence_challenge_count", 0) > 1:
        raise SystemExit(f"[FAIL] record coherence challenge count too high: {record.get('coherence_challenge_count')}")
    print(
        f"[OK] MCP guided replay {name}: accepted_forks={len(accepted)} "
        f"guided_fields={','.join(sorted(guided_record))} coherence={coherence.get('status')} "
        f"challenges={challenge_count} intrinsic={recalc_payload['dcf']['estimatedValuePerShare']}"
    )
    return record


record_a = run_replay("first")
record_b = run_replay("second")
diff = diff_conformance_records(record_a, record_b)
if diff != {"identical": True, "differences": []}:
    raise SystemExit(f"[FAIL] identical replay diff failed: {json.dumps(diff, sort_keys=True)}")
mutated = stable(record_a)
mutated["revealed_thesis"]["decisions"][0]["selected_interpretation"] = "Changed interpretation."
mutation_diff = diff_conformance_records(record_a, mutated)
expected_path = "revealed_thesis.decisions[0].interpretation"
if mutation_diff["differences"] != [
    {
        "path": expected_path,
        "first": record_a["revealed_thesis"]["decisions"][0]["selected_interpretation"],
        "second": "Changed interpretation.",
    }
]:
    raise SystemExit(f"[FAIL] mutation diff path failed: {json.dumps(mutation_diff, sort_keys=True)}")
print(f"[OK] MCP conformance replay diff identical=true mutation_path={expected_path} thesis_copies=6")
PY
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
echo "[1/6] yfinance health"
run_yfinance_health
echo "[2/6] valuation-service baseline DCF"
run_valuation_service_check
echo "[3/6] prospectus challenged-basis quality gate"
run_prospectus_quality_check
echo "[4/6] MCP health"
run_mcp_call_check "stockvaluation.health" "{}"
echo "[5/6] MCP value_ticker"
run_mcp_call_check "stockvaluation.value_ticker" "{\"ticker\":\"${TICKER}\"}"
echo "[6/6] MCP semantic guided reasoning"
run_mcp_guided_reasoning_check
echo "Agent-native smoke test passed."
