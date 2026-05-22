"""Plugin interface called by mimic.core.twin — zero hard dependency."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from mimic_forecast import registry
from mimic_forecast.data.series import pull_series

logger = logging.getLogger(__name__)


def forecast_for_event(
    context: dict[str, Any],
    event: str,
    horizon: int = 30,
    frequency: str = "D",
    fred_api_key: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Given a company context dict and event string, return quantitative forecasts.

    This is the primary entry point called by mimic's orchestrator when
    mimic-forecast is installed.

    Args:
        context: Company context dict with keys like 'ticker', 'sector', etc.
        event: Free-text event description (e.g. "oil spikes to $150").
        horizon: Forecast horizon in steps (default 30 days).
        frequency: Pandas offset alias for step size (default 'D').
        fred_api_key: Optional FRED API key for macro series.

    Returns:
        Dict mapping series_name → {point_end, q10, q90, model, confidence}.
    """
    event_type = registry.detect_event_type(event)
    series_names = registry.series_for_event(event_type)

    logger.info(
        "Event '%s' classified as '%s'. Forecasting %d series.",
        event,
        event_type,
        len(series_names),
    )

    results: dict[str, dict[str, Any]] = {}

    for series_name in series_names:
        spec = registry.SERIES_REGISTRY.get(series_name)
        if spec is None:
            continue

        try:
            series = pull_series(
                ticker=spec["ticker"],
                source=spec["source"],
                years=5,
                fred_api_key=fred_api_key,
            )
        except Exception as exc:
            logger.warning("Could not fetch series '%s': %s", series_name, exc)
            continue

        try:
            adapter = registry.best_model_for(series_name)
            result = adapter.forecast(series, horizon=horizon, frequency=frequency)

            results[series_name] = {
                "point_end": float(result.point.iloc[-1]),
                "q10": float(result.quantiles[0.1].iloc[-1]) if 0.1 in result.quantiles else None,
                "q90": float(result.quantiles[0.9].iloc[-1]) if 0.9 in result.quantiles else None,
                "model": result.model_name,
                "confidence": result.confidence,
                "horizon_steps": len(result.point),
            }
            logger.info(
                "  %s → %.2f [%.2f, %.2f] via %s",
                series_name,
                results[series_name]["point_end"],
                results[series_name]["q10"] or 0,
                results[series_name]["q90"] or 0,
                result.model_name,
            )
        except Exception as exc:
            logger.warning("Forecast failed for '%s': %s", series_name, exc)

    return results


def get_forecaster(auto: bool = True) -> "AutoForecaster":
    """Factory used by mimic.core.twin when mimic-forecast is installed."""
    return AutoForecaster()


class AutoForecaster:
    """Auto-selects the best available model per series.

    This is what mimic calls when it does:
        from mimic_forecast import get_forecaster
        forecaster = get_forecaster(auto=True)
        forecast_context = forecaster.forecast_for_event(context, event)
    """

    def forecast_for_event(
        self,
        context: dict[str, Any],
        event: str,
        horizon: int = 30,
        frequency: str = "D",
        fred_api_key: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        return forecast_for_event(
            context=context,
            event=event,
            horizon=horizon,
            frequency=frequency,
            fred_api_key=fred_api_key,
        )
