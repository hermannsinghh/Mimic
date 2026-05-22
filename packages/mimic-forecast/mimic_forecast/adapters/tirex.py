"""TiRex adapter — Plan §3.2 FC-03.

Cheap fallback for the 2026-frontier tier. Loads lazily.

Install:
    pip install 'mimic-forecast[tirex]'
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from mimic_forecast.base import ForecasterAdapter, ForecastResult

_HF_REPO = "NX-AI/TiRex"  # placeholder identifier
_MIN_HISTORY = 32
_DEFAULT_QUANTILES = [0.1, 0.5, 0.9]


@lru_cache(maxsize=1)
def _load_model(device: str) -> Any:
    try:
        import tirex  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "TiRex is not installed. Run: pip install 'mimic-forecast[tirex]' "
            f"(model: {_HF_REPO})"
        ) from e
    raise NotImplementedError("FC-03 model loading lands when tirex is in the env")


class TiRexAdapter(ForecasterAdapter):
    """TiRex — cheap fallback forecaster."""

    def __init__(self, device: str = "cpu") -> None:
        self.device = device

    @property
    def name(self) -> str:
        return "tirex"

    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "D",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        self._validate_series(series, min_length=_MIN_HISTORY)
        model = _load_model(self.device)
        raise NotImplementedError("TiRex inference wiring lands with FC-03")
