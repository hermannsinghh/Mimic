"""BISTRO adapter — BIS macroeconomic time series model."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from mimic_forecast.base import ForecastResult, ForecasterAdapter

logger = logging.getLogger(__name__)

# BIS BISTRO model — placeholder repo until official HF release
_HF_REPO = "bis-models/bistro"
_CONTEXT_LEN = 120  # ~10 years of monthly data
_MIN_HISTORY = 24
_DEFAULT_QUANTILES = [0.1, 0.5, 0.9]


@lru_cache(maxsize=1)
def _load_model(device: str) -> Any:
    try:
        from transformers import AutoModel, AutoConfig  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "Transformers is not installed. Run: pip install 'mimic-forecast[bistro]'"
        ) from e

    logger.info("Loading BISTRO macro model from HuggingFace…")
    config = AutoConfig.from_pretrained(_HF_REPO, trust_remote_code=True)
    model = AutoModel.from_pretrained(_HF_REPO, config=config, trust_remote_code=True)
    model = model.to(device)
    model.eval()
    logger.info("BISTRO loaded.")
    return model


def _cuda_available() -> bool:
    try:
        import torch  # type: ignore[import]
        return torch.cuda.is_available()
    except ImportError:
        return False


class BISTROAdapter(ForecasterAdapter):
    """Adapter for the BIS BISTRO macroeconomic model.

    Best for: GDP, inflation, unemployment, interest rate trajectories.
    Supports conditional 'what-if' forecasting via covariates.
    Designed for low-frequency data (monthly, quarterly).
    """

    def __init__(self) -> None:
        self._device = "cuda" if _cuda_available() else "cpu"

    @property
    def name(self) -> str:
        return "bistro-macro"

    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "M",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        self._validate_series(series, min_length=_MIN_HISTORY)

        if frequency not in ("M", "Q", "Y"):
            logger.warning(
                "BISTRO is designed for macro frequencies (M/Q/Y), got '%s'. "
                "Results may be suboptimal.",
                frequency,
            )

        import torch  # type: ignore[import]

        input_series = series.iloc[-_CONTEXT_LEN:]
        values = input_series.values.astype(np.float32)

        mean, std = float(values.mean()), float(values.std()) + 1e-8
        normalized = (values - mean) / std

        model = _load_model(self._device)

        cov_tensor = None
        if covariates:
            cov_arrays = []
            for cov_series in covariates.values():
                aligned = cov_series.reindex(input_series.index, method="nearest")
                cov_arrays.append(aligned.values.astype(np.float32))
            cov_matrix = np.stack(cov_arrays, axis=-1)
            cov_tensor = torch.tensor(cov_matrix).unsqueeze(0).to(self._device)

        input_tensor = torch.tensor(normalized).unsqueeze(0).unsqueeze(-1).to(self._device)

        with torch.no_grad():
            if cov_tensor is not None and hasattr(model, "forward_with_covariates"):
                outputs = model.forward_with_covariates(input_tensor, cov_tensor, prediction_length=horizon)
            else:
                outputs = model(input_tensor, prediction_length=horizon)

        if hasattr(outputs, "sequences"):
            raw = outputs.sequences[0].cpu().numpy()
        elif hasattr(outputs, "last_hidden_state"):
            hidden = outputs.last_hidden_state[0, -horizon:, 0].cpu().numpy()
            raw = hidden[np.newaxis, :]
        else:
            raw = outputs[0].cpu().numpy()

        if raw.ndim == 1:
            raw = raw[np.newaxis, :]

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
                "covariates_used": list(covariates.keys()) if covariates else [],
                "what_if_mode": covariates is not None,
            },
        )


def _estimate_confidence(full_series: pd.Series, used_series: pd.Series) -> float:
    coverage = len(used_series) / max(len(full_series), 1)
    cv = used_series.std() / (abs(used_series.mean()) + 1e-8)
    stability = max(0.0, 1.0 - float(cv) * 0.5)
    return round(float(coverage * stability), 3)
