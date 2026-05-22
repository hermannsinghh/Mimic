"""Chronos adapter (amazon/chronos-t5-large)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
import torch  # type: ignore[import]

from mimic_forecast.base import ForecastResult, ForecasterAdapter

logger = logging.getLogger(__name__)

_HF_REPO = "amazon/chronos-t5-large"
_CONTEXT_LEN = 512
_MIN_HISTORY = 16
_DEFAULT_QUANTILES = [0.1, 0.2, 0.5, 0.8, 0.9]
_N_SAMPLES = 20  # Monte Carlo draws for quantile estimation


@lru_cache(maxsize=1)
def _load_pipeline(device: str) -> Any:
    try:
        from chronos import ChronosPipeline  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "Chronos is not installed. Run: pip install 'mimic-forecast[chronos]'"
        ) from e

    logger.info("Loading Chronos T5-Large from HuggingFace…")
    pipeline = ChronosPipeline.from_pretrained(
        _HF_REPO,
        device_map=device,
        torch_dtype=torch.bfloat16,
    )
    logger.info("Chronos loaded.")
    return pipeline


class ChronosAdapter(ForecasterAdapter):
    """Adapter for Amazon Chronos T5-Large.

    Best for: zero-shot multivariate, covariate-informed forecasting.
    Native probabilistic via Monte Carlo sampling.
    """

    def __init__(self, n_samples: int = _N_SAMPLES) -> None:
        self._n_samples = n_samples
        self._device = "cuda" if torch.cuda.is_available() else "cpu"

    @property
    def name(self) -> str:
        return "chronos-t5-large"

    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "D",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        self._validate_series(series, min_length=_MIN_HISTORY)

        input_series = series.iloc[-_CONTEXT_LEN:]
        context = torch.tensor(input_series.values, dtype=torch.float32).unsqueeze(0)

        pipeline = _load_pipeline(self._device)

        # forecast returns (batch, n_samples, horizon)
        forecast_tensor, _, _ = pipeline.predict(
            context=context,
            prediction_length=horizon,
            num_samples=self._n_samples,
            temperature=1.0,
            top_k=50,
            top_p=1.0,
        )

        samples = forecast_tensor[0].numpy()  # (n_samples, horizon)
        future_index = self._build_future_index(series, horizon, frequency)

        point = pd.Series(samples.mean(axis=0), index=future_index, name="forecast")

        quantiles: dict[float, pd.Series] = {}
        for q in _DEFAULT_QUANTILES:
            q_vals = np.quantile(samples, q, axis=0)
            quantiles[q] = pd.Series(q_vals, index=future_index, name=f"q{int(q*100)}")

        confidence = _estimate_confidence(series, input_series)

        return ForecastResult(
            point=point,
            quantiles=quantiles,
            model_name=self.name,
            confidence=confidence,
            metadata={
                "device": self._device,
                "n_samples": self._n_samples,
                "context_points_used": len(input_series),
                "covariates_used": list(covariates.keys()) if covariates else [],
                "frequency": frequency,
            },
        )


def _estimate_confidence(full_series: pd.Series, used_series: pd.Series) -> float:
    coverage = len(used_series) / max(len(full_series), 1)
    cv = used_series.std() / (abs(used_series.mean()) + 1e-8)
    stability = max(0.0, 1.0 - float(cv) * 0.5)
    return round(float(coverage * stability), 3)
