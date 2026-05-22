"""Equivalence harness — Plan §9 / ADR 2026-05-21-runner-equivalence-criterion."""
from .noise_floor import NoiseFloorResult, measure_noise_floor  # noqa: F401

__all__ = ["NoiseFloorResult", "measure_noise_floor"]
