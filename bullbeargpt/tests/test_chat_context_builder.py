from services.chat_context_builder import build_full_valuation_context


def test_context_builder_includes_input_output_extracts_and_recent_theses():
    context = build_full_valuation_context(
        ticker="NVDA",
        name="NVIDIA",
        valuation_data={"ticker": "NVDA"},
        valuation_input_json={
            "initialCostCapital": 10.0,
            "segments": {"segments": [{"sector": "semiconductors"}]},
        },
        valuation_output_json={
            "currency": "USD",
            "companyDTO": {"estimatedValuePerShare": 120.0, "price": 90.0},
            "financialDTO": {
                "costOfCapital": [10.0, 9.5],
                "revenueGrowthRate": [None, 12.0],
                "ebitOperatingMargin": [None, 28.0],
                "salesToCapitalRatio": [None, 2.4],
            },
            "terminalValueDTO": {"costOfCapital": 9.0, "growthRate": 3.0},
        },
        recent_theses=[
            {
                "title": "Prior NVDA thesis",
                "summary": "Old summary",
                "preview_json": {
                    "title": "Prior NVDA thesis",
                    "summary": "Demand remains AI-led.",
                    "fair_value": 130.0,
                    "current_price": 95.0,
                    "upside": 36.8,
                    "conviction": "high",
                    "timeframe": "12m",
                    "key_assumptions": ["Data center demand"],
                    "risks": ["Capex slowdown"],
                },
            }
        ],
    )

    assert "CURRENT VALUATION INPUT EXTRACTS" in context
    assert "Segment sectors: semiconductors" in context
    assert "CURRENT VALUATION OUTPUT EXTRACTS" in context
    assert "Fair value per share: 120.0" in context
    assert "RECENT SAVED THESES (MAX 2)" in context
    assert "Prior NVDA thesis" in context
    assert "Demand remains AI-led." in context
