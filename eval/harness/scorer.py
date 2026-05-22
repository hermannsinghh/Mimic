"""Scoring metrics — Plan §11.1.

TODO:
- implement directional_accuracy(simulated, truth)
- implement crps(simulated_distribution, truth)
- implement decision_realism_wasserstein(simulated_actions, historical_actions)
- emit a CalibrationBadge dataclass
"""
from __future__ import annotations

from pydantic import BaseModel


class CalibrationBadge(BaseModel):
    scenario_id: str
    scenario_version: str
    mimic_version: str
    directional_accuracy: float
    crps: float | None = None
    decision_realism_w1: float | None = None
    usd_per_run: float
    badge_signature: str | None = None
