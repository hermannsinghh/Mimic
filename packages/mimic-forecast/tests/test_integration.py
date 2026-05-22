"""Tests for the mimic plugin integration layer (mocked)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from mimic_forecast.integration.mimic_plugin import AutoForecaster, forecast_for_event


def _fake_series(n=500):
    index = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.Series(100.0 + np.arange(n, dtype=float), index=index)


def _fake_forecast_result(horizon=30):
    from mimic_forecast.base import ForecastResult
    future_index = pd.date_range("2024-01-01", periods=horizon, freq="D")
    point = pd.Series(np.ones(horizon) * 80.0, index=future_index)
    return ForecastResult(
        point=point,
        quantiles={
            0.1: point * 0.9,
            0.9: point * 1.1,
        },
        model_name="dummy",
        confidence=0.8,
    )


def test_forecast_for_event_energy(monkeypatch):
    """forecast_for_event should return dict with relevant series."""
    monkeypatch.setattr(
        "mimic_forecast.integration.mimic_plugin.pull_series",
        lambda **kwargs: _fake_series(),
    )

    from mimic_forecast.base import ForecasterAdapter

    fake_adapter = MagicMock(spec=ForecasterAdapter)
    fake_adapter.name = "dummy"
    fake_adapter.forecast.return_value = _fake_forecast_result()

    monkeypatch.setattr(
        "mimic_forecast.integration.mimic_plugin.registry.best_model_for",
        lambda series_name: fake_adapter,
    )

    result = forecast_for_event(
        context={"ticker": "XOM"},
        event="oil spikes to $150",
        horizon=30,
    )

    assert isinstance(result, dict)
    assert len(result) > 0
    for key, val in result.items():
        assert "point_end" in val
        assert "model" in val


def test_auto_forecaster_delegates(monkeypatch):
    """AutoForecaster.forecast_for_event calls forecast_for_event."""
    called = {}

    def fake_ffe(context, event, horizon, frequency, fred_api_key):
        called["event"] = event
        return {"oil_price": {"point_end": 90.0, "model": "dummy"}}

    monkeypatch.setattr(
        "mimic_forecast.integration.mimic_plugin.forecast_for_event",
        fake_ffe,
    )

    af = AutoForecaster()
    result = af.forecast_for_event({"ticker": "WMT"}, "oil spikes to $150")
    assert called["event"] == "oil spikes to $150"
    assert "oil_price" in result


def test_get_forecaster_returns_auto_forecaster():
    from mimic_forecast.integration.mimic_plugin import get_forecaster
    f = get_forecaster(auto=True)
    assert isinstance(f, AutoForecaster)
