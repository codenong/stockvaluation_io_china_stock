#!/usr/bin/env python3
"""Founder-style MSFT live acceptance round for BullBearGPT."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests


DEFAULT_TICKER = "MSFT"
DEFAULT_BULLBEAR_URL = os.getenv("BULLBEARGPT_BASE_URL", "http://localhost:5000/bullbeargpt/api/notebook")
DEFAULT_VALUATION_AGENT_URL = os.getenv("VALUATION_AGENT_URL", "http://localhost:5001")
DEFAULT_PROMPT_DUMP_DIR = Path(".etl/prompt_dump/bullbear_agent_msft")
DEFAULT_ARTIFACTS_ROOT = Path(".etl/live_test_runs/bullbear_agent_msft")


class AcceptanceRunError(RuntimeError):
    """Raised when a critical live-test prerequisite fails."""


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp() -> str:
    return _utc_now().strftime("%Y%m%d_%H%M%S")


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "step"


def _headers() -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    internal_api_key = os.getenv("INTERNAL_API_KEY", "").strip()
    if internal_api_key:
        headers["Authorization"] = f"Bearer {internal_api_key}"
        headers["X-Internal-API-Key"] = internal_api_key
    return headers


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _snapshot_prompt_files(prompt_dump_dir: Path) -> set[str]:
    if not prompt_dump_dir.exists():
        return set()
    return {
        str(path.relative_to(prompt_dump_dir))
        for path in prompt_dump_dir.rglob("*")
        if path.is_file()
    }


def _load_dump_json(prompt_dump_dir: Path, relative_path: str) -> Dict[str, Any]:
    return json.loads((prompt_dump_dir / relative_path).read_text(encoding="utf-8"))


def _select_dump_files(relative_paths: Iterable[str], prefix: str, suffix: str) -> List[str]:
    matches = []
    for relative_path in relative_paths:
        rel = Path(relative_path)
        if not rel.parts:
            continue
        if rel.parts[0].startswith(prefix) and relative_path.endswith(suffix):
            matches.append(relative_path)
    return sorted(matches)


def _latest_dump(relative_paths: Iterable[str], prefix: str, suffix: str) -> Optional[str]:
    matches = _select_dump_files(relative_paths, prefix, suffix)
    return matches[-1] if matches else None


class LiveRoundRunner:
    def __init__(
        self,
        bullbear_url: str,
        valuation_agent_url: str,
        ticker: str,
        user_id: str,
        prompt_dump_dir: Path,
        artifacts_root: Path,
    ) -> None:
        self.bullbear_url = bullbear_url.rstrip("/")
        self.valuation_agent_url = valuation_agent_url.rstrip("/")
        self.ticker = ticker.upper()
        self.user_id = user_id
        self.prompt_dump_dir = prompt_dump_dir.resolve()
        self.artifacts_root = artifacts_root.resolve()
        self.run_dir = self.artifacts_root / _timestamp()
        self.sse_dir = self.run_dir / "sse"
        self.report_path = self.run_dir / "report.md"
        self.summary_path = self.run_dir / "summary.json"
        self.session = requests.Session()
        self.session.headers.update(_headers())
        self.results: List[CheckResult] = []
        self.seeded_theses: List[Dict[str, Any]] = []
        self.canonical_valuation: Dict[str, Any] = {}
        self.main_session: Dict[str, Any] = {}
        self.latest_step_dumps: Dict[str, List[str]] = {}

    def check(self, name: str, condition: bool, detail: str) -> None:
        self.results.append(CheckResult(name=name, status="PASS" if condition else "FAIL", detail=detail))

    def info(self, name: str, detail: str) -> None:
        self.results.append(CheckResult(name=name, status="INFO", detail=detail))

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            raise AcceptanceRunError(message)

    def run(self) -> int:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.sse_dir.mkdir(parents=True, exist_ok=True)

        self.info(
            "Prompt Dump Setup",
            (
                "Start BullBearGPT with "
                "DUMP_PROMPTS=true, "
                f"PROMPT_DUMP_DIR={self.prompt_dump_dir}, "
                "ALLOW_PROMPT_DUMPS_IN_PRODUCTION=true if FLASK_ENV=production."
            ),
        )

        self._create_canonical_msft_valuation()
        self._seed_prior_theses()
        self._run_live_acceptance_matrix()
        self._verify_thesis_history_refresh()
        self._write_report()
        _write_json(self.summary_path, self._build_summary_payload())
        return 1 if any(result.status == "FAIL" for result in self.results) else 0

    def _json_get(self, url: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = self.session.get(url, params=params, timeout=120)
        response.raise_for_status()
        return response.json()

    def _json_post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.post(url, json=payload, timeout=240)
        response.raise_for_status()
        return response.json()

    def _post_sse(self, step_name: str, session_id: str, message: str) -> Dict[str, Any]:
        before_files = _snapshot_prompt_files(self.prompt_dump_dir)
        response = self.session.post(
            f"{self.bullbear_url}/sessions/{session_id}/messages",
            json={"message": message, "user_id": self.user_id},
            headers={"Accept": "text/event-stream", **_headers()},
            timeout=300,
            stream=True,
        )
        response.raise_for_status()

        raw_lines: List[str] = []
        events: List[Dict[str, Any]] = []
        current_event: Optional[str] = None
        current_data: List[str] = []

        def flush_event() -> None:
            nonlocal current_event, current_data
            if current_event is None and not current_data:
                return
            raw_payload = "\n".join(current_data)
            try:
                payload = json.loads(raw_payload) if raw_payload else {}
            except json.JSONDecodeError:
                payload = {"raw_data": raw_payload}
            events.append({"type": current_event or "", "payload": payload, "raw_data": raw_payload})
            current_event = None
            current_data = []

        for line in response.iter_lines(decode_unicode=True):
            normalized = line if line is not None else ""
            raw_lines.append(normalized)
            if normalized.startswith("event: "):
                current_event = normalized[7:].strip()
            elif normalized.startswith("data: "):
                current_data.append(normalized[6:].strip())
            elif normalized == "":
                flush_event()

        flush_event()
        transcript_name = f"{len(list(self.sse_dir.glob('*.txt'))) + 1:02d}_{_slug(step_name)}"
        (self.sse_dir / f"{transcript_name}.txt").write_text("\n".join(raw_lines), encoding="utf-8")

        time.sleep(0.2)
        after_files = _snapshot_prompt_files(self.prompt_dump_dir)
        new_dump_files = sorted(after_files - before_files)
        self.latest_step_dumps[step_name] = new_dump_files

        summary = {
            "step_name": step_name,
            "message": message,
            "status_code": response.status_code,
            "events": events,
            "event_types": [event["type"] for event in events],
            "stream_text": "".join(
                event["payload"].get("chunk", "")
                for event in events
                if isinstance(event.get("payload"), dict) and event["type"] == "stream"
            ),
            "tool_plan": next((event["payload"] for event in events if event["type"] == "tool_plan"), None),
            "tool_result": next((event["payload"] for event in events if event["type"] == "tool_result"), None),
            "final_cell": next(
                (
                    event["payload"].get("cell")
                    for event in reversed(events)
                    if event["type"] == "cell_complete" and isinstance(event.get("payload"), dict)
                ),
                None,
            ),
            "new_dump_files": new_dump_files,
            "transcript_path": str((self.sse_dir / f"{transcript_name}.txt").relative_to(self.run_dir)),
        }
        _write_json(self.sse_dir / f"{transcript_name}.json", summary)
        return summary

    def _create_canonical_msft_valuation(self) -> None:
        valuation_start = self._json_post(
            f"{self.valuation_agent_url}/api-s/valuate",
            {"ticker": self.ticker},
        )
        valuation_id = valuation_start.get("valuation_id")
        self.require(bool(valuation_id), "valuation-agent did not return valuation_id for MSFT")

        valuation_record = self._json_get(f"{self.valuation_agent_url}/api-s/valuation/{valuation_id}")
        self.require(bool(valuation_record.get("valuation_data")), "valuation-agent returned empty valuation_data")

        self.canonical_valuation = valuation_record
        self.check(
            "Canonical MSFT Valuation",
            True,
            f"Created valuation_id={valuation_id} with input/output payloads ready for reuse.",
        )

    def _seed_prior_theses(self) -> None:
        valuation_data = self.canonical_valuation.get("valuation_data") or {}
        valuation_input_json = self.canonical_valuation.get("input_json") or {}
        valuation_output_json = self.canonical_valuation.get("output_json") or {}
        company_name = self.canonical_valuation.get("company_name") or self.ticker

        titles = [
            "MSFT Seed Thesis A",
            "MSFT Seed Thesis B",
            "MSFT Seed Thesis C",
        ]

        for index, title in enumerate(titles, start=1):
            session_payload = {
                "ticker": self.ticker,
                "company_name": company_name,
                "user_id": self.user_id,
                "valuation_data": valuation_data,
                "valuation_input_json": valuation_input_json,
                "valuation_output_json": valuation_output_json,
            }
            seeded_session = self._json_post(f"{self.bullbear_url}/sessions", session_payload)
            thesis_payload = {
                "user_id": self.user_id,
                "title": title,
                "summary": f"Seeded prior thesis {index} for MSFT acceptance coverage.",
                "preview_json": {
                    "title": title,
                    "summary": f"Seeded prior thesis {index} for MSFT acceptance coverage.",
                    "conviction": "medium",
                    "key_assumptions": [f"Seed assumption {index}"],
                    "risks": [f"Seed risk {index}"],
                    "fair_value": (self.canonical_valuation.get("fair_value") or 0) + index,
                    "current_price": self.canonical_valuation.get("current_price"),
                    "upside": self.canonical_valuation.get("upside_percentage"),
                    "timeframe": "12m",
                },
            }
            saved = self._json_post(
                f"{self.bullbear_url}/sessions/{seeded_session['id']}/save-thesis",
                thesis_payload,
            )
            self.seeded_theses.append(saved["thesis"])
            time.sleep(0.05)

        grouped = self._json_get(
            f"{self.bullbear_url}/theses",
            params={"user_id": self.user_id, "grouped": "true"},
        )
        msft_group = grouped.get("grouped", {}).get(self.ticker, {})
        grouped_titles = [
            thesis["title"]
            for theses in msft_group.values()
            for thesis in theses
        ]
        expected_latest_titles = ["MSFT Seed Thesis C", "MSFT Seed Thesis B"]
        latest_two = grouped_titles[:2]
        self.check(
            "Seeded Thesis History",
            latest_two == expected_latest_titles,
            f"Expected latest two theses {expected_latest_titles}, got {latest_two}.",
        )

    def _create_main_session(self, *, valuation_id: Optional[str], valuation_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ticker": self.ticker,
            "company_name": self.canonical_valuation.get("company_name") or self.ticker,
            "user_id": self.user_id,
        }
        if valuation_id:
            payload["valuation_id"] = valuation_id
        if valuation_data is not None:
            payload["valuation_data"] = valuation_data
            payload["valuation_input_json"] = self.canonical_valuation.get("input_json") or {}
            payload["valuation_output_json"] = self.canonical_valuation.get("output_json") or {}
        return self._json_post(f"{self.bullbear_url}/sessions", payload)

    def _run_live_acceptance_matrix(self) -> None:
        self.main_session = self._create_main_session(valuation_id=self.canonical_valuation["id"])
        main_session_id = self.main_session["id"]

        smoke = self._post_sse(
            "context_smoke",
            main_session_id,
            "Summarize the current MSFT valuation in two sentences using only the current notebook context. Do not run any tool.",
        )
        self.check(
            "Context Smoke Avoids Tools",
            smoke["tool_plan"] is None,
            f"Tool plan observed: {smoke['tool_plan']!r}",
        )
        self._verify_context_prompt(smoke, expect_latest_titles=["MSFT Seed Thesis C", "MSFT Seed Thesis B"], excluded_title="MSFT Seed Thesis A")

        valuation_loader_round = self._run_tool_round(
            step_prefix="valuation_loader",
            session_id=main_session_id,
            prompt="Load the raw MSFT valuation input/output and compare them to my last two saved MSFT theses.",
            expected_tool_name="valuation_loader",
            approval="yes",
        )
        valuation_loader_result = valuation_loader_round["approval_response"].get("tool_result") or {}
        recent_theses = ((valuation_loader_result.get("data") or {}).get("recent_theses") or [])
        self.check(
            "valuation_loader Returns Two Recent Theses",
            len(recent_theses) == 2,
            f"valuation_loader returned {len(recent_theses)} recent theses.",
        )
        self._verify_synthesis_dump(
            valuation_loader_round["approval_response"],
            required_snippets=["Tool results and data:", "Recent theses:", "Input JSON keys:"],
            check_name="valuation_loader Synthesis Uses Tool Output",
        )

        comparables_round = self._run_tool_round(
            step_prefix="industry_comparables",
            session_id=main_session_id,
            prompt="Is MSFT’s revenue growth assumption reasonable versus industry? Use the comparables path.",
            expected_tool_name="get_industry_comparables",
            approval="yes",
        )
        comparables_result = comparables_round["approval_response"].get("tool_result") or {}
        comparables_data = comparables_result.get("data") or {}
        self.check(
            "get_industry_comparables Uses Growth Anchor",
            comparables_data.get("metric") == "revenue_cagr" and comparables_data.get("industry_band"),
            f"Comparables payload: {json.dumps(comparables_data, default=str)}",
        )

        denied_round = self._run_tool_round(
            step_prefix="dcf_recalc_denied",
            session_id=main_session_id,
            prompt="What if WACC was 10%?",
            expected_tool_name="dcf_recalculator",
            approval="no",
        )
        denied_final_cell = denied_round["approval_response"].get("final_cell") or {}
        denied_tool_results = (((denied_final_cell.get("ai_output") or {}).get("tool_results")) or [])
        self.check(
            "dcf_recalculator Denial Path",
            denied_round["approval_response"].get("tool_result") is None and denied_tool_results == [],
            "Denied approval returned no tool_result event and stored no tool_results on the response cell.",
        )

        approved_round = self._run_tool_round(
            step_prefix="dcf_recalc_approved",
            session_id=main_session_id,
            prompt="What if WACC was 10%?",
            expected_tool_name="dcf_recalculator",
            approval="yes",
        )
        recalc_result = approved_round["approval_response"].get("tool_result") or {}
        comparison = ((recalc_result.get("data") or {}).get("comparison") or {})
        before_fair_value = ((comparison.get("before") or {}).get("fair_value"))
        after_fair_value = ((comparison.get("after") or {}).get("fair_value"))
        session_after_recalc = self._json_get(f"{self.bullbear_url}/sessions/{main_session_id}")
        current_output = session_after_recalc.get("valuation_output_json") or {}
        current_fair_value = ((current_output.get("companyDTO") or {}).get("estimatedValuePerShare"))
        self.check(
            "dcf_recalculator Updates Session Context",
            after_fair_value is not None and after_fair_value != before_fair_value and current_fair_value == after_fair_value,
            f"Before fair value={before_fair_value}, after={after_fair_value}, session current={current_fair_value}.",
        )

        post_recalc_smoke = self._post_sse(
            "post_recalc_context_smoke",
            main_session_id,
            "State the current fair value and WACC after the approved recalc using only the current notebook context.",
        )
        self._verify_recalc_context_prompt(post_recalc_smoke, after_fair_value)

        python_round = self._run_tool_round(
            step_prefix="python_interpreter",
            session_id=main_session_id,
            prompt=(
                "Use Python to calculate upside from the current MSFT fair value/current price, "
                "then show a 3-row sensitivity table for fair value -5%, base, and +5%."
            ),
            expected_tool_name="python_interpreter",
            approval="yes",
        )
        python_tool_result = python_round["approval_response"].get("tool_result") or {}
        python_data = python_tool_result.get("data") or {}
        result_rows = python_data.get("result")
        self.check(
            "python_interpreter Returns Structured Result",
            isinstance(result_rows, (dict, list)) and bool(python_data.get("code")),
            f"python_interpreter result keys: {list(python_data.keys())}",
        )
        generate_code_dump = _latest_dump(
            python_round["approval_response"].get("new_dump_files", []),
            prefix="generate_code_",
            suffix="_prompt.json",
        )
        self.check(
            "python_interpreter Dumps Generated Code Prompt",
            generate_code_dump is not None,
            f"New generate_code dump: {generate_code_dump}",
        )

        main_save = self._json_post(
            f"{self.bullbear_url}/sessions/{main_session_id}/save-thesis",
            {
                "user_id": self.user_id,
                "title": "MSFT Live Acceptance Thesis",
                "summary": "Founder acceptance thesis saved from the live MSFT test round.",
                "preview_json": {
                    "title": "MSFT Live Acceptance Thesis",
                    "summary": "Founder acceptance thesis saved from the live MSFT test round.",
                    "conviction": "high",
                    "key_assumptions": ["Copilot monetization", "Azure durability"],
                    "risks": ["AI capex normalizes"],
                    "fair_value": after_fair_value,
                    "current_price": current_output.get("companyDTO", {}).get("price"),
                    "upside": current_output.get("companyDTO", {}).get("upside"),
                    "timeframe": "12m",
                },
            },
        )
        thesis_id = (main_save.get("thesis") or {}).get("id")
        grouped = self._json_get(
            f"{self.bullbear_url}/theses",
            params={"user_id": self.user_id, "grouped": "true"},
        )
        loaded_thesis = self._json_get(f"{self.bullbear_url}/theses/{thesis_id}")
        msft_titles_after_save = [
            thesis["title"]
            for theses in grouped.get("grouped", {}).get(self.ticker, {}).values()
            for thesis in theses
        ]
        self.check(
            "save-thesis API Roundtrip",
            thesis_id is not None
            and "MSFT Live Acceptance Thesis" in msft_titles_after_save
            and (loaded_thesis.get("thesis") or {}).get("id") == thesis_id,
            f"Saved thesis_id={thesis_id}, grouped titles head={msft_titles_after_save[:3]}",
        )

    def _verify_thesis_history_refresh(self) -> None:
        refreshed_session = self._create_main_session(
            valuation_id=None,
            valuation_data=self.canonical_valuation.get("valuation_data") or {},
        )
        refreshed_smoke = self._post_sse(
            "fresh_session_context_smoke",
            refreshed_session["id"],
            "Summarize the current MSFT valuation in one sentence using the current notebook context only.",
        )
        self._verify_context_prompt(
            refreshed_smoke,
            expect_latest_titles=["MSFT Live Acceptance Thesis", "MSFT Seed Thesis C"],
            excluded_title="MSFT Seed Thesis B",
            check_name="Fresh Session Loads Latest Two Prior Theses",
        )

    def _run_tool_round(
        self,
        step_prefix: str,
        session_id: str,
        prompt: str,
        expected_tool_name: str,
        approval: str,
    ) -> Dict[str, Any]:
        plan_response = self._post_sse(f"{step_prefix}_plan", session_id, prompt)
        tool_plan = plan_response.get("tool_plan") or {}
        self.check(
            f"{expected_tool_name} Tool Plan",
            tool_plan.get("tool_name") == expected_tool_name,
            f"Observed tool_plan={json.dumps(tool_plan, default=str)}",
        )
        select_tools_dump = _latest_dump(
            plan_response.get("new_dump_files", []),
            prefix="select_tools_",
            suffix="_prompt.json",
        )
        self.check(
            f"{expected_tool_name} select_tools Prompt Dump",
            select_tools_dump is not None,
            f"New select_tools dump: {select_tools_dump}",
        )
        approval_response = self._post_sse(f"{step_prefix}_{approval}", session_id, approval)
        final_cell = approval_response.get("final_cell") or {}
        final_tool_results = (((final_cell.get("ai_output") or {}).get("tool_results")) or [])
        if approval == "yes":
            self.check(
                f"{expected_tool_name} Tool Result Event",
                (approval_response.get("tool_result") or {}).get("tool_name") == expected_tool_name
                and (approval_response.get("tool_result") or {}).get("status") == "success",
                f"Observed tool_result={json.dumps(approval_response.get('tool_result'), default=str)}",
            )
            self.check(
                f"{expected_tool_name} Reasoning Cell Stores Tool Results",
                bool(final_tool_results) and final_tool_results[0].get("tool_name") == expected_tool_name,
                f"Final cell tool_results={json.dumps(final_tool_results, default=str)}",
            )
        return {
            "plan_response": plan_response,
            "approval_response": approval_response,
        }

    def _verify_context_prompt(
        self,
        step_summary: Dict[str, Any],
        *,
        expect_latest_titles: List[str],
        excluded_title: str,
        check_name: str = "Context Prompt Contains Current Inputs/Outputs And Latest Two Theses",
    ) -> None:
        stream_chat_dump = _latest_dump(step_summary.get("new_dump_files", []), prefix="stream_chat_", suffix="_conversation.json")
        if not stream_chat_dump:
            self.check(check_name, False, "No new stream_chat conversation dump was found for this step.")
            return

        dump_payload = _load_dump_json(self.prompt_dump_dir, stream_chat_dump)
        system_prompt = dump_payload.get("system_prompt", "")
        required_sections = [
            "CURRENT VALUATION SUMMARY",
            "CURRENT VALUATION INPUT EXTRACTS",
            "CURRENT VALUATION OUTPUT EXTRACTS",
            "RECENT SAVED THESES (MAX 2)",
        ]
        all_sections_present = all(section in system_prompt for section in required_sections)
        titles_present = all(title in system_prompt for title in expect_latest_titles)
        excluded_absent = excluded_title not in system_prompt

        self.check(
            check_name,
            all_sections_present and titles_present and excluded_absent,
            (
                f"stream_chat dump={stream_chat_dump}; "
                f"sections_ok={all_sections_present}; "
                f"expected_titles={expect_latest_titles}; "
                f"excluded_absent={excluded_absent}"
            ),
        )

    def _verify_recalc_context_prompt(self, step_summary: Dict[str, Any], expected_fair_value: Any) -> None:
        stream_chat_dump = _latest_dump(step_summary.get("new_dump_files", []), prefix="stream_chat_", suffix="_conversation.json")
        if not stream_chat_dump:
            self.check("Post-Recalc Context Dump", False, "No stream_chat dump found after approved recalc smoke.")
            return
        dump_payload = _load_dump_json(self.prompt_dump_dir, stream_chat_dump)
        system_prompt = dump_payload.get("system_prompt", "")
        fair_value_text = str(expected_fair_value)
        self.check(
            "Post-Recalc Context Shows Updated Fair Value",
            expected_fair_value is not None and fair_value_text in system_prompt,
            f"Expected fair value {fair_value_text!r} in dump {stream_chat_dump}.",
        )

    def _verify_synthesis_dump(
        self,
        step_summary: Dict[str, Any],
        *,
        required_snippets: List[str],
        check_name: str,
    ) -> None:
        stream_chat_dump = _latest_dump(step_summary.get("new_dump_files", []), prefix="stream_chat_", suffix="_conversation.json")
        if not stream_chat_dump:
            self.check(check_name, False, "No synthesis stream_chat dump was found.")
            return
        dump_payload = _load_dump_json(self.prompt_dump_dir, stream_chat_dump)
        messages = dump_payload.get("messages") or []
        joined_messages = "\n".join(str(message.get("content", "")) for message in messages if isinstance(message, dict))
        ok = all(snippet in joined_messages for snippet in required_snippets)
        self.check(
            check_name,
            ok,
            f"Checked dump {stream_chat_dump} for snippets {required_snippets}.",
        )

    def _build_summary_payload(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "user_id": self.user_id,
            "valuation_id": self.canonical_valuation.get("id"),
            "prompt_dump_dir": str(self.prompt_dump_dir),
            "artifacts_dir": str(self.run_dir),
            "results": [result.__dict__ for result in self.results],
            "seeded_theses": self.seeded_theses,
            "main_session_id": self.main_session.get("id"),
            "step_dumps": self.latest_step_dumps,
        }

    def _write_report(self) -> None:
        failures = [result for result in self.results if result.status == "FAIL"]
        lines = [
            f"# BullBear Agent {self.ticker} Live Test Round",
            "",
            f"- Run timestamp: {_utc_now().isoformat()}",
            f"- User ID: `{self.user_id}`",
            f"- Valuation ID: `{self.canonical_valuation.get('id')}`",
            f"- Prompt dump dir: `{self.prompt_dump_dir}`",
            f"- SSE transcript dir: `{self.sse_dir}`",
            f"- Summary JSON: `{self.summary_path}`",
            "",
            "## Results",
        ]

        for result in self.results:
            lines.append(f"- [{result.status}] {result.name}: {result.detail}")

        lines.extend(
            [
                "",
                "## Manual UI Smoke",
                "- [ ] Thesis sidebar shows grouped `MSFT` theses on load.",
                "  Screenshot: add image path under `screenshots/thesis_sidebar.png`.",
                "- [ ] Saving thesis updates the sidebar without a full reload.",
                "  Screenshot: add image path under `screenshots/thesis_save_refresh.png`.",
                "- [ ] Clicking a thesis opens a thesis tab with the saved content.",
                "  Screenshot: add image path under `screenshots/thesis_tab_open.png`.",
                "",
                "## Exit",
                f"- Overall status: {'FAIL' if failures else 'PASS'}",
            ]
        )
        self.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default=DEFAULT_TICKER, help="Ticker to use for the round. Defaults to MSFT.")
    parser.add_argument("--bullbear-url", default=DEFAULT_BULLBEAR_URL, help="BullBearGPT notebook API base URL.")
    parser.add_argument("--valuation-agent-url", default=DEFAULT_VALUATION_AGENT_URL, help="valuation-agent base URL.")
    parser.add_argument("--prompt-dump-dir", default=str(DEFAULT_PROMPT_DUMP_DIR), help="Expected BullBearGPT prompt dump directory.")
    parser.add_argument("--artifacts-root", default=str(DEFAULT_ARTIFACTS_ROOT), help="Where to store transcripts and reports.")
    parser.add_argument(
        "--user-id",
        default=f"msft_live_round_{_timestamp()}",
        help="User ID for seeded thesis history and notebook sessions.",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    runner = LiveRoundRunner(
        bullbear_url=args.bullbear_url,
        valuation_agent_url=args.valuation_agent_url,
        ticker=args.ticker,
        user_id=args.user_id,
        prompt_dump_dir=Path(args.prompt_dump_dir),
        artifacts_root=Path(args.artifacts_root),
    )
    try:
        return runner.run()
    except AcceptanceRunError as exc:
        runner.check("Critical Failure", False, str(exc))
        runner._write_report()
        _write_json(runner.summary_path, runner._build_summary_payload())
        print(f"Live round failed: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        runner.check("HTTP Failure", False, str(exc))
        runner._write_report()
        _write_json(runner.summary_path, runner._build_summary_payload())
        print(f"HTTP failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
