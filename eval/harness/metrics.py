"""Scoring metrics — Plan §11.1.

- directional_accuracy(simulated, truth) — fraction of correctly-signed deltas
- crps(samples, truth) — continuous ranked probability score (lower is better)
- wasserstein1(samples_a, samples_b) — 1-Wasserstein distance for decision realism

All metrics are pure numpy and deterministic. No external deps beyond numpy.
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np


def directional_accuracy(simulated: Sequence[float], truth: Sequence[float]) -> float:
    """Fraction of (simulated, truth) pairs whose signs match.

    Pairs where truth is exactly zero are excluded from the count (a sign of 0
    is ambiguous). If all truths are zero, returns 1.0 only when all simulated
    are zero too; otherwise 0.0.
    """
    sim = np.asarray(simulated, dtype=float)
    tru = np.asarray(truth, dtype=float)
    if sim.shape != tru.shape:
        raise ValueError(f"shape mismatch: simulated={sim.shape}, truth={tru.shape}")
    mask = tru != 0
    if not mask.any():
        return float(np.all(sim == 0))
    return float(np.mean(np.sign(sim[mask]) == np.sign(tru[mask])))


def crps(samples: Sequence[float], truth: float) -> float:
    """Continuous Ranked Probability Score via the empirical estimator.

        CRPS(F, y) = E|X - y| - 0.5 * E|X - X'|

    Lower is better. Perfectly calibrated deterministic forecasts give 0.
    """
    x = np.asarray(samples, dtype=float)
    if x.size == 0:
        raise ValueError("samples must be non-empty")
    term1 = float(np.mean(np.abs(x - truth)))
    # E|X - X'| using the sort-based O(n log n) formulation
    s = np.sort(x)
    n = s.size
    weights = (2 * np.arange(1, n + 1) - n - 1) / (n * n)
    term2 = float(np.sum(weights * s))
    return term1 - term2


def wasserstein1(samples_a: Sequence[float], samples_b: Sequence[float]) -> float:
    """1-Wasserstein distance between two empirical distributions (1D).

    Computed via the closed form:
        W_1(F, G) = integral |F^{-1}(t) - G^{-1}(t)| dt
    which reduces to mean(|sort(a)_i - sort(b)_i|) when |a| == |b|.
    For unequal sizes we interpolate the CDFs onto a common quantile grid.
    """
    a = np.sort(np.asarray(samples_a, dtype=float))
    b = np.sort(np.asarray(samples_b, dtype=float))
    if a.size == 0 or b.size == 0:
        raise ValueError("both sample sets must be non-empty")
    if a.size == b.size:
        return float(np.mean(np.abs(a - b)))
    n = max(a.size, b.size) * 4  # oversample the quantile grid for stability
    qs = (np.arange(n) + 0.5) / n
    aq = np.quantile(a, qs)
    bq = np.quantile(b, qs)
    return float(np.mean(np.abs(aq - bq)))
