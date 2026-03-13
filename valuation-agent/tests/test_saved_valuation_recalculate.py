import importlib

from storage.persistence.valuation_persistence import ValuationPersistenceService


def test_save_and_get_valuation_preserves_input_output_json(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    service = ValuationPersistenceService()

    valuation_id = service.save_valuation(
        ticker="NVDA",
        company_name="NVIDIA",
        valuation_data={"ticker": "NVDA"},
        input_json={"initialCostCapital": 10.0},
        output_json={"companyDTO": {"estimatedValuePerShare": 120.0, "price": 90.0}},
    )

    record = service.get_valuation_by_id(valuation_id)

    assert record is not None
    assert record["input_json"]["initialCostCapital"] == 10.0
    assert record["output_json"]["companyDTO"]["estimatedValuePerShare"] == 120.0


def test_saved_valuation_recalculate_endpoint_updates_persisted_record(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SECRET_KEY", "test-valuation-agent-secret")

    app_module = importlib.import_module("api.app")
    local_service = ValuationPersistenceService()
    monkeypatch.setattr(app_module, "valuation_service", local_service)

    valuation_id = local_service.save_valuation(
        ticker="NVDA",
        company_name="NVIDIA",
        valuation_data={
            "ticker": "NVDA",
            "company_name": "NVIDIA",
            "financials": {"current_price": 90.0},
            "dcf_analysis": {"fair_value": 110.0, "intrinsic_value": 110.0},
            "valuation_metadata": {
                "baseline_financial_data_input": {},
                "recalculate_financial_data_input": {"segments": {"segments": []}},
            },
        },
        input_json={"segments": {"segments": []}},
        output_json={"companyDTO": {"estimatedValuePerShare": 110.0, "price": 90.0}},
    )

    app = app_module.StockValuationApp()

    def _fake_recalc(ticker, overrides, auth_header=None):
        assert ticker == "NVDA"
        assert overrides["initialCostCapital"] == 10.0
        return {
            "currency": "USD",
            "companyDTO": {
                "estimatedValuePerShare": 100.0,
                "price": 90.0,
            },
            "financialDTO": {
                "costOfCapital": [10.0, 9.5],
                "revenueGrowthRate": [None, 12.0, 11.0],
                "ebitOperatingMargin": [None, 25.0, 25.0],
                "salesToCapitalRatio": [None, 2.0, 2.0, 2.0, 2.0, 2.0, 1.8],
            },
            "terminalValueDTO": {
                "costOfCapital": 9.5,
                "growthRate": 3.0,
            },
        }

    monkeypatch.setattr(app.valuation_service_client, "recalculate_valuation", _fake_recalc)

    client = app.app.test_client()
    response = client.post(
        f"/api-s/valuation/{valuation_id}/recalculate",
        json={"top_level_overrides": {"wacc": 10.0}, "persist": True},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["input_json"]["initialCostCapital"] == 10.0
    assert payload["output_json"]["companyDTO"]["estimatedValuePerShare"] == 100.0
    assert payload["valuation_data"]["dcf_analysis"]["fair_value"] == 100.0

    saved_record = local_service.get_valuation_by_id(valuation_id)
    assert saved_record["input_json"]["initialCostCapital"] == 10.0
    assert saved_record["output_json"]["companyDTO"]["estimatedValuePerShare"] == 100.0
