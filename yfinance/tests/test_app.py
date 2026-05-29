import json

import app as app_module


class FakeYFinanceService:
    def get_endpoint_map(self):
        return {
            "info": self.info,
            "financials": self.financials,
        }

    @staticmethod
    def info(ticker, freq):
        return {"ticker": ticker, "freq": freq, "source": "fake"}

    @staticmethod
    def financials(ticker, freq):
        return json.dumps({"ticker": ticker, "freq": freq, "rows": []})


def test_health_endpoint_reports_service_status():
    client = app_module.YFinanceApp().app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"
    assert response.get_json()["service"] == "stockvaluation.io.yfinance"


def test_api_endpoint_dispatches_to_service_and_normalizes_ticker(monkeypatch):
    monkeypatch.setattr(app_module, "YFinanceService", FakeYFinanceService)
    client = app_module.YFinanceApp().app.test_client()

    response = client.get("/api-s/info?ticker=msft&freq=quarterly")

    assert response.status_code == 200
    assert response.get_json() == {"ticker": "MSFT", "freq": "quarterly", "source": "fake"}


def test_api_endpoint_decodes_json_string_service_result(monkeypatch):
    monkeypatch.setattr(app_module, "YFinanceService", FakeYFinanceService)
    client = app_module.YFinanceApp().app.test_client()

    response = client.get("/api-s/financials?ticker=MSFT")

    assert response.status_code == 200
    assert response.get_json() == {"ticker": "MSFT", "freq": "yearly", "rows": []}


def test_default_api_response_shape_remains_unwrapped_for_existing_callers(monkeypatch):
    monkeypatch.setattr(app_module, "YFinanceService", FakeYFinanceService)
    client = app_module.YFinanceApp().app.test_client()

    response = client.get("/api-s/info?ticker=SAP.DE")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {"ticker": "SAP.DE", "freq": "yearly", "source": "fake"}
    assert "data" not in payload
    assert "sourceProvenance" not in payload


def test_api_endpoint_rejects_missing_ticker(monkeypatch):
    monkeypatch.setattr(app_module, "YFinanceService", FakeYFinanceService)
    client = app_module.YFinanceApp().app.test_client()

    response = client.get("/api-s/info")

    assert response.status_code == 400


def test_api_endpoint_rejects_unknown_endpoint(monkeypatch):
    monkeypatch.setattr(app_module, "YFinanceService", FakeYFinanceService)
    client = app_module.YFinanceApp().app.test_client()

    response = client.get("/api-s/not-real?ticker=MSFT")

    assert response.status_code == 404
