"""Pure validation for company-specific investment framing forks.

Framing forks contain business judgment only.  In particular, they never
contain scenario numbers; the guided-question planner binds accepted stories
to server-owned driver anchors after validation.
"""

from __future__ import annotations

import re
from typing import Any

from .security import sanitize_for_agent

FRAMING_FORK_SCHEMA_VERSION = "framing_fork.v1"
FRAMING_CONFIDENCES = frozenset({"low", "medium", "high"})
FRAMING_OPTION_LABELS = ("A", "B", "C")
FRAMING_REQUIRED_FIELDS = (
    "schema_version",
    "fork_id",
    "primary_driver",
    "causal_question",
    "confidence",
    "material",
    "supporting_evidence_refs",
    "opposing_evidence_refs",
    "evidence_gaps",
    "options",
)
FRAMING_REJECTION_CODES = frozenset(
    {
        "invalid_fork",
        "missing_required_field",
        "unsupported_schema_version",
        "missing_fork_id",
        "unsupported_driver",
        "missing_causal_question",
        "invalid_confidence",
        "invalid_analysis_lean",
        "invalid_evidence_references",
        "invalid_options",
        "numeric_content_forbidden",
    }
)

SUPPORTED_FRAMING_DRIVERS = frozenset(
    {
        "revenue_growth",
        "operating_margin",
        "reinvestment_sales_to_capital",
        "terminal_value_mature_state",
        "risk_wacc",
        "accounting_adjustments",
    }
)

_NUMERIC_KEYS = frozenset(
    {
        "value",
        "candidate_value",
        "override",
        "override_candidate",
        "growth",
        "margin",
        "wacc",
        "rate",
        "percent",
        "percentage",
        "multiple",
        "sales_to_capital",
    }
)

_NON_CONTENT_STRING_KEYS = frozenset(
    {
        "schema_version",
        "fork_id",
        "id",
        "supporting_evidence_refs",
        "opposing_evidence_refs",
    }
)

_ENGLISH_NUMBER_WORD = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|"
    r"billion|trillion)\b",
    re.IGNORECASE,
)


def validate_framing_forks(raw_forks: Any, evidence_items: Any) -> dict[str, Any]:
    """Return accepted semantic forks and stable, non-throwing rejections."""
    raw_list = raw_forks if isinstance(raw_forks, list) else []
    evidence_refs = _available_evidence_references(evidence_items)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    if raw_forks is not None and not isinstance(raw_forks, list):
        rejected.append(_rejection({}, "invalid_fork", "framing_forks must be an array."))

    for index, raw in enumerate(raw_list):
        sanitized = sanitize_for_agent(raw)
        if not isinstance(raw, dict):
            rejected.append(_rejection({}, "invalid_fork", f"Framing fork at index {index} must be an object."))
            continue

        code, reason = _validation_error(raw, evidence_refs)
        fork_id = _text(raw.get("fork_id") or raw.get("id"))
        if code is None and fork_id in seen_ids:
            code, reason = "invalid_fork", f"Duplicate framing fork id: {fork_id}."
        if code is not None:
            rejected.append(_rejection(sanitized, code, reason or "Invalid framing fork."))
            continue

        normalized = _normalize_fork(raw)
        accepted.append(normalized)
        seen_ids.add(normalized["fork_id"])

    return {
        "schema_version": FRAMING_FORK_SCHEMA_VERSION,
        "accepted_forks": accepted,
        "rejected_forks": rejected,
    }


def framing_forks_input_schema() -> dict[str, Any]:
    """Complete JSON Schema fragment used by the MCP tools/list contract."""
    evidence_refs = {
        "type": "array",
        "description": "Exact evidence ids or source URLs present in evidence_items. Use an empty array when that side has an evidence gap; never fabricate a reference.",
        "items": {"type": "string", "minLength": 1},
        "uniqueItems": True,
    }
    option_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string", "enum": list(FRAMING_OPTION_LABELS)},
            "story": {"type": "string", "minLength": 1},
            "falsifier": {"type": "string", "minLength": 1},
        },
        "required": ["label", "story", "falsifier"],
    }
    return {
        "type": "array",
        "description": "Optional company-specific, non-numeric framing forks. The server validates evidence references and attaches all scenario numbers from canonical anchors.",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "schema_version": {"type": "string", "const": FRAMING_FORK_SCHEMA_VERSION},
                "fork_id": {"type": "string", "minLength": 1},
                "primary_driver": {"type": "string", "enum": sorted(SUPPORTED_FRAMING_DRIVERS)},
                "causal_question": {"type": "string", "minLength": 1},
                "confidence": {"type": "string", "enum": sorted(FRAMING_CONFIDENCES)},
                "material": {"type": "boolean"},
                "supporting_evidence_refs": evidence_refs,
                "opposing_evidence_refs": evidence_refs,
                "evidence_gaps": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "description": "Known missing evidence. Gaps are preserved and must not be filled with invented references.",
                },
                "options": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": option_schema,
                },
                "analysis_lean": {
                    "description": "Optional analysis lean. It never changes the neutral B default.",
                    "anyOf": [
                        {"type": "string", "enum": list(FRAMING_OPTION_LABELS)},
                        {"type": "null"},
                    ],
                },
            },
            "required": [
                "schema_version",
                "fork_id",
                "primary_driver",
                "causal_question",
                "confidence",
                "material",
                "supporting_evidence_refs",
                "opposing_evidence_refs",
                "evidence_gaps",
                "options",
            ],
        },
    }


def _validation_error(raw: dict[str, Any], evidence_refs: set[str]) -> tuple[str | None, str | None]:
    missing_fields = [field for field in FRAMING_REQUIRED_FIELDS if field not in raw]
    if missing_fields:
        return "missing_required_field", f"Required framing fork field is missing: {missing_fields[0]}."
    if raw.get("schema_version") != FRAMING_FORK_SCHEMA_VERSION:
        return "unsupported_schema_version", f"schema_version must be {FRAMING_FORK_SCHEMA_VERSION}."
    if not _text(raw.get("fork_id") or raw.get("id")):
        return "missing_fork_id", "fork_id is required."
    driver = _text(raw.get("primary_driver") or raw.get("driver"))
    if driver not in SUPPORTED_FRAMING_DRIVERS:
        return "unsupported_driver", "primary_driver is not supported for framing forks."
    if not _text(raw.get("causal_question")):
        return "missing_causal_question", "causal_question is required."
    if _text(raw.get("confidence")).lower() not in FRAMING_CONFIDENCES:
        return "invalid_confidence", "confidence must be low, medium, or high."
    lean = raw.get("analysis_lean")
    if lean is not None and _text(lean).upper() not in FRAMING_OPTION_LABELS:
        return "invalid_analysis_lean", "analysis_lean must be A, B, C, or null."
    if _contains_model_number(raw):
        return "numeric_content_forbidden", "Framing forks may not supply numbers or override candidates."

    support = _string_list(raw.get("supporting_evidence_refs"))
    oppose = _string_list(raw.get("opposing_evidence_refs"))
    if support is None or oppose is None:
        return "invalid_evidence_references", "supporting_evidence_refs and opposing_evidence_refs must be arrays of strings."
    unknown = sorted({*support, *oppose} - evidence_refs)
    if unknown:
        return "invalid_evidence_references", f"Evidence references must exactly match evidence_items; unknown: {', '.join(unknown)}."

    options = _normalized_options(raw.get("options"))
    if options is None:
        return "invalid_options", "options must contain distinct A, B, and C stories with non-empty falsifiers."
    return None, None


def _normalize_fork(raw: dict[str, Any]) -> dict[str, Any]:
    options = _normalized_options(raw.get("options")) or []
    return {
        "schema_version": FRAMING_FORK_SCHEMA_VERSION,
        "fork_id": _text(raw.get("fork_id") or raw.get("id")),
        "primary_driver": _text(raw.get("primary_driver") or raw.get("driver")),
        "causal_question": _text(raw.get("causal_question")),
        "confidence": _text(raw.get("confidence")).lower(),
        "material": raw.get("material") is not False,
        "supporting_evidence_refs": _string_list(raw.get("supporting_evidence_refs")) or [],
        "opposing_evidence_refs": _string_list(raw.get("opposing_evidence_refs")) or [],
        "evidence_gaps": _string_list(raw.get("evidence_gaps")) or [],
        "options": options,
        "analysis_lean": _text(raw.get("analysis_lean")).upper() or None,
    }


def _normalized_options(raw: Any) -> list[dict[str, str]] | None:
    if not isinstance(raw, list) or len(raw) != 3:
        return None
    normalized: dict[str, dict[str, str]] = {}
    stories: set[str] = set()
    for option in raw:
        if not isinstance(option, dict):
            return None
        label = _text(option.get("label")).upper()
        story = _text(option.get("story"))
        falsifier = _text(option.get("falsifier"))
        if label not in FRAMING_OPTION_LABELS or not story or not falsifier or story in stories:
            return None
        normalized[label] = {"label": label, "story": story, "falsifier": falsifier}
        stories.add(story)
    if set(normalized) != set(FRAMING_OPTION_LABELS):
        return None
    return [normalized[label] for label in FRAMING_OPTION_LABELS]


def _available_evidence_references(raw: Any) -> set[str]:
    items = raw if isinstance(raw, list) else []
    refs: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ("evidence_id", "id", "source_url", "sourceUrl"):
            value = _text(item.get(key))
            if value:
                refs.add(value)
    return refs


def _contains_model_number(raw: Any, key: str = "") -> bool:
    if isinstance(raw, bool) or raw is None:
        return False
    if isinstance(raw, (int, float)):
        return True
    if isinstance(raw, str):
        return key not in _NON_CONTENT_STRING_KEYS and (
            any(character.isdigit() for character in raw) or _ENGLISH_NUMBER_WORD.search(raw) is not None
        )
    if isinstance(raw, dict):
        for child_key, value in raw.items():
            normalized_key = _text(child_key).lower()
            if normalized_key in _NUMERIC_KEYS:
                return True
            if _contains_model_number(value, normalized_key):
                return True
    elif isinstance(raw, list):
        return any(_contains_model_number(value, key) for value in raw)
    return False


def _string_list(raw: Any) -> list[str] | None:
    if not isinstance(raw, list) or any(not isinstance(value, str) or not value.strip() for value in raw):
        return None
    return [value.strip() for value in raw]


def _rejection(raw: Any, code: str, reason: str) -> dict[str, Any]:
    return {
        "fork_id": _text(raw.get("fork_id") or raw.get("id")) if isinstance(raw, dict) else "",
        "primary_driver": _text(raw.get("primary_driver") or raw.get("driver")) if isinstance(raw, dict) else "",
        "material": raw.get("material") is not False if isinstance(raw, dict) else False,
        "code": code,
        "reason": reason,
    }


def _text(raw: Any) -> str:
    return str(raw).strip() if raw is not None else ""
