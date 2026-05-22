"""Toto 2.0 adapter (Datadog/Toto-Open-Base-1.0) — Plan §3.2 FC-01.

Multivariate probabilistic forecaster. Loads the model lazily; raises a
clear ImportError if `toto` isn't installed.

Install:
    pip install 'mimic-forecast[toto]'
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from mimic_forecast.base import ForecasterAdapter, ForecastResult

_HF_REPO = "Datadog/Toto-Open-Base-1.0"
_MIN_HISTORY = 16
_DEFAULT_QUANTILES = [0.1, 0.2, 0.5, 0.8, 0.9]


@lru_cache(maxsize=1)
def _load_model(device: str) -> Any:
    try:
        import toto  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "Toto 2.0 is not installed. Run: pip install 'mimic-forecast[toto]' "
            f"(model: {_HF_REPO})"
        ) from e
    raise NotImplementedError(
        "FC-01 model loading lands when the toto package is added to the env. "
        "Wire torch checkpoint load + push to `device`."
    )


class Toto2Adapter(ForecasterAdapter):
    """Toto 2.0 — multivariate probabilistic forecasting."""

    def __init__(self, device: str = "cpu") -> None:
        self.device = device

    @property
    def name(self) -> str:
        return "toto-open-base-1.0"

    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "D",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        self._validate_series(series, min_length=_MIN_HISTORY)
        model = _load_model(self.device)
        raise NotImplementedError(
            "Toto 2.0 inference wiring lands with FC-01. Use the model to produce "
            "a probabilistic forecast over `horizon` steps, then return a "
            "ForecastResult with quantile bands."
        )
