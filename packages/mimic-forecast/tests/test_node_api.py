"""Tests for the per-node forecast API — Plan §3.2 FC-06."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mimic_forecast import NodeForecast, forecast_node
from mimic_forecast.base import ForecastResult, ForecasterAdapter


class _StubAdapter(ForecasterAdapter):
    @property
    def name(self) -> str:
        return "stub-v1"

    def forecast(self, series, horizon, frequency="D", covariates=None):
        future = pd.date_range(series.index[-1], periods=horizon + 1, freq=frequency)[1:]
        point = pd.Series(np.linspace(100.0, 110.0, horizon), index=future)
        q_low = point - 5.0
        q_high = point + 5.0
        return ForecastResult(
            point=point,
            quantiles={0.1: q_low, 0.5: point, 0.9: q_high},
            model_name=self.name,
            confidence=0.8,
        )


def _historical():
    idx = pd.date_range("2026-01-01", periods=30, freq="D")
    return pd.Series(np.linspace(90.0, 100.0, 30), index=idx)


def test_forecast_node_happy_path():
    adapter = _StubAdapter()
    resolver = lambda node: _historical()
    nf = forecast_node(
        adapter, "https://mimic.ai/instruments/svb-equity",
        horizon=5, series_resolver=resolver,
    )
    assert isinstance(nf, NodeForecast)
    assert nf.node == "https://mimic.ai/instruments/svb-equity"
    assert nf.horizon == 5
    assert len(nf.point) == 5
    assert set(nf.distribution.keys()) == {0.1, 0.5, 0.9}
    assert nf.metadata["requested_quantiles"] == [0.1, 0.5, 0.9]


def test_forecast_node_rejects_bad_horizon():
    adapter = _StubAdapter()
    with pytest.raises(ValueError, match="horizon"):
        forecast_node(adapter, "n", horizon=0, series_resolver=lambda _: _historical())


def test_forecast_node_rejects_bad_quantiles():
    adapter = _StubAdapter()
    with pytest.raises(ValueError, match="quantiles"):
        forecast_node(adapter, "n", horizon=3, quantiles=(0.0, 1.0),
                      series_resolver=lambda _: _historical())


def test_forecast_node_interpolates_missing_quantile():
    adapter = _StubAdapter()  # only provides 0.1, 0.5, 0.9
    nf = forecast_node(
        adapter, "n", horizon=4, quantiles=(0.25,),
        series_resolver=lambda _: _historical(),
    )
    q25 = nf.distribution[0.25]
    # 0.25 sits 3/8 of the way from 0.1 to 0.5 → t = (0.25-0.1)/(0.5-0.1) = 0.375
    # value = q10 * (1-0.375) + q50 * 0.375
    expected_first = (-5.0 + 100.0) * 0.625 + 100.0 * 0.375
    np.testing.assert_allclose(q25.iloc[0], expected_first, rtol=1e-9)


def test_forecast_node_rejects_non_series_resolver():
    adapter = _StubAdapter()
    with pytest.raises(TypeError):
        forecast_node(adapter, "n", horizon=3, series_resolver=lambda _: [1, 2, 3])
