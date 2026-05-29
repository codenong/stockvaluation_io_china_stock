from valuation_agent.evidence_packet import validate_evidence_packet


def _source_family(family="annual_report", status="checked"):
    return {
        "family": family,
        "status": status,
        "source_title": "FY annual report",
        "source_url": "https://example.com/msft-annual-report",
        "source_date": "2026-06-30",
    }


def _evidence_item(**overrides):
    item = {
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
    item.update(overrides)
    return item


def _packet(**overrides):
    packet = {
        "ticker": "MSFT",
        "company": "Microsoft Corporation",
        "run_mode": "full_researched",
        "source_families": [_source_family()],
        "sources_checked": [
            {
                "source_title": "FY annual report",
                "source_url": "https://example.com/msft-annual-report",
                "source_date": "2026-06-30",
                "source_type": "annual_report",
                "used": True,
            }
        ],
        "evidence_items": [_evidence_item()],
        "conflicts_or_uncertainties": [],
        "data_gaps": [],
    }
    packet.update(overrides)
    return packet


def test_validate_evidence_packet_accepts_governed_driver_evidence():
    result = validate_evidence_packet(_packet())

    assert result["ok"] is True
    assert result["status"] == "valid_governed_evidence"
    assert result["validation_warnings"] == []
    assert result["unsupported_blockers"] == []
    assert result["source_family_status"] == [
        {
            "family": "annual_report",
            "status": "checked",
            "source_title": "FY annual report",
            "source_url": "https://example.com/msft-annual-report",
            "source_date": "2026-06-30",
        }
    ]
    assert result["governed_evidence"] == [
        {
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
    ]
    assert result["report_only_evidence"] == []
    assert result["rejected_evidence"] == []
    assert result["sanitized_packet"]["ticker"] == "MSFT"


def test_validate_evidence_packet_requires_packet_and_evidence_fields():
    packet = _packet(ticker="", source_families=[], evidence_items=[_evidence_item(source_url="")])

    result = validate_evidence_packet(packet)

    assert result["ok"] is False
    assert result["status"] == "invalid_packet"
    assert "ticker is required." in result["validation_warnings"]
    assert "source_families must contain at least one source-family status." in result["validation_warnings"]
    assert result["rejected_evidence"] == [
        {
            "item": {
                "driver": "revenue_growth",
                "source_title": "FY annual report",
                "source_url": "",
                "source_date": "2026-06-30",
                "evidence_summary": "Commercial cloud revenue increased 21% year over year.",
                "direction": "supports higher assumption",
                "confidence": "high",
                "assumption_implication": "Supports a modestly higher revenue CAGR than the mechanical baseline.",
                "allowed_to_affect_autonomous_recalculation": True,
                "model_action": "governed assumption change",
            },
            "status": "missing_required_evidence_field",
            "reason": "source_url is required.",
        }
    ]
    assert result["governed_evidence"] == []


def test_validate_evidence_packet_separates_governed_report_only_and_unsupported_driver_evidence():
    result = validate_evidence_packet(
        _packet(
            evidence_items=[
                _evidence_item(),
                _evidence_item(
                    driver="operating_margin",
                    evidence_summary="Gross margin was stable despite higher AI infrastructure costs.",
                    allowed_to_affect_autonomous_recalculation=False,
                    model_action="report explanation only",
                ),
                _evidence_item(
                    driver="risk_wacc",
                    evidence_summary="The company disclosed regulatory risk in its latest filing.",
                    allowed_to_affect_autonomous_recalculation=True,
                    model_action="governed assumption change",
                ),
            ]
        )
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_by_unsupported_fields"
    assert [item["driver"] for item in result["governed_evidence"]] == ["revenue_growth"]
    assert [item["driver"] for item in result["report_only_evidence"]] == ["operating_margin"]
    assert result["rejected_evidence"][0]["status"] == "unsupported_governed_driver"
    assert result["rejected_evidence"][0]["item"]["driver"] == "risk_wacc"
    assert result["unsupported_blockers"] == [
        {
            "field": "risk_wacc",
            "status": "unsupported_governed_driver",
            "reason": "risk_wacc is report-only in autonomous researched evidence validation.",
        }
    ]


def test_validate_evidence_packet_rejects_unknown_evidence_drivers():
    result = validate_evidence_packet(
        _packet(
            evidence_items=[
                _evidence_item(
                    driver="market_price",
                    evidence_summary="The stock traded above the mechanical baseline.",
                    allowed_to_affect_autonomous_recalculation=False,
                    model_action="report explanation only",
                )
            ]
        )
    )

    assert result["ok"] is False
    assert result["status"] == "invalid_packet"
    assert result["rejected_evidence"][0]["status"] == "unsupported_driver"
    assert result["rejected_evidence"][0]["reason"] == "market_price is not a supported EvidencePacket driver."
    assert result["governed_evidence"] == []
    assert result["report_only_evidence"] == []


def test_validate_evidence_packet_rejects_generic_source_presence_and_search_result_urls():
    result = validate_evidence_packet(
        _packet(
            evidence_items=[
                _evidence_item(evidence_summary="10-K found."),
                _evidence_item(
                    source_url="https://www.google.com/search?q=MSFT+10-K",
                    evidence_summary="Cloud revenue grew faster than company revenue.",
                ),
            ]
        )
    )

    assert result["ok"] is False
    assert result["status"] == "invalid_packet"
    assert result["governed_evidence"] == []
    assert [item["status"] for item in result["rejected_evidence"]] == [
        "generic_source_presence",
        "search_result_url",
    ]
    assert [item["reason"] for item in result["rejected_evidence"]] == [
        "Generic source presence is not valuation-driver evidence.",
        "source_url must be a direct source URL, not a search-result URL.",
    ]


def test_validate_evidence_packet_rejects_malformed_source_url_and_date():
    result = validate_evidence_packet(
        _packet(
            evidence_items=[
                _evidence_item(source_url="not-a-url"),
                _evidence_item(source_date="not-a-date"),
            ]
        )
    )

    assert result["ok"] is False
    assert result["status"] == "invalid_packet"
    assert [item["status"] for item in result["rejected_evidence"]] == [
        "invalid_source_url",
        "invalid_source_date",
    ]
    assert [item["reason"] for item in result["rejected_evidence"]] == [
        "source_url must be a valid http(s) direct source URL.",
        "source_date must be YYYY-MM-DD or unknown.",
    ]


def test_validate_evidence_packet_fails_closed_for_weak_mixed_or_undated_governed_changes():
    result = validate_evidence_packet(
        _packet(
            evidence_items=[
                _evidence_item(confidence="low"),
                _evidence_item(direction="neutral/mixed", confidence="medium"),
                _evidence_item(source_date="unknown"),
            ]
        )
    )

    assert result["ok"] is True
    assert result["status"] == "valid_no_governed_change"
    assert result["governed_evidence"] == []
    assert [item["status"] for item in result["rejected_evidence"]] == [
        "low_confidence_governed_change",
        "mixed_governed_change",
        "undated_governed_change",
    ]
    assert result["validation_warnings"] == [
        "No governed evidence accepted; weak, mixed, or undated evidence is report context only."
    ]


def test_validate_evidence_packet_preserves_source_family_status_without_source_count_gate():
    result = validate_evidence_packet(
        _packet(
            source_families=[
                _source_family("annual_report", "checked"),
                {
                    "family": "investor_presentation_or_transcript",
                    "status": "missing",
                    "reason": "No current investor presentation or transcript found in the research pass.",
                },
            ],
            data_gaps=[
                {
                    "family": "investor_presentation_or_transcript",
                    "reason": "No current investor presentation or transcript found in the research pass.",
                }
            ],
        )
    )

    assert result["ok"] is True
    assert result["status"] == "valid_governed_evidence"
    assert result["source_family_status"][1] == {
        "family": "investor_presentation_or_transcript",
        "status": "missing",
        "reason": "No current investor presentation or transcript found in the research pass.",
    }
    assert result["sanitized_packet"]["data_gaps"] == [
        {
            "family": "investor_presentation_or_transcript",
            "reason": "No current investor presentation or transcript found in the research pass.",
        }
    ]


def test_validate_evidence_packet_requires_direct_source_family_metadata_for_checked_sources():
    result = validate_evidence_packet(
        _packet(
            source_families=[
                {
                    "family": "annual_report",
                    "status": "checked",
                    "source_title": "Search results",
                    "source_url": "https://www.google.com/search?q=MSFT+annual+report",
                }
            ]
        )
    )

    assert result["ok"] is False
    assert result["status"] == "invalid_packet"
    assert result["validation_warnings"] == [
        "source_families[0] checked status requires direct source_url and source_date."
    ]


def test_validate_evidence_packet_sanitizes_accepted_evidence_metadata():
    result = validate_evidence_packet(
        _packet(
            evidence_items=[
                _evidence_item(
                    evidence_summary="Commercial cloud revenue increased 21%; API_KEY=secret-123",
                    assumption_implication="TOKEN=abc123 supports a modest revenue-growth change.",
                )
            ]
        )
    )

    assert result["ok"] is True
    assert result["governed_evidence"][0]["evidence_summary"].endswith("API_KEY=[REDACTED]")
    assert result["governed_evidence"][0]["assumption_implication"].startswith(
        "TOKEN=[REDACTED] supports"
    )
