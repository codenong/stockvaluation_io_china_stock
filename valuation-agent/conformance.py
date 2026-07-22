"""Conformance records: a compact, diffable summary of a workflow run.

A conformance record is emitted from M2 run state plus the run's final
valuation output. Two runs of the same scripted scenario must produce
identical records (timestamps and run ids excluded); the checker reports
exactly which fields diverge when they do not.
"""

from __future__ import annotations

import copy
from typing import Any

CONFORMANCE_SCHEMA_VERSION = "conformance_record.v1"


def build_conformance_record(
    run: dict[str, Any],
    *,
    value_per_share: float | None = None,
    value_range: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize a run from persisted run state and its final output."""
    guided_plan = run.get("guided_plan") if isinstance(run.get("guided_plan"), dict) else {}
    framing_validation = guided_plan.get("framing_fork_validation") if isinstance(guided_plan, dict) else {}
    accepted_framing_forks = [
        {
            "fork_id": fork.get("fork_id"),
            "primary_driver": fork.get("primary_driver"),
            "confidence": fork.get("confidence"),
        }
        for fork in (framing_validation or {}).get("accepted_forks", [])
        if isinstance(fork, dict)
    ]
    coherence_review = run.get("coherence_review") if isinstance(run.get("coherence_review"), dict) else {}
    revealed_thesis = run.get("revealed_thesis") if isinstance(run.get("revealed_thesis"), dict) else None
    gates_in_order = [
        {
            "gate": event.get("gate"),
            "outcome": event.get("outcome"),
            "reason": event.get("reason"),
        }
        for event in run.get("events", [])
        if event.get("type") == "gate"
    ]
    question_count = None
    for event in run.get("events", []):
        if event.get("type") == "guided_plan_created":
            question_count = event.get("question_count")
    tool_calls = [
        {"tool": event.get("tool"), "ok": event.get("ok", True)}
        for event in run.get("events", [])
        if event.get("type") == "tool_call"
    ]
    drivers = {
        field: {"value": entry.get("value"), "source": entry.get("source")}
        for field, entry in sorted((run.get("guided_answers") or {}).items())
    }
    anchors = {
        field: {
            label: (anchor_set.get("anchors") or {}).get(label, {}).get("value")
            for label in ("low", "base", "high")
        }
        for field, anchor_set in sorted((run.get("anchors") or {}).items())
    }
    if value_range is not None:
        final_case_type = "range"
        value: Any = {
            "unresolved_drivers": value_range.get("unresolved_drivers"),
            "low": (value_range.get("low") or {}).get("value_per_share"),
            "high": (value_range.get("high") or {}).get("value_per_share"),
        }
    elif value_per_share is not None:
        final_case_type = "point"
        value = value_per_share
    else:
        final_case_type = "none"
        value = None
    return {
        "schema_version": CONFORMANCE_SCHEMA_VERSION,
        "workflow_type": run.get("workflow_type"),
        "subject": run.get("subject"),
        "gates_in_order": gates_in_order,
        "tool_calls": tool_calls,
        "question_count": question_count,
        "accepted_framing_forks": accepted_framing_forks,
        "coherence_status": coherence_review.get("status"),
        "coherence_challenge_count": run.get("coherence_challenge_count", 0),
        "material_anchor_fields": sorted(run.get("material_anchor_fields") or []),
        "anchors": anchors,
        "drivers": drivers,
        "revealed_thesis": copy.deepcopy(revealed_thesis),
        "final_scenario_record": {
            "case_type": final_case_type,
            "value": copy.deepcopy(value),
        },
        "final_case_type": final_case_type,
        "value": value,
    }


def diff_conformance_records(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """Diff two records field by field; identical means consistent runs."""
    differences: list[dict[str, Any]] = []

    def walk(path: str, a: Any, b: Any) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b)):
                walk(f"{path}.{key}" if path else str(key), a.get(key), b.get(key))
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                differences.append({"path": path, "first": a, "second": b})
                return
            for index, (item_a, item_b) in enumerate(zip(a, b)):
                walk(f"{path}[{index}]", item_a, item_b)
        elif a != b:
            differences.append({"path": _reported_path(path), "first": a, "second": b})

    walk("", first, second)
    return {"identical": not differences, "differences": differences}


def _reported_path(path: str) -> str:
    return path.replace(".selected_interpretation", ".interpretation")
