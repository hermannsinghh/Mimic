"""
Parameter space and distribution wrappers for mimic-sim.

Each simulation run samples from a ParameterSpace to produce a self-consistent
set of inputs: event severity, duration, macro conditions, and behavioral variation.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Any

from scipy import stats as scipy_stats


class Distribution:
    """
    Thin wrapper around scipy distributions for readable parameter definitions.

    All sample() calls return a single float. Use sample_many(n) for vectorised
    sampling when building a batch of run parameters.
    """

    def __init__(self, dist: Any, **kwargs: Any) -> None:
        self._dist = dist
        self._kwargs = kwargs

    def sample(self, rng: np.random.Generator | None = None) -> float:
        if rng is not None:
            return float(self._dist.rvs(random_state=rng, **self._kwargs))
        return float(self._dist.rvs(**self._kwargs))

    def sample_many(self, n: int, rng: np.random.Generator | None = None) -> np.ndarray:
        if rng is not None:
            return self._dist.rvs(size=n, random_state=rng, **self._kwargs)
        return self._dist.rvs(size=n, **self._kwargs)

    def ppf(self, q: float) -> float:
        """Percent-point function (inverse CDF) — useful for plotting."""
        return float(self._dist.ppf(q, **self._kwargs))

    def mean(self) -> float:
        return float(self._dist.mean(**self._kwargs))

    def std(self) -> float:
        return float(self._dist.std(**self._kwargs))

    # ── Factories ──────────────────────────────────────────────────────────

    @staticmethod
    def uniform(low: float, high: float) -> Distribution:
        """Uniform distribution between [low, high]."""
        return Distribution(scipy_stats.uniform, loc=low, scale=high - low)

    @staticmethod
    def normal(mean: float, std: float) -> Distribution:
        """Normal (Gaussian) distribution. Truncated at zero for positive quantities."""
        return Distribution(scipy_stats.norm, loc=mean, scale=std)

    @staticmethod
    def lognormal(mean: float, sigma: float) -> Distribution:
        """
        Log-normal parameterised by the mean of the *underlying* normal.
        Good for durations, prices — strictly positive with a fat right tail.
        """
        return Distribution(scipy_stats.lognorm, s=sigma, scale=np.exp(mean))

    @staticmethod
    def triangular(low: float, mode: float, high: float) -> Distribution:
        """
        Triangular distribution — natural for expert-elicited ranges where
        you know the worst case, best case, and most likely value.
        """
        c = (mode - low) / (high - low)
        return Distribution(scipy_stats.triang, c=c, loc=low, scale=high - low)

    @staticmethod
    def beta(alpha: float, beta: float, low: float = 0.0, high: float = 1.0) -> Distribution:
        """Beta distribution scaled to [low, high] — good for probabilities."""
        return Distribution(
            scipy_stats.beta, a=alpha, b=beta, loc=low, scale=high - low
        )

    @staticmethod
    def empirical(samples: list[float]) -> Distribution:
        """
        Kernel-density-estimated distribution from historical data.
        Use when you have past observations to anchor parameter ranges.
        """
        samples_arr = np.asarray(samples, dtype=float)
        kde = scipy_stats.gaussian_kde(samples_arr)
        # Wrap KDE in a scipy rv_continuous-compatible shim
        return _KDEDistribution(kde, samples_arr)

    @staticmethod
    def constant(value: float) -> Distribution:
        """Deterministic 'distribution' — useful for fixing a single parameter."""
        return Distribution(scipy_stats.uniform, loc=value, scale=0.0)


class _KDEDistribution(Distribution):
    """Internal: KDE-backed distribution for empirical samples."""

    def __init__(self, kde: scipy_stats.gaussian_kde, samples: np.ndarray) -> None:
        self._kde = kde
        self._samples = samples

    def sample(self, rng: np.random.Generator | None = None) -> float:
        seed = int(rng.integers(0, 2**31)) if rng is not None else None
        return float(self._kde.resample(1, seed=seed)[0][0])

    def sample_many(self, n: int, rng: np.random.Generator | None = None) -> np.ndarray:
        seed = int(rng.integers(0, 2**31)) if rng is not None else None
        return self._kde.resample(n, seed=seed)[0]

    def ppf(self, q: float) -> float:
        xs = np.linspace(self._samples.min(), self._samples.max(), 1000)
        cdf = self._kde.integrate_box_1d(self._samples.min(), xs)
        return float(np.interp(q, cdf, xs))

    def mean(self) -> float:
        return float(self._samples.mean())

    def std(self) -> float:
        return float(self._samples.std())


@dataclass
class SampledParams:
    """One fully-realised draw from a ParameterSpace — a single run's inputs."""

    severity: float
    duration_days: float
    macro_conditions: dict[str, float]
    company_behavior: dict[str, dict[str, float]]
    intervention_triggered: bool
    run_seed: int


@dataclass
class ParameterSpace:
    """
    Defines all random dimensions of a Monte Carlo simulation.

    severity         : how severe is the triggering event (0–1 scale)
    duration_days    : how long does the event last
    macro_conditions : dict of macro variable → Distribution
                       e.g. {"oil_price": Distribution.normal(85, 20)}
    company_behavior : dict of ticker → dict of behavior key → Distribution
                       e.g. {"WMT": {"risk_appetite_delta": Distribution.normal(0, 0.1)}}
    intervention_probability : P(government/Fed intervenes during the event)
    """

    severity: Distribution = field(
        default_factory=lambda: Distribution.triangular(low=0.4, mode=0.7, high=0.95)
    )
    duration_days: Distribution = field(
        default_factory=lambda: Distribution.lognormal(mean=3.4, sigma=0.5)  # ~30d median
    )
    macro_conditions: dict[str, Distribution] = field(default_factory=dict)
    company_behavior: dict[str, dict[str, Distribution]] = field(default_factory=dict)
    intervention_probability: float = 0.15

    def sample(self, rng: np.random.Generator) -> SampledParams:
        """Draw one complete parameter set for a simulation run."""
        seed = int(rng.integers(0, 2**31))
        macro = {k: v.sample(rng) for k, v in self.macro_conditions.items()}
        behavior: dict[str, dict[str, float]] = {}
        for ticker, dims in self.company_behavior.items():
            behavior[ticker] = {k: v.sample(rng) for k, v in dims.items()}

        return SampledParams(
            severity=self.severity.sample(rng),
            duration_days=max(1.0, self.duration_days.sample(rng)),
            macro_conditions=macro,
            company_behavior=behavior,
            intervention_triggered=float(rng.random()) < self.intervention_probability,
            run_seed=seed,
        )

    def sample_batch(
        self, n: int, seed: int | None = None
    ) -> list[SampledParams]:
        """Vectorised draw of n parameter sets — used by the simulation loop."""
        rng = np.random.default_rng(seed)
        return [self.sample(rng) for _ in range(n)]
