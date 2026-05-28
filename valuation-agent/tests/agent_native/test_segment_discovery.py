from valuation_agent.segment_discovery import build_segment_search_plan, sanitize_segment_package


def test_segment_discovery_search_plan_prefers_official_company_domains():
    plan = build_segment_search_plan(
        company_name="NVIDIA Corporation",
        ticker="NVDA",
        company_url="https://www.nvidia.com/en-us/",
        industry="Semiconductors",
        description="Accelerated computing platforms, data center, gaming, and automotive systems.",
    )

    assert plan["company"] == "NVIDIA Corporation"
    assert plan["domains"][:3] == ["nvidia.com", "investor.nvidia.com", "investors.nvidia.com"]
    assert "sec.gov" in plan["fallback_domains"]
    assert plan["queries"]
    assert len(plan["queries"][0]["query"]) <= 400
    assert "segment revenue" in plan["queries"][0]["query"].lower()
    assert "10-k" in plan["queries"][0]["query"].lower()


def test_segment_package_sanitizer_rejects_generic_or_names_only_evidence():
    result = sanitize_segment_package(
        {
            "segments": [
                {
                    "segment_name": "Data Center",
                    "mapped_industry": "Semiconductor",
                    "mapping_confidence": "high",
                    "source_name": "FY 10-K found",
                    "source_date": "2026-03-01",
                    "source_url": "https://example.com/10k",
                }
            ]
        }
    )

    assert result["baseline_quality"] == "segment_evidence_insufficient"
    assert result["segment_aware"] is False
    assert result["segment_coverage_pct"] == 0.0
    assert result["segments"] == []
    assert any("revenue weights" in warning for warning in result["validation_warnings"])
    assert any("generic source presence" in warning for warning in result["validation_warnings"])


def test_segment_package_sanitizer_rejects_weighted_segments_with_generic_source_presence():
    result = sanitize_segment_package(
        {
            "segments": [
                {
                    "segment_name": "Data Center",
                    "mapped_industry": "Semiconductor",
                    "mapping_confidence": "high",
                    "revenue_share": 100.0,
                    "source_name": "FY 10-K segment table found",
                    "source_date": "2026-03-01",
                    "source_url": "https://example.com/10k",
                }
            ]
        }
    )

    assert result["baseline_quality"] == "segment_evidence_insufficient"
    assert result["segment_aware"] is False
    assert result["segments"] == []
    assert any("generic source presence" in warning for warning in result["validation_warnings"])


def test_segment_package_sanitizer_rejects_weights_without_source_metadata():
    result = sanitize_segment_package(
        {
            "segments": [
                {
                    "segment_name": "Cloud",
                    "mapped_industry": "Software",
                    "mapping_confidence": "high",
                    "revenue_share": 1.0,
                    "source_name": "FY 10-K segment table",
                }
            ]
        }
    )

    assert result["baseline_quality"] == "segment_evidence_insufficient"
    assert result["segment_aware"] is False
    assert result["segments"] == []
    assert any("source metadata" in warning for warning in result["validation_warnings"])
