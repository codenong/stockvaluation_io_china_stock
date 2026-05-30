import json
from pathlib import Path

from valuation_agent.evidence_packet import validate_evidence_packet
from valuation_agent.valuation_audit_packet import validate_valuation_audit_packet

REPO_ROOT = Path(__file__).resolve().parents[3]
PHASE_2_ACCEPTANCE_CASES = (
    REPO_ROOT
    / "valuation-agent"
    / "tests"
    / "agent_native"
    / "fixtures"
    / "phase_2_valuation_audit_packet_cases.json"
)


def _evidence_packet(**item_overrides):
    evidence_item = {
        "driver": "revenue_growth",
        "source_title": "FY annual report",
        "source_url": "https://example.com/msft-annual-report",
        "source_date": "2026-06-30",
        "evidence_summary": "Commercial cloud revenue increased 21% year over year.",
        "direction": "supports higher assumption",
        "confidence": "high",
        "assumption_implication": "Supports a modestly higher revenue CAGR than the mechanical baseline.",
        "allowed_to_affect_autonomous_recalculation": True,
        "model_action": "governed assumption change",
    }
    evidence_item.update(item_overrides)
    return {
        "ticker": "MSFT",
        "company": "Microsoft Corporation",
        "run_mode": "full_researched",
        "source_families": [
            {
                "family": "annual_report",
                "status": "checked",
                "source_title": "FY annual report",
                "source_url": "https://example.com/msft-annual-report",
                "source_date": "2026-06-30",
            }
        ],
        "sources_checked": [
            {
                "source_title": "FY annual report",
                "source_url": "https://example.com/msft-annual-report",
                "source_date": "2026-06-30",
                "status": "checked",
                "source_type": "annual_report",
                "used": True,
            }
        ],
        "evidence_items": [evidence_item],
        "conflicts_or_uncertainties": [],
        "data_gaps": [],
    }


def _valid_evidence_result():
    return validate_evidence_packet(_evidence_packet())


def _rejected_evidence_result():
    return validate_evidence_packet(
        _evidence_packet(
            evidence_summary="10-K found.",
            allowed_to_affect_autonomous_recalculation=True,
        )
    )


def _no_change_evidence_result():
    return validate_evidence_packet(_evidence_packet(confidence="low"))


def _missing_evidence_result():
    return {
        "ok": False,
        "status": "missing_evidence_packet",
        "sanitized_packet": {},
        "governed_evidence": [],
        "report_only_evidence": [],
        "rejected_evidence": [],
        "source_family_status": [],
        "validation_warnings": ["EvidencePacket was not provided."],
        "unsupported_blockers": [
            {
                "status": "missing_evidence_packet_for_requested_changes",
                "reason": "missing_evidence_packet_for_requested_changes",
            }
        ],
    }


def _packet(**overrides):
    packet = {
        "ticker": "MSFT",
        "company": "Microsoft Corporation",
        "run_mode": "full_researched",
        "evidence_packet": _valid_evidence_result(),
        "segment_validation": {
            "baseline_quality": "segment_weighted_baseline",
            "segment_aware": True,
            "validation_warnings": [],
        },
        "baseline_plausibility": {
            "status": "accepted",
            "unsupported_blockers": [],
        },
        "assumption_judgment": {
            "status": "governed_recalculation_supported",
            "assumptions_left_unchanged": [],
        },
        "recalculate_payloads": [
            {
                "kind": "autonomous_researched",
                "requested": {"revenue_growth": 0.09},
                "mapped": {"compoundAnnualGrowth2_5": 9.0},
                "unsupported": {},
                "effective": {"revenue_growth": 7.0},
                "metadata": {"request_policy": {"mode": "autonomous_researched"}},
                "status": "executed",
            }
        ],
        "assumption_buckets": {
            "requested": {"revenue_growth": 0.09},
            "mapped": {"compoundAnnualGrowth2_5": 9.0},
            "unsupported": {},
            "metadata": {"evidence_packet": {"status": "valid_governed_evidence"}},
            "effective": {"revenue_growth": 7.0},
        },
        "guided_refinement": {
            "status": "not_started",
            "bypass_reason": None,
            "user_judgment": None,
        },
        "final_case_type": "evidence_constrained_governed_recalculation",
        "final_report_inputs": {
            "summary": "Evidence supports a governed revenue-growth recalculation.",
        },
        "data_quality_limitations": [],
        "mcp_call_references": [
            {"tool": "stockvaluation.recalculate", "status": "ok"},
        ],
        "accounting_decisions": {
            "requested": {},
            "mapped": {},
            "unsupported": {},
            "report_only": [],
            "governed_scenarios": [],
            "rejected": [],
            "metadata": {},
            "effective": [],
        },
    }
    packet.update(overrides)
    return packet


def test_validate_valuation_audit_packet_accepts_minimal_phase_1_backed_packet():
    result = validate_valuation_audit_packet(_packet())

    assert result["ok"] is True
    assert result["status"] == "valid_audit_packet"
    packet = result["packet"]
    assert packet["schema_version"] == "valuation_audit_packet.v1"
    assert packet["final_case_type"] == "evidence_constrained_governed_recalculation"
    assert packet["evidence_packet"]["status"] == "valid_governed_evidence"
    assert packet["evidence_packet"]["governed_evidence"][0]["driver"] == "revenue_growth"
    assert packet["assumption_buckets"]["requested"] == {"revenue_growth": 0.09}
    assert result["summary"] == {
        "packet_status": "valid_audit_packet",
        "final_case_type": "evidence_constrained_governed_recalculation",
        "evidence_status": "valid_governed_evidence",
        "guided_refinement_status": "not_started",
    }


def test_validate_valuation_audit_packet_requires_user_facing_final_case_type():
    missing = _packet(final_case_type="")
    mechanical = _packet(final_case_type="mechanical_baseline")

    missing_result = validate_valuation_audit_packet(missing)
    mechanical_result = validate_valuation_audit_packet(mechanical)

    assert missing_result["ok"] is False
    assert "final_case_type is required." in missing_result["validation_warnings"]
    assert mechanical_result["ok"] is False
    assert mechanical_result["validation_warnings"] == ["final_case_type is unsupported."]
    assert mechanical_result["summary"]["final_case_type"] == "mechanical_baseline"


def test_validate_valuation_audit_packet_rejects_missing_required_sections():
    packet = _packet()
    del packet["segment_validation"]
    del packet["assumption_buckets"]["effective"]
    del packet["accounting_decisions"]

    result = validate_valuation_audit_packet(packet)

    assert result["ok"] is False
    assert "segment_validation is required." in result["validation_warnings"]
    assert "assumption_buckets.effective is required." in result["validation_warnings"]
    assert "accounting_decisions is required." in result["validation_warnings"]


def test_validate_valuation_audit_packet_keeps_mechanical_baseline_internal_only():
    result = validate_valuation_audit_packet(
        _packet(
            internal_state={
                "mechanical_baseline": {
                    "visibility": "user_facing",
                    "estimatedValuePerShare": 412.34,
                }
            }
        )
    )

    assert result["ok"] is False
    assert result["validation_warnings"] == [
        "internal_state.mechanical_baseline.visibility must be internal_only."
    ]


def test_validate_valuation_audit_packet_rejects_visible_mechanical_baseline_case():
    result = validate_valuation_audit_packet(
        _packet(
            final_report_inputs={
                "summary": "Evidence was insufficient.",
                "visible_scenarios": [{"case_type": "mechanical_baseline"}],
            }
        )
    )

    assert result["ok"] is False
    assert result["validation_warnings"] == [
        "final_report_inputs must not expose mechanical_baseline as a visible report case or scenario."
    ]


def test_validate_valuation_audit_packet_redacts_unsafe_serialized_material(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "postgres-live-secret")

    result = validate_valuation_audit_packet(
        _packet(
            final_report_inputs={
                "summary": "Evidence supports a governed revenue-growth recalculation.",
                "env_path": "/repo/.env",
                "raw_article_body": "Full article body that should not be serialized.",
                "raw_filing_body": "Full 10-K body that should not be serialized.",
                "prompt_dump_path": "/tmp/prompt_dump_from_container/run.txt",
                "local_data_path": "/repo/local_data/runtime.json",
                "search_traces": ["broad search trace should not be serialized"],
                "secret_note": "POSTGRES_PASSWORD=postgres-live-secret failed",
            },
            mcp_call_references=[
                {
                    "tool": "stockvaluation.recalculate",
                    "status": "ok",
                    "authorization": "Bearer postgres-live-secret",
                }
            ],
        )
    )

    serialized = json.dumps(result["packet"], sort_keys=True)
    assert result["ok"] is True
    for prohibited in [
        "postgres-live-secret",
        "/repo/.env",
        "Full article body",
        "Full 10-K body",
        "prompt_dump_from_container",
        "local_data",
        "broad search trace",
    ]:
        assert prohibited not in serialized
    assert "[REDACTED]" in serialized


def test_validate_valuation_audit_packet_preserves_rejected_evidence_and_unsupported_fields():
    rejected_evidence = _rejected_evidence_result()
    result = validate_valuation_audit_packet(
        _packet(
            evidence_packet=rejected_evidence,
            final_case_type="insufficient_researched_evidence",
            assumption_buckets={
                "requested": {"wacc": 8.5, "terminal_growth": 3.0},
                "mapped": {},
                "unsupported": {
                    "wacc": {"status": "scenario_only_in_autonomous_researched_mode"},
                    "terminal_growth": {"status": "scenario_only_in_autonomous_researched_mode"},
                },
                "metadata": {"evidence_packet": {"status": rejected_evidence["status"]}},
                "effective": {},
            },
        )
    )

    assert result["ok"] is True
    packet = result["packet"]
    assert packet["evidence_packet"]["ok"] is False
    assert packet["evidence_packet"]["rejected_evidence"][0]["status"] == "generic_source_presence"
    assert set(packet["assumption_buckets"]["unsupported"]) == {"wacc", "terminal_growth"}


def test_phase_2_acceptance_fixture_cases_validate_required_paths():
    matrix = json.loads(PHASE_2_ACCEPTANCE_CASES.read_text(encoding="utf-8"))
    cases = matrix["cases"]

    assert matrix["purpose"] == "phase_2_valuation_audit_packet_acceptance"
    assert {case["name"] for case in cases} == {
        "full_researched_governed_recalculation",
        "evidence_constrained_no_change",
        "quick_no_questions_bypass",
        "rejected_evidence_preserved",
        "mechanical_only_insufficient_evidence",
    }

    evidence_by_status = {
        "valid_governed_evidence": _valid_evidence_result(),
        "valid_no_governed_change": _no_change_evidence_result(),
        "invalid_packet": _rejected_evidence_result(),
        "missing_evidence_packet": _missing_evidence_result(),
    }
    for case in cases:
        unsupported = {
            field: {"status": "acceptance_fixture_blocker"}
            for field in case.get("unsupported_fields", [])
        }
        result = validate_valuation_audit_packet(
            _packet(
                evidence_packet=evidence_by_status[case["evidence_status"]],
                final_case_type=case["final_case_type"],
                guided_refinement={
                    "status": case["guided_refinement_status"],
                    "bypass_reason": "quick valuation requested"
                    if case["guided_refinement_status"] == "bypassed"
                    else None,
                    "user_judgment": None,
                },
                recalculate_payloads=[
                    {
                        "kind": "acceptance_fixture",
                        "requested": {},
                        "mapped": {},
                        "unsupported": unsupported,
                        "effective": {},
                        "metadata": {},
                        "status": case["recalculate_status"],
                    }
                ],
                assumption_buckets={
                    "requested": {},
                    "mapped": {},
                    "unsupported": unsupported,
                    "metadata": {"evidence_packet": {"status": case["evidence_status"]}},
                    "effective": {},
                },
                internal_state={
                    "mechanical_baseline": {
                        "visibility": case.get("mechanical_baseline_visibility", "internal_only"),
                        "baseline_use_status": "mechanical_only",
                    }
                },
            )
        )

        assert result["ok"] is True
        assert result["summary"]["final_case_type"] == case["final_case_type"]
        assert result["summary"]["evidence_status"] == case["evidence_status"]
        assert result["summary"]["guided_refinement_status"] == case["guided_refinement_status"]
        if "rejected_evidence_status" in case:
            assert (
                result["packet"]["evidence_packet"]["rejected_evidence"][0]["status"]
                == case["rejected_evidence_status"]
            )
