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
REVEALED_THESIS_SCHEMA_VERSION = "revealed_thesis.v1"
FRAMING_CONFIDENCES = frozenset({"low", "medium", "high"})
FRAMING_OPTION_LABELS = ("A", "B", "C")
REVEALED_THESIS_UNRESOLVED_STATEMENT = (
    "The revealed thesis is unresolved because no guided framing answers were recorded."
)
CHOICE_D_INTERPRETATIONS = {
    "numeric_user_input": "Custom numeric scenario input recorded as user input; it is not independent evidence.",
    "segment_user_input": "Custom segment scenario package recorded as user input; service weighting remains authoritative.",
    "report_only": "Custom report-only judgment recorded without changing valuation math.",
    "unsupported": "Custom unsupported judgment recorded as unresolved and excluded from valuation math.",
}
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


def revealed_thesis_output_schema() -> dict[str, Any]:
    """Closed schema for the report-authoritative guided decision trail."""
    string_array = {"type": "array", "items": {"type": "string"}}
    evidence_item = {
        "type": "object",
        "additionalProperties": True,
    }
    mapped_effect = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string"},
            "field": {"type": ["string", "null"]},
            "value": {},
            "source": {"type": "string"},
        },
        "required": ["status", "field", "value", "source"],
    }
    question_ref = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "question_id": {"type": "string"},
            "plan_order": {"type": "integer"},
            "driver": {"type": "string"},
            "question": {"type": "string"},
        },
        "required": ["question_id", "plan_order", "driver", "question"],
    }
    interpretation_ref = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "question_id": {"type": "string"},
            "driver": {"type": "string"},
            "selected_choice": {"type": "string", "enum": ["A", "B", "C", "D"]},
            "interpretation": {"type": "string"},
        },
        "required": ["question_id", "driver", "selected_choice", "interpretation"],
    }
    mapping_ref = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "question_id": {"type": "string"},
            "driver": {"type": "string"},
            "model_action": {"type": "string"},
            "mapped_effect": mapped_effect,
        },
        "required": ["question_id", "driver", "model_action", "mapped_effect"],
    }
    evidence_ref = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "question_id": {"type": "string"},
            "supporting_evidence_refs": string_array,
            "opposing_evidence_refs": string_array,
            "evidence_gaps": string_array,
            "evidence_used": {"type": "array", "items": evidence_item},
        },
        "required": ["question_id", "supporting_evidence_refs", "opposing_evidence_refs", "evidence_gaps", "evidence_used"],
    }
    falsifier_ref = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "question_id": {"type": "string"},
            "driver": {"type": "string"},
            "falsifier": {"type": "string"},
        },
        "required": ["question_id", "driver", "falsifier"],
    }
    decision = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "question_id": {"type": "string"},
            "plan_order": {"type": "integer"},
            "driver": {"type": "string"},
            "framing_question": {"type": "string"},
            "selected_choice": {"type": "string", "enum": ["A", "B", "C", "D"]},
            "recommended_choice": {"type": "string"},
            "used_recommended_choice": {"type": "boolean"},
            "selected_interpretation": {"type": "string"},
            "thesis_clause": {"type": "string"},
            "assumption_effect": {"type": "string"},
            "model_action": {"type": "string"},
            "mapped_effect": mapped_effect,
            "supporting_evidence_refs": string_array,
            "opposing_evidence_refs": string_array,
            "evidence_gaps": string_array,
            "evidence_used": {"type": "array", "items": evidence_item},
            "falsifier": {"type": "string"},
            "anchor_provenance": {"type": "object", "additionalProperties": True},
            "anchor_explanation": {"type": ["string", "null"]},
            "coherence_caveats": string_array,
        },
        "required": [
            "question_id",
            "plan_order",
            "driver",
            "framing_question",
            "selected_choice",
            "recommended_choice",
            "used_recommended_choice",
            "selected_interpretation",
            "thesis_clause",
            "assumption_effect",
            "model_action",
            "mapped_effect",
            "supporting_evidence_refs",
            "opposing_evidence_refs",
            "evidence_gaps",
            "evidence_used",
            "falsifier",
            "anchor_provenance",
            "anchor_explanation",
            "coherence_caveats",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "const": REVEALED_THESIS_SCHEMA_VERSION},
            "source_type": {"type": "string", "const": "guided_answer_trail"},
            "plan_id": {"type": "string"},
            "status": {"type": "string", "enum": ["resolved", "unresolved"]},
            "investment_thesis": {"type": "string"},
            "framing_questions": {"type": "array", "items": question_ref},
            "selected_interpretations": {"type": "array", "items": interpretation_ref},
            "driver_mappings": {"type": "array", "items": mapping_ref},
            "evidence": {"type": "array", "items": evidence_ref},
            "coherence_caveats": string_array,
            "falsifiers": {"type": "array", "items": falsifier_ref},
            "decisions": {"type": "array", "items": decision},
        },
        "required": [
            "schema_version",
            "source_type",
            "plan_id",
            "status",
            "investment_thesis",
            "framing_questions",
            "selected_interpretations",
            "driver_mappings",
            "evidence",
            "coherence_caveats",
            "falsifiers",
            "decisions",
        ],
    }


def build_revealed_thesis(
    plan: dict[str, Any],
    judgment: dict[str, Any],
    coherence_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the authoritative thesis from recorded guided answers."""
    question_order = [
        _text(question_id)
        for question_id in (plan.get("question_order") or [])
        if _text(question_id)
    ]
    questions = {
        _text(question.get("id")): question
        for question in (plan.get("questions") or [])
        if isinstance(question, dict) and _text(question.get("id"))
    }
    order_index = {question_id: index for index, question_id in enumerate(question_order)}
    answers = [
        answer
        for answer in (judgment.get("answers") or [])
        if isinstance(answer, dict) and _text(answer.get("question_id")) in questions
    ]
    answers.sort(key=lambda answer: order_index.get(_text(answer.get("question_id")), 10_000))
    caveats = _coherence_caveat_texts(coherence_review)
    decisions = [
        _revealed_decision(answer, questions[_text(answer.get("question_id"))], order_index, caveats)
        for answer in answers
    ]
    thesis_clauses = [_text(decision.get("thesis_clause")) for decision in decisions if _text(decision.get("thesis_clause"))]
    investment_thesis = " ".join(thesis_clauses) if thesis_clauses else REVEALED_THESIS_UNRESOLVED_STATEMENT
    status = "resolved" if thesis_clauses else "unresolved"
    return sanitize_for_agent(
        {
            "schema_version": REVEALED_THESIS_SCHEMA_VERSION,
            "source_type": "guided_answer_trail",
            "plan_id": _text(plan.get("plan_id")),
            "status": status,
            "investment_thesis": investment_thesis,
            "framing_questions": [
                {
                    "question_id": decision["question_id"],
                    "plan_order": decision["plan_order"],
                    "driver": decision["driver"],
                    "question": decision["framing_question"],
                }
                for decision in decisions
            ],
            "selected_interpretations": [
                {
                    "question_id": decision["question_id"],
                    "driver": decision["driver"],
                    "selected_choice": decision["selected_choice"],
                    "interpretation": decision["selected_interpretation"],
                }
                for decision in decisions
            ],
            "driver_mappings": [
                {
                    "question_id": decision["question_id"],
                    "driver": decision["driver"],
                    "model_action": decision["model_action"],
                    "mapped_effect": decision["mapped_effect"],
                }
                for decision in decisions
            ],
            "evidence": [
                {
                    "question_id": decision["question_id"],
                    "supporting_evidence_refs": decision["supporting_evidence_refs"],
                    "opposing_evidence_refs": decision["opposing_evidence_refs"],
                    "evidence_gaps": decision["evidence_gaps"],
                    "evidence_used": decision["evidence_used"],
                }
                for decision in decisions
            ],
            "coherence_caveats": caveats,
            "falsifiers": [
                {
                    "question_id": decision["question_id"],
                    "driver": decision["driver"],
                    "falsifier": decision["falsifier"],
                }
                for decision in decisions
                if _text(decision.get("falsifier"))
            ],
            "decisions": decisions,
        }
    )


def _revealed_decision(
    answer: dict[str, Any],
    question: dict[str, Any],
    order_index: dict[str, int],
    caveats: list[str],
) -> dict[str, Any]:
    question_id = _text(answer.get("question_id"))
    selected_choice = _resolved_choice_label(answer)
    choice = _choice_by_label(question, selected_choice)
    override = _dict(answer.get("requested_override"))
    mapped_effect = _mapped_effect(answer, override)
    interpretation = _selected_interpretation(selected_choice, choice, answer, override)
    thesis_clause = _thesis_clause(_text(question.get("driver")), interpretation)
    return {
        "question_id": question_id,
        "plan_order": order_index.get(question_id, 10_000),
        "driver": _text(question.get("driver") or answer.get("mapped_driver")),
        "framing_question": _text(question.get("causal_question") or question.get("question") or question.get("rationale")),
        "selected_choice": selected_choice,
        "recommended_choice": _text(answer.get("recommended_choice")),
        "used_recommended_choice": bool(answer.get("used_recommended_choice")),
        "selected_interpretation": interpretation,
        "thesis_clause": thesis_clause,
        "assumption_effect": _text(choice.get("assumption_effect")),
        "model_action": _text(answer.get("model_action")),
        "mapped_effect": mapped_effect,
        "supporting_evidence_refs": _string_list_or_empty(question.get("supporting_evidence_refs") or answer.get("supporting_evidence_refs")),
        "opposing_evidence_refs": _string_list_or_empty(question.get("opposing_evidence_refs")),
        "evidence_gaps": _string_list_or_empty(question.get("evidence_gaps")),
        "evidence_used": _list(question.get("evidence_used") or answer.get("evidence_used")),
        "falsifier": _text(choice.get("falsifier")),
        "anchor_provenance": _dict(answer.get("anchor_provenance")),
        "anchor_explanation": _text(answer.get("anchor_explanation")) or None,
        "coherence_caveats": caveats,
    }


def _mapped_effect(answer: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    field = _text(override.get("field")) or None
    value = override.get("value")
    reason = _text(answer.get("unsupported_or_report_only_reason"))
    if reason:
        status = reason
    elif field:
        status = "mapped"
    else:
        status = "unmapped"
    return {
        "status": status,
        "field": field,
        "value": sanitize_for_agent(value),
        "source": _text(answer.get("anchor_label")) or "none",
    }


def _selected_interpretation(
    selected_choice: str,
    choice: dict[str, Any],
    answer: dict[str, Any],
    override: dict[str, Any],
) -> str:
    if selected_choice != "D":
        return _text(choice.get("story"))
    reason = _text(answer.get("unsupported_or_report_only_reason"))
    model_action = _text(answer.get("model_action"))
    value = override.get("value")
    if isinstance(value, list):
        return CHOICE_D_INTERPRETATIONS["segment_user_input"]
    if model_action == "user scenario override":
        return CHOICE_D_INTERPRETATIONS["numeric_user_input"]
    if reason == "report_only_user_judgment" or model_action == "report-only user judgment":
        return CHOICE_D_INTERPRETATIONS["report_only"]
    return CHOICE_D_INTERPRETATIONS["unsupported"]


def _coherence_caveat_texts(coherence_review: dict[str, Any] | None) -> list[str]:
    review = _dict(coherence_review)
    caveats: list[str] = []
    status = _text(review.get("status"))
    if status in {"caveat_accepted", "awaiting_caveat_acceptance", "challenge_required"}:
        if status == "caveat_accepted":
            reason = _text(_dict(review.get("explicit_caveat")).get("reason"))
            caveats.append(reason or "The user accepted the recorded coherence caveat.")
        for issue in _list(review.get("issues")):
            if isinstance(issue, dict):
                message = _text(issue.get("message") or issue.get("issue") or issue.get("reason"))
                if message:
                    caveats.append(message)
    return _dedupe_strings(caveats)


def _resolved_choice_label(answer: dict[str, Any]) -> str:
    selected = _text(answer.get("selected_choice")).upper()
    if selected == "DEFAULT":
        selected = _text(answer.get("recommended_choice")).upper()
    return selected if selected in {"A", "B", "C", "D"} else "B"


def _choice_by_label(question: dict[str, Any], label: str) -> dict[str, Any]:
    for choice in _list(question.get("bounded_choices")):
        if _text(_dict(choice).get("label")).upper() == label:
            return _dict(choice)
    return {}


def _thesis_clause(driver: str, interpretation: str) -> str:
    if not interpretation:
        return ""
    driver_label = driver.replace("_", " ") if driver else "guided judgment"
    return f"{driver_label}: {interpretation}"


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        clean = _text(value)
        key = clean.lower()
        if clean and key not in seen:
            deduped.append(clean)
            seen.add(key)
    return deduped


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


def _dict(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _list(raw: Any) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _string_list_or_empty(raw: Any) -> list[str]:
    values = _string_list(raw)
    return values if values is not None else []


def _text(raw: Any) -> str:
    return str(raw).strip() if raw is not None else ""
