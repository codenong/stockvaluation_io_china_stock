#!/usr/bin/env python3
"""Live-tier conformance replay: one independent all-default SpaceX run.

Runs the fixed replay scenario from issues/prd.md (M6) against the live
valuation service in a fresh process: extract the SpaceX S-1/A, approve the
evidence review, plan guided questions, accept every default, and run the
final deterministic scenario valuation. Emits the run's conformance record
as JSON on stdout.

Usage (from the repo root, valuation service running):
    PYTHONPATH=valuation-agent python3.11 scripts/run_live_conformance_replay.py > run1.json
"""

from __future__ import annotations

import json
import sys

from valuation_agent.conformance import build_conformance_record
from valuation_agent.mcp_tools import MCPToolRegistry
from valuation_agent.workflow_run_state import GATE_EVIDENCE_REVIEW

FILING_URL = "https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm"

EVIDENCE_ITEMS = [
    {
        "driver": "revenue_growth",
        "evidence_summary": "Filing shows multi-year revenue growth.",
        "source_url": FILING_URL,
        "source_date": "2026-06-03",
        "confidence": "high",
    },
    {
        "driver": "operating_margin",
        "evidence_summary": "Filing shows one profitable year in the margin history.",
        "source_url": FILING_URL,
        "source_date": "2026-06-03",
        "confidence": "medium",
    },
    {
        "driver": "reinvestment_sales_to_capital",
        "evidence_summary": "Filing shows heavy capital expenditures against revenue growth.",
        "source_url": FILING_URL,
        "source_date": "2026-06-03",
        "confidence": "medium",
    },
]


def _call(registry: MCPToolRegistry, tool: str, args: dict) -> dict:
    payload = registry.call(tool, args)["structuredContent"]
    if not payload.get("ok"):
        raise SystemExit(f"{tool} failed: {json.dumps(payload.get('error'))}")
    return payload


def main() -> int:
    registry = MCPToolRegistry()

    extracted = _call(registry, "stockvaluation.extract_prospectus", {"filing_url": FILING_URL})
    run_id = extracted["run_id"]
    review_reference = extracted["prospectus"]["reviewReference"]

    # Simulated user: approves the evidence review.
    planned = _call(
        registry,
        "stockvaluation.plan_guided_questions",
        {
            "run_id": run_id,
            "company": "Space Exploration Technologies",
            "workflow_type": "prospectus",
            "evidence_items": EVIDENCE_ITEMS,
            "gate_records": [{"gate": GATE_EVIDENCE_REVIEW, "outcome": "approved"}],
        },
    )

    # Simulated user: accepts the default for every guided question. The plan
    # is not echoed back; the server uses its stored copy (planSource).
    applied = _call(
        registry,
        "stockvaluation.apply_guided_answers",
        {
            "run_id": run_id,
            "use_defaults": True,
        },
    )
    assert applied.get("planSource") == "run_state", applied.get("planSource")
    candidate = applied["prospectusScenarioCandidate"]
    if not candidate.get("supported"):
        raise SystemExit(f"scenario candidate unsupported: {json.dumps(candidate)}")

    valued = _call(
        registry,
        "stockvaluation.value_prospectus",
        {
            "run_id": run_id,
            "review_reference": review_reference,
            "review_status": "reviewed",
            "scenario": candidate["scenario"],
        },
    )

    run = registry.run_store.get_run(run_id)
    if "valuationRange" in valued:
        record = build_conformance_record(run, value_range=valued["valuationRange"])
    else:
        record = build_conformance_record(run, value_per_share=valued["dcf"]["estimatedValuePerShare"])
    record["run_id"] = run_id
    json.dump(record, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
