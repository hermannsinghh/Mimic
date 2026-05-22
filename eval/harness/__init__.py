"""Mimic calibration / eval harness.

Replays scenarios against historical episodes and emits a signed calibration
badge.

Metrics (Plan §11.1):
    directional_accuracy(simulated, truth)
    crps(samples, truth)
    wasserstein1(samples_a, samples_b)
"""
from .metrics import crps, directional_accuracy, wasserstein1  # noqa: F401
from .scorer import CalibrationBadge  # noqa: F401

__all__ = ["CalibrationBadge", "directional_accuracy", "crps", "wasserstein1"]
