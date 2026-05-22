"""TimesFM 2.0 adapter (google/timesfm-2.0-500m-pytorch)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from mimic_forecast.base import ForecastResult, ForecasterAdapter

logger = logging.getLogger(__name__)

_HF_REPO = "google/timesfm-2.0-500m-pytorch"
_CONTEXT_LEN = 2048
_MIN_HISTORY = 64
_DEFAULT_QUANTILES = [0.1, 0.2, 0.5, 0.8, 0.9]


@lru_cache(maxsize=1)
def _load_model(backend: str, device: str) -> Any:
    """Load and cache TimesFM model — expensive (~30-60s, ~2 GB)."""
    try:
        import timesfm  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "TimesFM is not installed. Run: pip install 'mimic-forecast[timesfm]'"
        ) from e

    logger.info("Loading TimesFM 2.0 from HuggingFace (first load may take 30-60s)…")

    tfm = timesfm.TimesFm(
        hparams=timesfm.TimesFmHparams(
            backend=backend,
            per_core_batch_size=32,
            horizon_len=128,
            num_layers=20,
            model_dims=1280,
            context_len=_CONTEXT_LEN,
        ),
        checkpoint=timesfm.TimesFmCheckpoint(
            huggingface_repo_id=_HF_REPO,
        ),
    )
    logger.info("TimesFM loaded successfully.")
    return tfm


def _detect_backend() -> tuple[str, str]:
    try:
        import torch  # type: ignore[import]

        if torch.cuda.is_available():
            return "gpu", "cuda"
    except ImportError:
        pass
    return "cpu", "cpu"


class TimesFMAdapter(ForecasterAdapter):
    """Adapter for Google TimesFM 2.0 (500M parameter version).

    Best for: general demand, retail, logistics, energy.
    Supports probabilistic output (P10 / P50 / P90).
    """

    def __init__(self, quantile_levels: list[float] | None = None) -> None:
        self._quantile_levels = quantile_levels or _DEFAULT_QUANTILES
        self._backend, self._device = _detect_backend()

    @property
    def name(self) -> str:
        return "timesfm-2.0-500m"

    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "D",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        self._validate_series(series, min_length=_MIN_HISTORY)

        if covariates:
            logger.warning("TimesFM 2.0 does not use covariates; they will be ignored.")

        # Clip to context window
        input_series = series.iloc[-_CONTEXT_LEN:]
        values = input_series.values.astype(np.float32)

        # Frequency token expected by TimesFM
        freq_token = _pandas_freq_to_timesfm(frequency)

        model = _load_model(self._backend, self._device)

        point_raw, quantile_raw = model.forecast(
            inputs=[values],
            freq=[freq_token],
            quantile_levels=self._quantile_levels,
        )

        # point_raw shape: (1, horizon_len) — trim to requested horizon
        point_vals = point_raw[0][:horizon]
        future_index = self._build_future_index(series, horizon, frequency)

        point = pd.Series(point_vals, index=future_index, name="forecast")

        quantiles: dict[float, pd.Series] = {}
        for i, q in enumerate(self._quantile_levels):
            q_vals = quantile_raw[0, :horizon, i]
            quantiles[q] = pd.Series(q_vals, index=future_index, name=f"q{int(q*100)}")

        # Confidence heuristic: based on series CV and context coverage
        confidence = _estimate_confidence(series, input_series)

        return ForecastResult(
            point=point,
            quantiles=quantiles,
            model_name=self.name,
            confidence=confidence,
            metadata={
                "backend": self._backend,
                "context_points_used": len(input_series),
                "frequency": frequency,
                "preprocessing": "raw",
            },
        )


def _pandas_freq_to_timesfm(freq: str) -> int:
    """Map pandas offset alias to TimesFM frequency token."""
    mapping = {
        "D": 0,   # daily
        "W": 1,   # weekly
        "M": 2,   # monthly
        "Q": 3,   # quarterly
        "Y": 4,   # yearly
        "H": 5,   # hourly
    }
    token = mapping.get(freq.upper().rstrip("-"))
    if token is None:
        logger.warning("Unknown frequency '%s', defaulting to daily (0).", freq)
        token = 0
    return token


def _estimate_confidence(full_series: pd.Series, used_series: pd.Series) -> float:
    """Heuristic confidence based on data quality."""
    coverage = len(used_series) / max(len(full_series), 1)
    cv = used_series.std() / (abs(used_series.mean()) + 1e-8)
    stability = max(0.0, 1.0 - float(cv) * 0.5)
    return round(float(coverage * stability), 3)
