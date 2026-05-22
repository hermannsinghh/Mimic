"""mimic-forecast — foundation model adapter layer for quantitative forecasting."""

from __future__ import annotations

from mimic_forecast.base import ForecasterAdapter, ForecastResult
from mimic_forecast.ensemble import EnsembleAdapter
from mimic_forecast.integration.mimic_plugin import AutoForecaster, get_forecaster
from mimic_forecast.node_api import NodeForecast, forecast_node

__version__ = "0.1.0"
__all__ = [
    "ForecasterAdapter",
    "ForecastResult",
    "EnsembleAdapter",
    "AutoForecaster",
    "get_forecaster",
    "NodeForecast",
    "forecast_node",
    # Adapters — imported lazily to avoid requiring all optional deps
    "TimesFMAdapter",
    "ChronosAdapter",
    "FinBERT2Adapter",
    "KronosAdapter",
    "MoiraiAdapter",
    "BISTROAdapter",
    "Toto2Adapter",
    "TimerS1Adapter",
    "TiRexAdapter",
]


def __getattr__(name: str):
    if name == "TimesFMAdapter":
        from mimic_forecast.adapters.timesfm import TimesFMAdapter
        return TimesFMAdapter
    if name == "ChronosAdapter":
        from mimic_forecast.adapters.chronos import ChronosAdapter
        return ChronosAdapter
    if name == "FinBERT2Adapter":
        from mimic_forecast.adapters.finbert import FinBERT2Adapter
        return FinBERT2Adapter
    if name == "KronosAdapter":
        from mimic_forecast.adapters.kronos import KronosAdapter
        return KronosAdapter
    if name == "MoiraiAdapter":
        from mimic_forecast.adapters.moirai import MoiraiAdapter
        return MoiraiAdapter
    if name == "BISTROAdapter":
        from mimic_forecast.adapters.bistro import BISTROAdapter
        return BISTROAdapter
    if name == "Toto2Adapter":
        from mimic_forecast.adapters.toto import Toto2Adapter
        return Toto2Adapter
    if name == "TimerS1Adapter":
        from mimic_forecast.adapters.timer_s1 import TimerS1Adapter
        return TimerS1Adapter
    if name == "TiRexAdapter":
        from mimic_forecast.adapters.tirex import TiRexAdapter
        return TiRexAdapter
    raise AttributeError(f"module 'mimic_forecast' has no attribute {name!r}")


def compare_models(
    series,
    models: list[ForecasterAdapter],
    horizon: int = 30,
    frequency: str = "D",
    metric: str = "RMSE",
) -> "ComparisonResult":
    """Run all models on the same series and return ranked results."""
    from mimic_forecast.benchmarks import run_comparison
    return run_comparison(series, models, horizon, frequency, metric)
