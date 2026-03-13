import importlib

from services.valuation_service_client import ValuationServiceClientError


def test_valuate_endpoint_includes_common_failure_reason_for_upstream_errors(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-valuation-agent-secret")

    app_module = importlib.import_module("api.app")
    app = app_module.StockValuationApp()

    def _raise_upstream_error(*args, **kwargs):
        raise ValuationServiceClientError("valuation-service unavailable")

    monkeypatch.setattr(app, "_fetch_baseline_valuation", _raise_upstream_error)

    response = app.app.test_client().post("/api-s/valuate", json={"ticker": "MSFT"})

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["error"] == "valuation-service unavailable"
    assert payload["ticker"] == "MSFT"
    assert payload["reason"] == app_module.COMMON_FAILURE_REASON


def test_valuate_endpoint_includes_common_failure_reason_for_unsupported_segments(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-valuation-agent-secret")

    app_module = importlib.import_module("api.app")
    app = app_module.StockValuationApp()

    monkeypatch.setattr(
        app,
        "_fetch_baseline_valuation",
        lambda *args, **kwargs: {
            "company_name": "Microsoft Corporation",
            "preprocessed_financials": {},
        },
    )
    monkeypatch.setattr(app, "_run_segment_mapping", lambda *args, **kwargs: {"mapped_segments": []})

    response = app.app.test_client().post("/api-s/valuate", json={"ticker": "MSFT"})

    assert response.status_code == 422
    payload = response.get_json()
    assert payload["error"] == "segments_required"
    assert payload["ticker"] == "MSFT"
    assert payload["company_name"] == "Microsoft Corporation"
    assert payload["reason"] == app_module.COMMON_FAILURE_REASON
