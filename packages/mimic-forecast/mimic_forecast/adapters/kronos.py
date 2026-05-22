"""Kronos adapter — market microstructure (K-line / candlestick data)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from mimic_forecast.base import ForecastResult, ForecasterAdapter

logger = logging.getLogger(__name__)

_HF_REPO = "AntGroup/Kronos"
_CONTEXT_LEN = 512
_MIN_HISTORY = 30
_DEFAULT_QUANTILES = [0.1, 0.5, 0.9]


@lru_cache(maxsize=1)
def _load_model(device: str) -> Any:
    try:
        from transformers import AutoModel, AutoTokenizer  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "Transformers is not installed. Run: pip install 'mimic-forecast[kronos]'"
        ) from e

    logger.info("Loading Kronos from HuggingFace (%s)…", _HF_REPO)
    tokenizer = AutoTokenizer.from_pretrained(_HF_REPO, trust_remote_code=True)
    model = AutoModel.from_pretrained(_HF_REPO, trust_remote_code=True)
    model = model.to(device)
    model.eval()
    logger.info("Kronos loaded.")
    return model, tokenizer


def _cuda_available() -> bool:
    try:
        import torch  # type: ignore[import]
        return torch.cuda.is_available()
    except ImportError:
        return False


class KronosAdapter(ForecasterAdapter):
    """Adapter for Kronos-499M — market microstructure model.

    Trained on 12 billion K-line records from 45 exchanges.
    Best for: stock price trajectories, order-flow patterns, event-driven shocks.
    """

    def __init__(self) -> None:
        self._device = "cuda" if _cuda_available() else "cpu"

    @property
    def name(self) -> str:
        return "kronos-499m"

    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "D",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        self._validate_series(series, min_length=_MIN_HISTORY)

        import torch  # type: ignore[import]

        input_series = series.iloc[-_CONTEXT_LEN:]
        model, tokenizer = _load_model(self._device)

        values = input_series.values.astype(np.float32)

        # Kronos expects normalized inputs
        mean, std = float(values.mean()), float(values.std()) + 1e-8
        normalized = (values - mean) / std

        input_tensor = torch.tensor(normalized, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)
        input_tensor = input_tensor.to(self._device)

        with torch.no_grad():
            outputs = model(input_tensor, prediction_length=horizon)

        # Output shape varies by Kronos version; handle common cases
        if hasattr(outputs, "sequences"):
            raw = outputs.sequences[0].cpu().numpy()  # (n_samples, horizon)
        elif hasattr(outputs, "last_hidden_state"):
            # Fallback: use hidden state projection
            hidden = outputs.last_hidden_state[0, -horizon:, 0].cpu().numpy()
            raw = hidden[np.newaxis, :]
        else:
            raw = outputs[0].cpu().numpy()

        if raw.ndim == 1:
            raw = raw[np.newaxis, :]

        # Denormalize
        raw = raw * std + mean
        future_index = self._build_future_index(series, horizon, frequency)

        point = pd.Series(raw.mean(axis=0)[:horizon], index=future_index, name="forecast")

        quantiles: dict[float, pd.Series] = {}
        for q in _DEFAULT_QUANTILES:
            q_vals = np.quantile(raw, q, axis=0)[:horizon]
            quantiles[q] = pd.Series(q_vals, index=future_index, name=f"q{int(q*100)}")

        confidence = _estimate_confidence(series, input_series)

        return ForecastResult(
            point=point,
            quantiles=quantiles,
            model_name=self.name,
            confidence=confidence,
            metadata={
                "device": self._device,
                "context_points_used": len(input_series),
                "frequency": frequency,
                "normalized": True,
            },
        )


def _estimate_confidence(full_series: pd.Series, used_series: pd.Series) -> float:
    coverage = len(used_series) / max(len(full_series), 1)
    cv = used_series.std() / (abs(used_series.mean()) + 1e-8)
    stability = max(0.0, 1.0 - float(cv) * 0.5)
    return round(float(coverage * stability), 3)
