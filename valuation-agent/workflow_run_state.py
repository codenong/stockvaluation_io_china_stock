"""Persistent workflow run state and gate tracking for the MCP layer.

A run is created when a baseline or extraction tool starts a workflow.
Downstream tools look the run up by ``run_id``, record gate events, and the
MCP layer refuses scenario-bearing calls whose gates were never cleared.
State is persisted one JSON file per run so it survives across separate MCP
processes; entries expire after 24 hours.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable

RUN_STATE_DIR_ENV = "STOCKVALUATION_RUN_STATE_DIR"
RUN_STATE_TTL_SECONDS = 24 * 60 * 60

GATE_EVIDENCE_REVIEW = "evidence_review"
GATE_GUIDED_REFINEMENT = "guided_refinement"
GATES = (GATE_EVIDENCE_REVIEW, GATE_GUIDED_REFINEMENT)

EVIDENCE_REVIEW_OUTCOMES = {"approved", "corrected", "caveated", "bypassed"}
GUIDED_REFINEMENT_OUTCOMES = {"applied", "bypassed"}
BYPASS_REASONS = {"quick", "no_questions", "automation", "smoke_test"}


def default_run_state_dir(home: Path | str | None = None) -> Path:
    env_dir = os.environ.get(RUN_STATE_DIR_ENV)
    if env_dir:
        return Path(env_dir).expanduser()
    base = Path(home).expanduser() if home is not None else Path.home()
    return base / ".stockvaluation" / "run_state"


def validate_gate_record(record: Any) -> str | None:
    """Return a human-readable problem with a gate record, or None when valid."""
    if not isinstance(record, dict):
        return "gate record must be an object"
    gate = record.get("gate")
    outcome = record.get("outcome")
    reason = record.get("reason")
    if gate not in GATES:
        return f"gate must be one of {sorted(GATES)}"
    allowed = EVIDENCE_REVIEW_OUTCOMES if gate == GATE_EVIDENCE_REVIEW else GUIDED_REFINEMENT_OUTCOMES
    if outcome not in allowed:
        return f"outcome for {gate} must be one of {sorted(allowed)}"
    if outcome == "bypassed":
        if reason not in BYPASS_REASONS:
            return f"bypass reason must be one of {sorted(BYPASS_REASONS)}"
    elif reason is not None and not isinstance(reason, str):
        return "reason must be a string when supplied"
    return None


class WorkflowRunStore:
    """Create, look up, and update persisted workflow runs."""

    def __init__(
        self,
        root: Path | str | None = None,
        home: Path | str | None = None,
        now: Callable[[], float] | None = None,
    ):
        self.root = Path(root).expanduser() if root is not None else default_run_state_dir(home)
        self._now = now or time.time

    def create_run(self, *, workflow_type: str, subject: str | None = None) -> dict[str, Any]:
        run = {
            "run_id": f"run-{uuid.uuid4().hex}",
            "created_at": self._now(),
            "workflow_type": workflow_type,
            "subject": subject,
            "gates": {gate: {"status": "pending"} for gate in GATES},
            "events": [],
            "anchors": {},
            "guided_answers": {},
        }
        self._write(run)
        return run

    def get_run(self, run_id: Any) -> dict[str, Any] | None:
        if not isinstance(run_id, str) or not run_id:
            return None
        path = self._path(run_id)
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        created_at = run.get("created_at")
        if not isinstance(created_at, (int, float)) or self._now() - created_at > RUN_STATE_TTL_SECONDS:
            try:
                path.unlink()
            except OSError:
                pass
            return None
        return run

    def record_event(self, run_id: str, event_type: str, detail: dict[str, Any] | None = None) -> dict[str, Any] | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        event = {"type": event_type, "at": self._now()}
        if detail:
            event.update(detail)
        run["events"].append(event)
        self._write(run)
        return run

    def record_gate(self, run_id: str, gate: str, outcome: str, reason: str | None = None) -> dict[str, Any] | None:
        run = self.get_run(run_id)
        if run is None or gate not in GATES:
            return None
        status = "bypassed" if outcome == "bypassed" else "cleared"
        entry: dict[str, Any] = {"status": status, "outcome": outcome, "recorded_at": self._now()}
        if reason is not None:
            entry["reason"] = reason
        run["gates"][gate] = entry
        event: dict[str, Any] = {"type": "gate", "gate": gate, "outcome": outcome, "at": entry["recorded_at"]}
        if reason is not None:
            event["reason"] = reason
        run["events"].append(event)
        self._write(run)
        return run

    def update_run(self, run: dict[str, Any]) -> None:
        self._write(run)

    def gate_cleared(self, run: dict[str, Any], gate: str) -> bool:
        entry = run.get("gates", {}).get(gate) or {}
        return entry.get("status") in {"cleared", "bypassed"}

    def workflow_state(self, run: dict[str, Any]) -> dict[str, Any]:
        gates = run.get("gates", {})
        passed = [gate for gate in GATES if (gates.get(gate) or {}).get("status") in {"cleared", "bypassed"}]
        pending = [gate for gate in GATES if gate not in passed]
        return {
            "run_id": run.get("run_id"),
            "gate_enforcement": "tracked",
            "gates": {gate: dict(gates.get(gate) or {"status": "pending"}) for gate in GATES},
            "gates_passed": passed,
            "gates_pending": pending,
        }

    def _path(self, run_id: str) -> Path:
        safe = "".join(ch for ch in run_id if ch.isalnum() or ch in "-_")
        return self.root / f"{safe}.json"

    def _write(self, run: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(run["run_id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
