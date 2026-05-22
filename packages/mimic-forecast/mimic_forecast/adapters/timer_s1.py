"""Timer-S1 adapter — Plan §3.2 FC-02.

Headline-accuracy time-series foundation model. Loads lazily; clear
ImportError if the timer dep isn't installed.

Install:
    pip install 'mimic-forecast[timer]'
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from mimic_forecast.base import ForecasterAdapter, ForecastResult

_HF_REPO = "thuml/timer-base-84m"  # placeholder identifier
_MIN_HISTORY = 32
_DEFAULT_QUANTILES = [0.1, 0.5, 0.9]


@lru_cache(maxsize=1)
def _load_model(device: str) -> Any:
    try:
        import timer  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "Timer-S1 is not installed. Run: pip install 'mimic-forecast[timer]' "
            f"(model: {_HF_REPO})"
        ) from e
    raise NotImplementedError("FC-02 model loading lands when timer is in the env")


class TimerS1Adapter(ForecasterAdapter):
    """Timer-S1 — headline-accuracy time-series foundation model."""

    def __init__(self, device: str = "cpu") -> None:
        self.device = device

    @property
    def name(self) -> str:
        return "timer-s1"

    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "D",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        self._validate_series(series, min_length=_MIN_HISTORY)
        model = _load_model(self.device)
        raise NotImplementedError("Timer-S1 inference wiring lands with FC-02")
