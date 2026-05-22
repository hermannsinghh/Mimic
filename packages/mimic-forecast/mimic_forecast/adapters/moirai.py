"""Moirai adapter (Salesforce/moirai-1.0-R-large)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from mimic_forecast.base import ForecastResult, ForecasterAdapter

logger = logging.getLogger(__name__)

_HF_REPO = "Salesforce/moirai-1.0-R-large"
_CONTEXT_LEN = 4096
_MIN_HISTORY = 32
_DEFAULT_QUANTILES = [0.1, 0.2, 0.5, 0.8, 0.9]
_N_SAMPLES = 100


@lru_cache(maxsize=1)
def _load_model(device: str) -> Any:
    try:
        from uni2ts.model.moirai import MoiraiForecast, MoiraiModule  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "uni2ts is not installed. Run: pip install 'mimic-forecast[moirai]'"
        ) from e

    logger.info("Loading Moirai-Large from HuggingFace…")
    model = MoiraiForecast.load_from_checkpoint(
        prediction_length=128,
        context_length=_CONTEXT_LEN,
        patch_size="auto",
        num_samples=_N_SAMPLES,
        target_dim=1,
        feat_dynamic_real_dim=0,
        past_feat_dynamic_real_dim=0,
        module=MoiraiModule.from_pretrained(_HF_REPO),
    )
    logger.info("Moirai loaded.")
    return model


def _cuda_available() -> bool:
    try:
        import torch  # type: ignore[import]
        return torch.cuda.is_available()
    except ImportError:
        return False


class MoiraiAdapter(ForecasterAdapter):
    """Adapter for Salesforce Moirai-1.0-R-Large.

    Strong zero-shot performance, frequently tops public benchmarks.
    Good second-opinion model alongside TimesFM.
    """

    def __init__(self) -> None:
        self._device = "cuda" if _cuda_available() else "cpu"

    @property
    def name(self) -> str:
        return "moirai-1.0-R-large"

    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "D",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        self._validate_series(series, min_length=_MIN_HISTORY)

        import torch  # type: ignore[import]
        from einops import rearrange  # type: ignore[import]
        from gluonts.dataset.pandas import PandasDataset  # type: ignore[import]
        from gluonts.dataset.split import split  # type: ignore[import]

        input_series = series.iloc[-_CONTEXT_LEN:]
        model = _load_model(self._device)

        freq_str = _pandas_to_gluon_freq(frequency)
        ds = PandasDataset({"target": input_series}, freq=freq_str)

        _, test_template = split(ds, offset=-horizon)
        test_data = test_template.generate_instances(horizon)

        predictor = model.create_predictor(batch_size=16, device=self._device)
        forecasts = list(predictor.predict(test_data.input))

        samples = forecasts[0].samples  # (n_samples, horizon)
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
                "n_samples": _N_SAMPLES,
                "context_points_used": len(input_series),
                "frequency": frequency,
            },
        )


def _pandas_to_gluon_freq(freq: str) -> str:
    mapping = {
        "D": "D",
        "W": "W",
        "M": "MS",
        "Q": "QS",
        "H": "H",
    }
    return mapping.get(freq.upper(), "D")


def _estimate_confidence(full_series: pd.Series, used_series: pd.Series) -> float:
    coverage = len(used_series) / max(len(full_series), 1)
    cv = used_series.std() / (abs(used_series.mean()) + 1e-8)
    stability = max(0.0, 1.0 - float(cv) * 0.5)
    return round(float(coverage * stability), 3)
