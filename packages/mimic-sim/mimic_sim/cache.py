"""
Tier 2: Decision cache for cached-LLM simulation.

Pre-computes behavioral decisions over a severity × duration grid, then performs
nearest-neighbour lookup at simulation time to inject calibrated modifiers into
the Tier 3 formula engine.

Grid: severity [0.3, 0.5, 0.7, 0.9] × duration [7, 14, 30, 60, 90] = 20 configs.

Usage:
    from mimic_sim.cache import DecisionCache
    from mimic_sim.execution.tier3_formulas import CompanyProfile

    profiles = [CompanyProfile.walmart(), CompanyProfile.apple()]
    cache = DecisionCache()
    cache.build(profiles, scenario_name="taiwan_strait_closure_30d")
    cache.save("taiwan_cache.json")

    # Later:
    cache = DecisionCache.load("taiwan_cache.json")
    result = sim.run(mode="tier2", cache=cache)
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable


SEVERITY_GRID = [0.3, 0.5, 0.7, 0.9]
DURATION_GRID = [7, 14, 30, 60, 90]


def _default_decision_fn(
    ticker: str,
    severity: float,
    duration_days: float,
    scenario_name: str,
) -> dict[str, float]:
    """
    Formula-based proxy for LLM behavioral decisions.

    Approximates how a company would adjust its risk posture in response to
    an event of given severity and duration. Returns deltas relative to the
    company's baseline risk_appetite and decision_speed from its CompanyProfile.
    """
    duration_factor = math.log1p(duration_days / 30) / math.log1p(1)

    # Severe + long shocks push companies toward conservation and faster action
    risk_delta = -0.12 * severity * (0.5 + 0.5 * duration_factor)
    speed_delta = 0.08 * severity + 0.04 * duration_factor

    return {
        "risk_appetite_delta": round(float(risk_delta), 4),
        "decision_speed_delta": round(float(speed_delta), 4),
    }


class DecisionCache:
    """
    Tier 2 decision cache: pre-computed behavioral modifiers on a parameter grid.

    build() fills the 20-point grid (or more if you call a real LLM).
    lookup() does nearest-neighbour retrieval for any (severity, duration) pair.
    save() / load() persist the cache to JSON so you only pay for the LLM once.
    """

    SEVERITY_GRID = SEVERITY_GRID
    DURATION_GRID = DURATION_GRID

    def __init__(self) -> None:
        self._grid: dict[tuple[float, float], dict[str, dict[str, float]]] = {}
        self._scenario_name: str = ""
        self._tickers: list[str] = []

    def build(
        self,
        profiles: list,  # list[CompanyProfile]
        scenario_name: str,
        llm_fn: Callable[[str, float, float, str], dict[str, float]] | None = None,
    ) -> None:
        """
        Pre-compute behavioral decisions for every grid point.

        llm_fn(ticker, severity, duration_days, scenario_name) -> dict
            Must return at minimum {"risk_appetite_delta": float, "decision_speed_delta": float}.
            If None, uses the formula-based proxy (no LLM calls, no API cost).

        Calling with a real LLM fn costs ~20 × n_companies calls per scenario.
        The cache is reusable across all subsequent sim.run(mode='tier2') calls.
        """
        if llm_fn is None:
            llm_fn = _default_decision_fn

        self._scenario_name = scenario_name
        self._tickers = [p.ticker for p in profiles]
        self._grid = {}

        for severity in self.SEVERITY_GRID:
            for duration in self.DURATION_GRID:
                entry: dict[str, dict[str, float]] = {}
                for profile in profiles:
                    entry[profile.ticker] = llm_fn(
                        profile.ticker, severity, float(duration), scenario_name
                    )
                self._grid[(severity, float(duration))] = entry

    def lookup(
        self,
        severity: float,
        duration_days: float,
    ) -> dict[str, dict[str, float]]:
        """
        Nearest-neighbour lookup on the pre-computed grid.

        Returns a company_behavior dict compatible with SampledParams — i.e.,
        {ticker: {"risk_appetite_delta": float, "decision_speed_delta": float}}.

        Distance metric weights severity and duration equally after normalisation.
        """
        if not self._grid:
            raise RuntimeError("Cache is empty — call build() or load() first.")

        sev_range = max(self.SEVERITY_GRID) - min(self.SEVERITY_GRID)
        dur_range = max(self.DURATION_GRID) - min(self.DURATION_GRID)

        best_key = min(
            self._grid.keys(),
            key=lambda k: (
                ((k[0] - severity) / sev_range) ** 2
                + ((k[1] - duration_days) / dur_range) ** 2
            ),
        )
        return self._grid[best_key]

    def save(self, path: str | Path) -> None:
        """Persist the cache to a JSON file."""
        payload = {
            "scenario_name": self._scenario_name,
            "tickers": self._tickers,
            "grid": {
                f"{s},{d}": entry
                for (s, d), entry in self._grid.items()
            },
        }
        Path(path).write_text(json.dumps(payload, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> DecisionCache:
        """Load a previously saved cache from a JSON file."""
        payload = json.loads(Path(path).read_text())
        cache = cls()
        cache._scenario_name = payload["scenario_name"]
        cache._tickers = payload["tickers"]
        cache._grid = {
            (float(k.split(",")[0]), float(k.split(",")[1])): v
            for k, v in payload["grid"].items()
        }
        return cache

    def __len__(self) -> int:
        return len(self._grid)

    def __repr__(self) -> str:
        return (
            f"DecisionCache(scenario={self._scenario_name!r}, "
            f"tickers={self._tickers}, grid_points={len(self._grid)})"
        )
