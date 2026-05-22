"""Tests for EnsembleAdapter."""

import numpy as np
import pandas as pd
import pytest

from mimic_forecast.base import ForecastResult, ForecasterAdapter
from mimic_forecast.ensemble import EnsembleAdapter


class ConstantAdapter(ForecasterAdapter):
    """Returns a constant value — easy to reason about in ensemble tests."""

    def __init__(self, value: float, name_suffix: str = "") -> None:
        self._value = value
        self._name = f"constant_{value}{name_suffix}"

    @property
    def name(self) -> str:
        return self._name

    def forecast(self, series, horizon, frequency="D", covariates=None) -> ForecastResult:
        future_index = self._build_future_index(series, horizon, frequency)
        point = pd.Series(np.full(horizon, self._value), index=future_index)
        quantiles = {
            0.1: point * 0.9,
            0.5: point,
            0.9: point * 1.1,
        }
        return ForecastResult(
            point=point,
            quantiles=quantiles,
            model_name=self.name,
            confidence=0.8,
        )


def test_equal_weight_average(daily_series):
    a = ConstantAdapter(100.0, "a")
    b = ConstantAdapter(200.0, "b")
    ensemble = EnsembleAdapter([a, b])
    result = ensemble.forecast(daily_series, horizon=10)

    expected = 150.0
    np.testing.assert_allclose(result.point.values, expected, rtol=1e-5)


def test_custom_weights(daily_series):
    a = ConstantAdapter(100.0, "a")
    b = ConstantAdapter(200.0, "b")
    # Weight a=3, b=1 → normalized 0.75, 0.25 → expected = 125
    ensemble = EnsembleAdapter([a, b], weights=[3.0, 1.0])
    result = ensemble.forecast(daily_series, horizon=10)

    expected = 0.75 * 100.0 + 0.25 * 200.0
    np.testing.assert_allclose(result.point.values, expected, rtol=1e-5)


def test_ensemble_name_contains_members(daily_series):
    a = ConstantAdapter(1.0, "x")
    b = ConstantAdapter(2.0, "y")
    ensemble = EnsembleAdapter([a, b])
    assert "constant_1.0x" in ensemble.name
    assert "constant_2.0y" in ensemble.name


def test_empty_models_raises():
    with pytest.raises(ValueError, match="at least one model"):
        EnsembleAdapter([])


def test_weight_mismatch_raises():
    a = ConstantAdapter(1.0, "a")
    b = ConstantAdapter(2.0, "b")
    with pytest.raises(ValueError, match="weights must match"):
        EnsembleAdapter([a, b], weights=[0.5, 0.3, 0.2])


def test_single_model_ensemble(daily_series):
    a = ConstantAdapter(42.0, "only")
    ensemble = EnsembleAdapter([a])
    result = ensemble.forecast(daily_series, horizon=5)
    np.testing.assert_allclose(result.point.values, 42.0, rtol=1e-5)


def test_ensemble_quantiles_present(daily_series):
    a = ConstantAdapter(100.0, "a")
    b = ConstantAdapter(200.0, "b")
    ensemble = EnsembleAdapter([a, b])
    result = ensemble.forecast(daily_series, horizon=5)
    assert 0.1 in result.quantiles
    assert 0.9 in result.quantiles


def test_failing_member_is_skipped(daily_series):
    """Ensemble should succeed even if one member throws."""

    class BrokenAdapter(ForecasterAdapter):
        @property
        def name(self) -> str:
            return "broken"

        def forecast(self, *args, **kwargs):
            raise RuntimeError("intentional failure")

    good = ConstantAdapter(50.0, "g")
    broken = BrokenAdapter()
    ensemble = EnsembleAdapter([good, broken])
    result = ensemble.forecast(daily_series, horizon=5)
    np.testing.assert_allclose(result.point.values, 50.0, rtol=1e-5)
    assert result.metadata["members_succeeded"] == 1
