"""Per-node probabilistic forecast API — Plan §3.2 FC-06.

    forecast_node(adapter, node, horizon, quantiles, ...) -> NodeForecast

`node` is a FIBO IRI (or any opaque entity reference); `series_resolver` is a
caller-supplied function that turns the node into the underlying time series the
adapter consumes. This decouples the forecast contract from connector wiring —
in production the resolver lives in `mimic.framework.signal.sources`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from .base import ForecasterAdapter, ForecastResult

SeriesResolver = Callable[[str], pd.Series]
DEFAULT_QUANTILES = (0.1, 0.5, 0.9)


@dataclass(frozen=True)
class NodeForecast:
    """Per-node probabilistic forecast.

    `distribution[q]` is the value at quantile q at each horizon step (pd.Series
    indexed by future timestamps). `q==0.5` is the median.
    """
    node: str
    model_name: str
    horizon: int
    point: pd.Series
    distribution: dict[float, pd.Series]
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


def forecast_node(
    adapter: ForecasterAdapter,
    node: str,
    horizon: int,
    *,
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
    series_resolver: SeriesResolver,
    frequency: str = "D",
    covariates: dict[str, pd.Series] | None = None,
) -> NodeForecast:
    """Produce a NodeForecast for `node`.

    Adapter is consulted for its native distribution; if it returns more or
    fewer quantiles than requested, we interpolate using linear interpolation
    over the available quantile levels at each timestamp.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if not quantiles or any(not 0 < q < 1 for q in quantiles):
        raise ValueError("quantiles must be a non-empty tuple of values in (0, 1)")

    series = series_resolver(node)
    if not isinstance(series, pd.Series):
        raise TypeError(f"series_resolver({node!r}) returned {type(series).__name__}, expected pandas.Series")

    raw: ForecastResult = adapter.forecast(series, horizon, frequency=frequency, covariates=covariates)
    distribution = _align_quantiles(raw.quantiles, requested=quantiles)

    return NodeForecast(
        node=node,
        model_name=raw.model_name,
        horizon=horizon,
        point=raw.point,
        distribution=distribution,
        confidence=raw.confidence,
        metadata={**raw.metadata, "requested_quantiles": list(quantiles)},
    )


def _align_quantiles(
    available: dict[float, pd.Series],
    *,
    requested: tuple[float, ...],
) -> dict[float, pd.Series]:
    """Return a dict containing exactly the requested quantiles.

    If the adapter already provides q, use it. Otherwise linearly interpolate
    between the two nearest provided quantiles at each timestamp.
    """
    if not available:
        raise ValueError("adapter returned no quantiles")
    out: dict[float, pd.Series] = {}
    sorted_qs = sorted(available.keys())
    for q in requested:
        if q in available:
            out[q] = available[q]
            continue
        # find bracketing quantiles
        lower = max((x for x in sorted_qs if x < q), default=None)
        upper = min((x for x in sorted_qs if x > q), default=None)
        if lower is None:
            out[q] = available[sorted_qs[0]]
        elif upper is None:
            out[q] = available[sorted_qs[-1]]
        else:
            t = (q - lower) / (upper - lower)
            out[q] = available[lower] * (1 - t) + available[upper] * t
    return out
