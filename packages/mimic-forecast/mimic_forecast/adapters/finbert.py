"""FinBERT-2 adapter — sentiment → directional signal."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from mimic_forecast.base import ForecastResult, ForecasterAdapter

logger = logging.getLogger(__name__)

_HF_REPO = "ProsusAI/finbert"
_FALLBACK_REPO = "yiyanghkust/finbert-tone"


@dataclass
class SentimentResult:
    """Output of FinBERT2Adapter.score_text()."""

    sentiment_score: float  # -1 (very negative) to +1 (very positive)
    confidence: float       # model softmax confidence
    label: str              # 'positive', 'neutral', 'negative'
    raw_scores: dict[str, float]


@lru_cache(maxsize=1)
def _load_pipeline(device: str) -> Any:
    try:
        from transformers import pipeline as hf_pipeline  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "Transformers is not installed. Run: pip install 'mimic-forecast[finbert]'"
        ) from e

    logger.info("Loading FinBERT from HuggingFace…")
    pipe = hf_pipeline(
        "text-classification",
        model=_HF_REPO,
        top_k=None,
        device=0 if _cuda_available() else -1,
    )
    logger.info("FinBERT loaded.")
    return pipe


def _cuda_available() -> bool:
    try:
        import torch  # type: ignore[import]
        return torch.cuda.is_available()
    except ImportError:
        return False


class FinBERT2Adapter(ForecasterAdapter):
    """FinBERT sentiment adapter.

    Not a time-series model — scores news/filings for directional signal.
    Use score_text() for single texts, or forecast() to build a sentiment
    time series from a list of texts aligned to dates.
    """

    @property
    def name(self) -> str:
        return "finbert-sentiment"

    def score_text(self, text: str) -> SentimentResult:
        """Return a sentiment score for a single piece of financial text."""
        pipe = _load_pipeline("cuda" if _cuda_available() else "cpu")
        results = pipe(text[:512])[0]  # truncate to BERT limit

        scores = {r["label"].lower(): r["score"] for r in results}
        positive = scores.get("positive", 0.0)
        negative = scores.get("negative", 0.0)
        neutral = scores.get("neutral", 0.0)

        # Map to [-1, +1]
        sentiment_score = float(positive - negative)
        top_label = max(scores, key=lambda k: scores[k])
        confidence = float(scores[top_label])

        return SentimentResult(
            sentiment_score=round(sentiment_score, 4),
            confidence=round(confidence, 4),
            label=top_label,
            raw_scores=scores,
        )

    def score_texts(self, texts: list[str]) -> list[SentimentResult]:
        """Score multiple texts in one batched pass."""
        return [self.score_text(t) for t in texts]

    def forecast(
        self,
        series: pd.Series,
        horizon: int,
        frequency: str = "D",
        covariates: dict[str, pd.Series] | None = None,
    ) -> ForecastResult:
        """Build a sentiment trend forecast.

        series: pd.Series of text strings indexed by date.
        Returns a directional score series as the point forecast.
        """
        if not all(isinstance(v, str) for v in series.values[:5]):
            raise ValueError(
                "FinBERT2Adapter.forecast() expects a Series of text strings, "
                "not numeric values. Use score_text() for single texts."
            )

        sentiment_scores = [self.score_text(str(v)).sentiment_score for v in series.values]
        smoothed = pd.Series(sentiment_scores, index=series.index).rolling(3, min_periods=1).mean()

        future_index = self._build_future_index(series, horizon, frequency)
        last_score = float(smoothed.iloc[-1])

        # Simple persistence forecast — sentiment signal decays toward neutral
        decay = np.exp(-np.arange(1, horizon + 1) / max(horizon / 2, 1))
        point_vals = last_score * decay
        point = pd.Series(point_vals, index=future_index, name="sentiment_forecast")

        upper = point + 0.3
        lower = point - 0.3
        quantiles = {
            0.1: lower.clip(-1, 1),
            0.5: point.clip(-1, 1),
            0.9: upper.clip(-1, 1),
        }

        return ForecastResult(
            point=point,
            quantiles=quantiles,
            model_name=self.name,
            confidence=0.6,
            metadata={"type": "sentiment_decay", "last_score": last_score},
        )
