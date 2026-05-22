"""EnsembleAdapter — weighted combination of multiple adapters."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from mimic_forecast.base import ForecastResult, ForecasterAdapter

logger = logging.getLogger(__name__)


class EnsembleAdapter(ForecasterAdapter):
    """Weighted ensemble over multiple ForecasterAdapters.

    Weights default to equal; set weights='auto' to use benchmark-tuned
    weights from the SERIES_REGISTRY once mimic-bench scores are available.
    """

    def __init__(
        self,
        models: list[ForecasterAdapter],
        weights: list[float] | str = "equal",
    ) -> None:
        if not models:
            raise ValueError("EnsembleAdapter requires at least one model.")
        self._models = models

        if weights == "equal" or weights == "auto":
            self._weights = [1.0 / len(models)] * len(models)
            if weights == "auto":
                logger.info(
                    "Ensemble weights='auto' not yet calibrated; using equal weights. "
                    "Run mimic-bench to generate calibrated weights."
                )
        else:
            if len(weights) != len(models):  # type: ignore[arg-type]
                raise ValueError("weights must match length of models.")
            total = sum(weights)  # type: ignore[arg-type]
            self._weights = [w / total for w in weights]  # type: ignore[arg-type]

    @property
    def name(self) -> str:
        names = "+".join(m.name for m in self._models)
        return f"ensemble({names})"

    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "D",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        results: list[ForecastResult] = []
        for model in self._models:
            try:
                r = model.forecast(series, horizon, frequency, covariates)
                results.append(r)
            except Exception as exc:
                logger.warning("Model %s failed in ensemble: %s", model.name, exc)

        if not results:
            raise RuntimeError("All ensemble members failed — cannot produce forecast.")

        active_weights = self._weights[: len(results)]
        total = sum(active_weights)
        normed = [w / total for w in active_weights]

        future_index = results[0].point.index

        # Weighted average of point forecasts
        point_matrix = np.stack([r.point.values for r in results], axis=0)
        point_vals = np.average(point_matrix, axis=0, weights=normed)
        point = pd.Series(point_vals, index=future_index, name="forecast")

        # Quantiles: union of quantile levels across all models
        all_quantile_levels: set[float] = set()
        for r in results:
            all_quantile_levels.update(r.quantiles.keys())

        quantiles: dict[float, pd.Series] = {}
        for q in sorted(all_quantile_levels):
            q_parts = []
            q_weights = []
            for r, w in zip(results, normed):
                if q in r.quantiles:
                    q_parts.append(r.quantiles[q].values)
                    q_weights.append(w)
            if q_parts:
                q_matrix = np.stack(q_parts, axis=0)
                q_total = sum(q_weights)
                q_normed = [w / q_total for w in q_weights]
                q_vals = np.average(q_matrix, axis=0, weights=q_normed)
                quantiles[q] = pd.Series(q_vals, index=future_index, name=f"q{int(q*100)}")

        confidence = float(np.average([r.confidence for r in results], weights=normed))

        return ForecastResult(
            point=point,
            quantiles=quantiles,
            model_name=self.name,
            confidence=round(confidence, 3),
            metadata={
                "members": [r.model_name for r in results],
                "weights": normed,
                "members_succeeded": len(results),
                "members_total": len(self._models),
            },
        )
