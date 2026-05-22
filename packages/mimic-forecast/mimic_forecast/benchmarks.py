"""In-process model comparison benchmark."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from mimic_forecast.base import ForecastResult, ForecasterAdapter

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Output of compare_models()."""

    winner: str
    """Name of the model that scored best on the given metric."""

    scores: dict[str, float]
    """Model name → metric score (lower is better for RMSE/MAE/MAPE)."""

    forecasts: dict[str, ForecastResult]
    """Raw forecast results for each model."""

    metric: str
    """Metric used for ranking."""

    series_length: int
    """Number of historical points used."""


def run_comparison(
    series: pd.Series,
    models: list[ForecasterAdapter],
    horizon: int = 30,
    frequency: str = "D",
    metric: str = "RMSE",
) -> ComparisonResult:
    """Backtest all models on the last `horizon` steps and score them.

    Uses walk-forward: trains on series[:-horizon], evaluates on series[-horizon:].
    """
    if len(series) < horizon * 2:
        raise ValueError(
            f"Series too short for backtesting with horizon={horizon}. "
            f"Need at least {horizon * 2} points, got {len(series)}."
        )

    train = series.iloc[:-horizon]
    actual = series.iloc[-horizon:]

    # Validate metric before running any models
    _compute_metric(np.array([1.0]), np.array([1.0]), metric)

    scores: dict[str, float] = {}
    forecasts: dict[str, ForecastResult] = {}

    for model in models:
        try:
            result = model.forecast(train, horizon=horizon, frequency=frequency)
            predicted = result.point.values[: len(actual)]
            score = _compute_metric(actual.values, predicted, metric)
            scores[model.name] = round(float(score), 6)
            forecasts[model.name] = result
            logger.info("  %s %s = %.4f", model.name, metric, score)
        except Exception as exc:
            logger.warning("Model %s failed during comparison: %s", model.name, exc)
            scores[model.name] = float("inf")

    winner = min(scores, key=lambda k: scores[k])

    return ComparisonResult(
        winner=winner,
        scores=scores,
        forecasts=forecasts,
        metric=metric,
        series_length=len(train),
    )


def _compute_metric(actual: np.ndarray, predicted: np.ndarray, metric: str) -> float:
    residuals = actual - predicted
    metric = metric.upper()

    if metric == "RMSE":
        return float(np.sqrt(np.mean(residuals**2)))
    if metric == "MAE":
        return float(np.mean(np.abs(residuals)))
    if metric == "MAPE":
        nonzero = actual != 0
        if not nonzero.any():
            return float("inf")
        return float(np.mean(np.abs(residuals[nonzero] / actual[nonzero])) * 100)

    raise ValueError(f"Unknown metric '{metric}'. Use RMSE, MAE, or MAPE.")
