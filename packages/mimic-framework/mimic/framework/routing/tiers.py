"""Tier assignment for an entity — Plan §6.1.

`systemic_score` formula and thresholds live in routing/systemic.py.
Every change to thresholds is a semver minor bump.
"""
from __future__ import annotations

from typing import Literal, Protocol

Tier = Literal["T1", "T2", "T3"]

SYSTEMIC_T1_THRESHOLD = 0.80
SYSTEMIC_T2_THRESHOLD = 0.40


class _EntityLike(Protocol):
    systemic_score: float


def assign_tier(entity: _EntityLike) -> Tier:
    if entity.systemic_score >= SYSTEMIC_T1_THRESHOLD:
        return "T1"
    if entity.systemic_score >= SYSTEMIC_T2_THRESHOLD:
        return "T2"
    return "T3"
