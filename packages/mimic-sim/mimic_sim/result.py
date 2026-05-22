"""
SimulationResult — analytics layer on top of raw Monte Carlo runs.

All financial figures are in USD billions unless noted.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from mimic_sim.execution.tier3_formulas import RunOutcome


@dataclass
class SimulationResult:
    """
    Immutable result of a completed simulation.
    Wraps a list of RunOutcome objects and exposes analytics methods.
    """

    n_runs: int
    scenario_name: str
    tickers: list[str]
    runs: list[RunOutcome]
    mode: str  # "tier1", "tier2", "tier3"

    # ── Internal helpers ───────────────────────────────────────────────────

    def _values(self, ticker: str, metric: str) -> np.ndarray:
        """Extract per-run scalar values for (ticker, metric)."""
        out = []
        for run in self.runs:
            co = run.company_outcomes.get(ticker)
            if co is None:
                raise KeyError(f"Ticker '{ticker}' not found in simulation results.")
            val = getattr(co, metric, None)
            if val is None:
                raise AttributeError(f"Metric '{metric}' not found on CompanyOutcome.")
            out.append(float(val))
        return np.array(out)

    def _time_series(self, ticker: str) -> np.ndarray:
        """Return (n_runs × n_steps) array of time-step impacts."""
        rows = []
        for run in self.runs:
            steps = run.time_step_impacts.get(ticker, [])
            rows.append(steps)
        return np.array(rows)

    # ── Descriptive statistics ─────────────────────────────────────────────

    def mean(self, ticker: str, metric: str = "financial_impact") -> float:
        return float(self._values(ticker, metric).mean())

    def std(self, ticker: str, metric: str = "financial_impact") -> float:
        return float(self._values(ticker, metric).std())

    def percentile(self, ticker: str, metric: str, p: float) -> float:
        """
        p-th percentile of metric distribution for ticker.
        p is in [0, 100].  e.g. percentile("WMT", "financial_impact", 5)
        gives the worst-5% outcome.
        """
        return float(np.percentile(self._values(ticker, metric), p))

    def describe(self, ticker: str, metric: str = "financial_impact") -> pd.Series:
        vals = self._values(ticker, metric)
        return pd.Series(
            {
                "mean": vals.mean(),
                "std": vals.std(),
                "p5": np.percentile(vals, 5),
                "p25": np.percentile(vals, 25),
                "p50": np.percentile(vals, 50),
                "p75": np.percentile(vals, 75),
                "p95": np.percentile(vals, 95),
                "min": vals.min(),
                "max": vals.max(),
                "skew": float(pd.Series(vals).skew()),
                "kurtosis": float(pd.Series(vals).kurtosis()),
            },
            name=f"{ticker}/{metric}",
        )

    # ── Risk metrics ───────────────────────────────────────────────────────

    def var(self, ticker: str, confidence: float = 0.95) -> float:
        """
        Value at Risk: the loss not exceeded in (confidence*100)% of runs.
        Expressed as a negative number (a loss).

        e.g. var("WMT", 0.95) = -2.1  means 95% of runs lose <= $2.1B
        """
        vals = self._values(ticker, "financial_impact")
        # VaR is the (1-confidence) quantile of the loss distribution
        return float(np.percentile(vals, (1 - confidence) * 100))

    def cvar(self, ticker: str, confidence: float = 0.95) -> float:
        """
        Conditional Value at Risk (Expected Shortfall): the expected loss
        among the worst (1-confidence) fraction of runs.
        Always worse than (more negative than) VaR.
        """
        vals = self._values(ticker, "financial_impact")
        threshold = self.var(ticker, confidence)
        tail = vals[vals <= threshold]
        if len(tail) == 0:
            return threshold
        return float(tail.mean())

    # ── Cross-company analysis ─────────────────────────────────────────────

    def correlation_matrix(self, metric: str = "financial_impact") -> pd.DataFrame:
        """Pearson correlation of outcomes across tickers."""
        data = {t: self._values(t, metric) for t in self.tickers}
        return pd.DataFrame(data).corr()

    def tail_coincidence(
        self,
        ticker_a: str,
        ticker_b: str,
        percentile_threshold: float = 10,
        metric: str = "financial_impact",
    ) -> float:
        """
        Fraction of runs where BOTH companies simultaneously hit their
        worst-`percentile_threshold`% outcomes.  A measure of systemic risk.
        """
        vals_a = self._values(ticker_a, metric)
        vals_b = self._values(ticker_b, metric)
        thresh_a = np.percentile(vals_a, percentile_threshold)
        thresh_b = np.percentile(vals_b, percentile_threshold)
        both_bad = (vals_a <= thresh_a) & (vals_b <= thresh_b)
        return float(both_bad.mean())

    # ── Sensitivity analysis ───────────────────────────────────────────────

    def sensitivity(
        self,
        target_ticker: str,
        target_metric: str = "financial_impact",
    ) -> dict[str, float]:
        """
        Variance-based sensitivity: fraction of outcome variance explained
        by each input parameter.  Uses squared Spearman correlation as a
        rank-based proxy (robust to non-linearity).

        Returns dict sorted by importance, values sum to ≈ 1.0.
        """
        target = self._values(target_ticker, target_metric)
        inputs: dict[str, np.ndarray] = {}

        # Scalar params from SampledParams
        inputs["severity"] = np.array([r.params.severity for r in self.runs])
        inputs["duration_days"] = np.array([r.params.duration_days for r in self.runs])
        inputs["intervention"] = np.array(
            [float(r.params.intervention_triggered) for r in self.runs]
        )

        # Macro conditions (present in all runs)
        if self.runs[0].params.macro_conditions:
            for key in self.runs[0].params.macro_conditions:
                inputs[key] = np.array(
                    [r.params.macro_conditions.get(key, 0.0) for r in self.runs]
                )

        from scipy.stats import spearmanr

        r2: dict[str, float] = {}
        for name, arr in inputs.items():
            if arr.std() < 1e-10:
                r2[name] = 0.0
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                corr, _ = spearmanr(arr, target)
            r2[name] = float(corr**2)

        total = sum(r2.values()) or 1.0
        normalised = {k: round(v / total, 4) for k, v in sorted(r2.items(), key=lambda x: -x[1])}
        return normalised

    # ── Extreme-run retrieval ──────────────────────────────────────────────

    def worst_runs(
        self, n: int = 10, ticker: str | None = None, metric: str = "financial_impact"
    ) -> list[RunOutcome]:
        t = ticker or self.tickers[0]
        vals = self._values(t, metric)
        idx = np.argsort(vals)[:n]
        return [self.runs[i] for i in idx]

    def best_runs(
        self, n: int = 10, ticker: str | None = None, metric: str = "financial_impact"
    ) -> list[RunOutcome]:
        t = ticker or self.tickers[0]
        vals = self._values(t, metric)
        idx = np.argsort(vals)[-n:][::-1]
        return [self.runs[i] for i in idx]

    def median_run(self, ticker: str | None = None) -> RunOutcome:
        t = ticker or self.tickers[0]
        vals = self._values(t, "financial_impact")
        idx = int(np.argsort(np.abs(vals - np.median(vals)))[0])
        return self.runs[idx]

    # ── Summary table ──────────────────────────────────────────────────────

    def summary(self) -> pd.DataFrame:
        """One-row-per-ticker summary with key risk metrics."""
        rows = []
        for ticker in self.tickers:
            rows.append(
                {
                    "ticker": ticker,
                    "mean_impact_bn": round(self.mean(ticker), 3),
                    "std_bn": round(self.std(ticker), 3),
                    "p5_bn": round(self.percentile(ticker, "financial_impact", 5), 3),
                    "p50_bn": round(self.percentile(ticker, "financial_impact", 50), 3),
                    "p95_bn": round(self.percentile(ticker, "financial_impact", 95), 3),
                    "var_95_bn": round(self.var(ticker, 0.95), 3),
                    "cvar_95_bn": round(self.cvar(ticker, 0.95), 3),
                }
            )
        return pd.DataFrame(rows).set_index("ticker")

    def __repr__(self) -> str:
        return (
            f"SimulationResult(n_runs={self.n_runs}, mode='{self.mode}', "
            f"scenario='{self.scenario_name}', tickers={self.tickers})"
        )
