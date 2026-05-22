"""Core abstractions: ForecasterAdapter and ForecastResult."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ForecastResult:
    """Output of any ForecasterAdapter.forecast() call."""

    point: pd.Series
    """Point forecast indexed by future timestamps."""

    quantiles: dict[float, pd.Series]
    """Probabilistic bands, e.g. {0.1: ..., 0.5: ..., 0.9: ...}."""

    model_name: str
    """Human-readable model identifier, e.g. 'timesfm-2.0-500m'."""

    confidence: float
    """Aggregate confidence in [0, 1]. 1.0 = model is certain."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Preprocessing choices, context length used, device, etc."""

    def summary(self) -> dict[str, Any]:
        """Return a compact dict suitable for feeding into an LLM prompt."""
        last = self.point.iloc[-1]
        result: dict[str, Any] = {
            "model": self.model_name,
            "horizon_steps": len(self.point),
            "point_end": float(last),
            "confidence": self.confidence,
        }
        for q, series in self.quantiles.items():
            result[f"q{int(q * 100)}_end"] = float(series.iloc[-1])
        return result


class ForecasterAdapter(ABC):
    """Base class every model adapter must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable model identifier, lowercase with hyphens."""

    @abstractmethod
    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "D",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        """Produce a forecast from a historical time series.

        Args:
            series: Historical values with a DatetimeIndex.
            horizon: Number of steps ahead to forecast.
            frequency: Pandas offset alias ('D', 'W', 'M', 'Q').
            covariates: Optional external regressors keyed by name.

        Returns:
            ForecastResult with point forecast and quantile bands.
        """

    def _validate_series(self, series: pd.Series, min_length: int = 16) -> None:
        if not isinstance(series.index, pd.DatetimeIndex):
            raise ValueError("series.index must be a DatetimeIndex")
        if len(series) < min_length:
            raise ValueError(
                f"{self.name} requires at least {min_length} data points, "
                f"got {len(series)}"
            )

    def _build_future_index(self, series: pd.Series, horizon: int, frequency: str) -> pd.DatetimeIndex:
        last = series.index[-1]
        return pd.date_range(start=last, periods=horizon + 1, freq=frequency)[1:]
