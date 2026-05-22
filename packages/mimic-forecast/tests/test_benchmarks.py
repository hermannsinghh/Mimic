"""Tests for the in-process comparison benchmark."""

import numpy as np
import pandas as pd
import pytest

from mimic_forecast.base import ForecastResult, ForecasterAdapter
from mimic_forecast.benchmarks import ComparisonResult, run_comparison


class PersistenceAdapter(ForecasterAdapter):
    """Naive last-value persistence — good baseline for testing."""

    @property
    def name(self) -> str:
        return "persistence"

    def forecast(self, series, horizon, frequency="D", covariates=None) -> ForecastResult:
        future_index = self._build_future_index(series, horizon, frequency)
        last = float(series.iloc[-1])
        point = pd.Series(np.full(horizon, last), index=future_index)
        return ForecastResult(
            point=point,
            quantiles={0.5: point},
            model_name=self.name,
            confidence=0.5,
        )


class ZeroAdapter(ForecasterAdapter):
    """Always predicts zero — intentionally terrible."""

    @property
    def name(self) -> str:
        return "zero"

    def forecast(self, series, horizon, frequency="D", covariates=None) -> ForecastResult:
        future_index = self._build_future_index(series, horizon, frequency)
        point = pd.Series(np.zeros(horizon), index=future_index)
        return ForecastResult(
            point=point,
            quantiles={0.5: point},
            model_name=self.name,
            confidence=0.0,
        )


def test_persistence_beats_zero(daily_series):
    result = run_comparison(daily_series, [PersistenceAdapter(), ZeroAdapter()], horizon=30)
    assert isinstance(result, ComparisonResult)
    assert result.winner == "persistence"
    assert result.scores["persistence"] < result.scores["zero"]


def test_metric_options(daily_series):
    for metric in ("RMSE", "MAE", "MAPE"):
        result = run_comparison(daily_series, [PersistenceAdapter()], horizon=30, metric=metric)
        assert result.metric == metric
        assert result.winner == "persistence"


def test_invalid_metric(daily_series):
    with pytest.raises(ValueError, match="Unknown metric"):
        run_comparison(daily_series, [PersistenceAdapter()], horizon=30, metric="R2")


def test_series_too_short_raises():
    short = pd.Series(
        range(10),
        index=pd.date_range("2024-01-01", periods=10, freq="D"),
        dtype=float,
    )
    with pytest.raises(ValueError, match="too short"):
        run_comparison(short, [PersistenceAdapter()], horizon=30)


def test_forecasts_accessible_in_result(daily_series):
    result = run_comparison(daily_series, [PersistenceAdapter()], horizon=20)
    assert "persistence" in result.forecasts
    assert len(result.forecasts["persistence"].point) == 20
