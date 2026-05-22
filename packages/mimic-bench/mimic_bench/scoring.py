"""Fidelity scoring for mimic-bench.

Score components (weights sum to 1.0):
  action_alignment (0.40): semantic similarity between predicted and actual action strings
  financial_accuracy (0.30): 1 - min(|pred - actual| / |actual|, 1)
  direction_accuracy (0.20): sign match on financial impact
  timing_accuracy   (0.10): whether predicted timing window matches the highest-signal window

The composite fidelity score ranges from 0.0 (completely wrong) to 1.0 (perfect).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional


WEIGHTS: Dict[str, float] = {
    "action_alignment": 0.40,
    "financial_accuracy": 0.30,
    "direction_accuracy": 0.20,
    "timing_accuracy": 0.10,
}

# Lazy-loaded sentence-transformer model (optional dependency)
_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            _encoder = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            pass  # fall back to token-overlap
    return _encoder


def _semantic_similarity(a: str, b: str) -> float:
    """Cosine similarity if sentence-transformers is installed, else token overlap."""
    if not a or not b:
        return 0.0

    encoder = _get_encoder()
    if encoder is not None:
        import numpy as np  # type: ignore

        embs = encoder.encode([a, b])
        num = float(np.dot(embs[0], embs[1]))
        denom = float(np.linalg.norm(embs[0]) * np.linalg.norm(embs[1]))
        return max(0.0, num / denom) if denom > 0 else 0.0

    # Fallback: Jaccard similarity on lowercased tokens
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / len(ta | tb)


def _action_alignment(prediction: dict, ground_truth: dict) -> float:
    """Average cosine similarity across available time windows."""
    windows = ["action_0_24h", "action_1_7d", "action_8_30d"]
    scores: List[float] = []
    for w in windows:
        pred_text = prediction.get(w) or prediction.get(f"predicted_{w}")
        gt_key = f"actual_{w}"
        gt_text = ground_truth.get(gt_key)
        if gt_text is None:
            continue  # window not labeled, skip
        if pred_text is None:
            scores.append(0.0)
        else:
            scores.append(_semantic_similarity(str(pred_text), str(gt_text)))
    return sum(scores) / len(scores) if scores else 0.0


def _financial_accuracy(prediction: dict, ground_truth: dict) -> Optional[float]:
    """1 - min(|pred - actual| / |actual|, 1). Returns None if actual unknown."""
    actual = ground_truth.get("financial_impact_usdM")
    if actual is None or not ground_truth.get("financial_impact_reported", False):
        return None
    pred = prediction.get("financial_impact_usdM")
    if pred is None:
        return 0.0
    if actual == 0.0:
        return 1.0 if pred == 0.0 else 0.0
    return 1.0 - min(abs(pred - actual) / abs(actual), 1.0)


def _direction_accuracy(prediction: dict, ground_truth: dict) -> Optional[float]:
    """1 if signs match (or both zero), 0 otherwise. None if actual unknown."""
    actual = ground_truth.get("financial_impact_usdM")
    if actual is None:
        return None
    pred = prediction.get("financial_impact_usdM")
    if pred is None:
        # try explicit direction field
        pred_dir = prediction.get("direction")
        if pred_dir is None:
            return 0.0
        actual_dir = "positive" if actual > 0 else "negative" if actual < 0 else "neutral"
        return 1.0 if pred_dir == actual_dir else 0.0
    actual_sign = math.copysign(1, actual) if actual != 0 else 0
    pred_sign = math.copysign(1, pred) if pred != 0 else 0
    return 1.0 if actual_sign == pred_sign else 0.0


def _timing_accuracy(prediction: dict, ground_truth: dict) -> float:
    """Check if the model identified the primary response window."""
    windows = ["action_0_24h", "action_1_7d", "action_8_30d"]
    # Find the highest-signal ground truth window
    primary_gt = None
    for w in windows:
        if ground_truth.get(f"actual_{w}"):
            primary_gt = w
            break
    if primary_gt is None:
        return 1.0  # no specific timing signal; treat as neutral

    pred_primary = prediction.get("primary_timing_window")
    if pred_primary is None:
        # Infer from which predicted window has content
        for w in windows:
            if prediction.get(w) or prediction.get(f"predicted_{w}"):
                pred_primary = w
                break
    return 1.0 if pred_primary == primary_gt else 0.5  # partial credit for adjacent


def fidelity_score(prediction: dict, ground_truth: dict) -> dict:
    """Compute multi-component fidelity score.

    Args:
        prediction: Dict with optional keys:
            action_0_24h, action_1_7d, action_8_30d,
            financial_impact_usdM, direction, primary_timing_window
        ground_truth: Single JSONL record from labels_v1.jsonl

    Returns:
        Dict with composite score and per-component breakdown.
    """
    components: Dict[str, Optional[float]] = {
        "action_alignment": _action_alignment(prediction, ground_truth),
        "financial_accuracy": _financial_accuracy(prediction, ground_truth),
        "direction_accuracy": _direction_accuracy(prediction, ground_truth),
        "timing_accuracy": _timing_accuracy(prediction, ground_truth),
    }

    # Re-weight if some components are None (unscored)
    active = {k: v for k, v in components.items() if v is not None}
    if not active:
        return {"composite": 0.0, "components": components, "weights_used": {}}

    total_weight = sum(WEIGHTS[k] for k in active)
    composite = sum(active[k] * WEIGHTS[k] for k in active) / total_weight
    weights_used = {k: WEIGHTS[k] / total_weight for k in active}

    return {
        "composite": round(composite, 4),
        "components": {k: round(v, 4) if v is not None else None for k, v in components.items()},
        "weights_used": {k: round(v, 4) for k, v in weights_used.items()},
    }


def aggregate_scores(results: List[dict]) -> dict:
    if not results:
        return {}

    composites = [r["score"]["composite"] for r in results if "score" in r and "error" not in r]
    if not composites:
        return {}

    by_event: Dict[str, List[float]] = {}
    by_sector: Dict[str, List[float]] = {}
    by_category: Dict[str, List[float]] = {}
    component_totals: Dict[str, List[float]] = {k: [] for k in WEIGHTS}

    for r in results:
        if "score" not in r or "error" in r:
            continue
        score = r["score"]
        by_event.setdefault(r["event_id"], []).append(score["composite"])
        by_sector.setdefault(r.get("sector", "unknown"), []).append(score["composite"])
        by_category.setdefault(r.get("event_category", "unknown"), []).append(score["composite"])
        for comp in WEIGHTS:
            val = score.get("components", {}).get(comp)
            if val is not None:
                component_totals[comp].append(val)

    def _stats(vals: List[float]) -> dict:
        n = len(vals)
        if n == 0:
            return {"mean": 0.0, "std": 0.0, "n": 0}
        mean = sum(vals) / n
        var = sum((v - mean) ** 2 for v in vals) / n
        return {"mean": round(mean, 4), "std": round(var**0.5, 4), "n": n}

    return {
        "overall": _stats(composites),
        "by_event": {k: _stats(v) for k, v in sorted(by_event.items())},
        "by_sector": {k: _stats(v) for k, v in sorted(by_sector.items())},
        "by_category": {k: _stats(v) for k, v in sorted(by_category.items())},
        "by_component": {k: _stats(component_totals[k]) for k in WEIGHTS},
    }
