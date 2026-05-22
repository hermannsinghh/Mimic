"""
Visualisation utilities for SimulationResult.

All functions accept an optional `ax` parameter (matplotlib Axes) so they
can be embedded in larger dashboards, or called standalone (which creates
and shows the figure automatically).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from mimic_sim.result import SimulationResult


_PALETTE = ["#2563EB", "#DC2626", "#16A34A", "#D97706", "#7C3AED"]


def plot_distribution(
    result: SimulationResult,
    ticker: str,
    metric: str = "financial_impact",
    bins: int = 80,
    ax: Axes | None = None,
    show: bool = True,
) -> Axes:
    """Histogram of the metric distribution with VaR/CVaR overlays."""
    vals = result._values(ticker, metric)
    var95 = result.var(ticker, 0.95)
    cvar95 = result.cvar(ticker, 0.95)

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(10, 5))

    ax.hist(vals, bins=bins, color=_PALETTE[0], alpha=0.75, edgecolor="white", linewidth=0.4)
    ax.axvline(var95, color=_PALETTE[1], linewidth=1.8, linestyle="--", label=f"VaR 95%: {var95:.2f}B")
    ax.axvline(cvar95, color="#991B1B", linewidth=1.8, linestyle=":", label=f"CVaR 95%: {cvar95:.2f}B")
    ax.axvline(vals.mean(), color=_PALETTE[2], linewidth=1.5, linestyle="-", label=f"Mean: {vals.mean():.2f}B")

    ax.set_xlabel(f"{metric.replace('_', ' ').title()} (USD Billions)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.set_title(f"{ticker} — {metric.replace('_', ' ').title()} Distribution\n"
                 f"{result.scenario_name}  |  n={result.n_runs:,}  |  mode={result.mode}",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)

    if standalone and show:
        plt.tight_layout()
        plt.show()

    return ax


def plot_correlation_heatmap(
    result: SimulationResult,
    metric: str = "financial_impact",
    ax: Axes | None = None,
    show: bool = True,
) -> Axes:
    """Heatmap of outcome correlations across companies."""
    corr = result.correlation_matrix(metric)

    standalone = ax is None
    if standalone:
        n = len(result.tickers)
        fig, ax = plt.subplots(figsize=(max(5, n + 1), max(4, n)))

    im = ax.imshow(corr.values, cmap="RdYlGn", vmin=-1, vmax=1)
    ticks = range(len(corr.columns))
    ax.set_xticks(list(ticks))
    ax.set_yticks(list(ticks))
    ax.set_xticklabels(corr.columns, fontsize=10)
    ax.set_yticklabels(corr.index, fontsize=10)

    for i in range(len(corr)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center",
                    fontsize=9, color="black")

    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title(f"Outcome Correlation Matrix — {metric.replace('_', ' ').title()}", fontweight="bold")

    if standalone and show:
        plt.tight_layout()
        plt.show()

    return ax


def plot_sensitivity_tornado(
    result: SimulationResult,
    ticker: str,
    metric: str = "financial_impact",
    ax: Axes | None = None,
    show: bool = True,
) -> Axes:
    """Horizontal bar chart (tornado) of sensitivity indices."""
    sens = result.sensitivity(ticker, metric)

    labels = list(sens.keys())
    values = list(sens.values())

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(9, max(4, len(labels) * 0.55 + 1.5)))

    colors = [_PALETTE[0] if v > 0.1 else "#93C5FD" for v in values]
    bars = ax.barh(labels, values, color=colors, edgecolor="white")

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
            f"{val:.1%}", va="center", fontsize=9,
        )

    ax.set_xlabel("Fraction of Outcome Variance Explained", fontsize=10)
    ax.set_title(f"{ticker} — Sensitivity Tornado\n{metric.replace('_', ' ').title()}",
                 fontweight="bold")
    ax.set_xlim(0, max(values) * 1.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.invert_yaxis()

    if standalone and show:
        plt.tight_layout()
        plt.show()

    return ax


def plot_fan_chart(
    result: SimulationResult,
    ticker: str,
    ax: Axes | None = None,
    show: bool = True,
) -> Axes:
    """
    Time-series fan chart: median trajectory with probability bands.
    Bands: 10-90%, 25-75%, 40-60%.
    """
    ts = result._time_series(ticker)  # (n_runs × n_steps)
    if ts.shape[1] == 0:
        raise ValueError(f"No time-step data for {ticker}")

    cumulative = np.cumsum(ts, axis=1)
    n_steps = cumulative.shape[1]
    x = np.arange(1, n_steps + 1)

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(10, 5))

    bands = [
        (5, 95, 0.15, "10–90%"),
        (15, 85, 0.25, "25–75% (inner)"),
        (35, 65, 0.40, "35–65% (core)"),
    ]
    for lo, hi, alpha, label in bands:
        low_vals = np.percentile(cumulative, lo, axis=0)
        high_vals = np.percentile(cumulative, hi, axis=0)
        ax.fill_between(x, low_vals, high_vals, alpha=alpha, color=_PALETTE[0], label=label)

    median = np.percentile(cumulative, 50, axis=0)
    ax.plot(x, median, color=_PALETTE[0], linewidth=2, label="Median")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)

    ax.set_xlabel("Event Phase", fontsize=10)
    ax.set_ylabel("Cumulative Financial Impact (USD Billions)", fontsize=10)
    ax.set_title(f"{ticker} — Fan Chart: Cumulative Impact Over Event Phases\n"
                 f"{result.scenario_name}  |  n={result.n_runs:,}", fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"Phase {i}" for i in x])
    ax.legend(fontsize=9, loc="lower left")
    ax.spines[["top", "right"]].set_visible(False)

    if standalone and show:
        plt.tight_layout()
        plt.show()

    return ax


def plot_multi_ticker_distributions(
    result: SimulationResult,
    metric: str = "financial_impact",
    show: bool = True,
) -> None:
    """Grid of per-ticker histograms for quick comparison."""
    n = len(result.tickers)
    cols = min(3, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 5, rows * 4))
    axes_flat = np.array(axes).flatten() if n > 1 else [axes]

    for i, ticker in enumerate(result.tickers):
        plot_distribution(result, ticker, metric, ax=axes_flat[i], show=False)

    for j in range(i + 1, len(axes_flat)):
        axes_flat[j].set_visible(False)

    fig.suptitle(
        f"Outcome Distributions — {result.scenario_name}  |  n={result.n_runs:,}",
        fontsize=13, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    if show:
        plt.show()
