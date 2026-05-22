"""Tests for ForecasterAdapter base and ForecastResult."""

import numpy as np
import pandas as pd
import pytest

from mimic_forecast.base import ForecastResult, ForecasterAdapter


class DummyAdapter(ForecasterAdapter):
    """Minimal adapter for unit testing the base interface."""

    @property
    def name(self) -> str:
        return "dummy"

    def forecast(self, series, horizon, frequency="D", covariates=None) -> ForecastResult:
        self._validate_series(series, min_length=10)
        future_index = self._build_future_index(series, horizon, frequency)
        point = pd.Series(np.ones(horizon) * float(series.iloc[-1]), index=future_index)
        quantiles = {
            0.1: point * 0.9,
            0.5: point,
            0.9: point * 1.1,
        }
        return ForecastResult(
            point=point,
            quantiles=quantiles,
            model_name=self.name,
            confidence=0.75,
            metadata={"test": True},
        )


def test_dummy_forecast_shape(daily_series):
    adapter = DummyAdapter()
    result = adapter.forecast(daily_series, horizon=30)

    assert len(result.point) == 30
    assert result.point.index.freq is not None or len(result.point.index) == 30
    assert set(result.quantiles.keys()) == {0.1, 0.5, 0.9}
    assert result.model_name == "dummy"
    assert 0.0 <= result.confidence <= 1.0


def test_future_index_starts_after_series(daily_series):
    adapter = DummyAdapter()
    result = adapter.forecast(daily_series, horizon=10)
    assert result.point.index[0] > daily_series.index[-1]


def test_summary_keys(daily_series):
    adapter = DummyAdapter()
    result = adapter.forecast(daily_series, horizon=5)
    summary = result.summary()
    assert "model" in summary
    assert "point_end" in summary
    assert "q10_end" in summary
    assert "q90_end" in summary


def test_validate_series_rejects_short(short_series):
    adapter = DummyAdapter()
    with pytest.raises(ValueError, match="at least"):
        # short_series has 10 points, DummyAdapter.forecast requires min 10 — pass with 11
        tiny = short_series.iloc[:5]
        adapter.forecast(tiny, horizon=3)


def test_validate_series_rejects_non_datetime():
    adapter = DummyAdapter()
    bad = pd.Series(range(50), index=range(50), dtype=float)
    with pytest.raises(ValueError, match="DatetimeIndex"):
        adapter.forecast(bad, horizon=5)


def test_forecast_result_quantile_ordering(daily_series):
    adapter = DummyAdapter()
    result = adapter.forecast(daily_series, horizon=20)
    q10 = result.quantiles[0.1].values
    q50 = result.quantiles[0.5].values
    q90 = result.quantiles[0.9].values
    assert np.all(q10 <= q50), "Q10 should be <= Q50"
    assert np.all(q50 <= q90), "Q50 should be <= Q90"
