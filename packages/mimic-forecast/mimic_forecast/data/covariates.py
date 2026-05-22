"""Build covariate matrices for multivariate adapters."""

from __future__ import annotations

import pandas as pd

from mimic_forecast.data.series import pull_series


def build_covariates(
    cov_specs: dict[str, dict],
    start: str | None = None,
    end: str | None = None,
    years: int = 5,
) -> dict[str, pd.Series]:
    """Fetch multiple covariate series and return as a dict.

    Args:
        cov_specs: Mapping of name → {ticker, source, fred_api_key?}.
            Example: {"oil": {"ticker": "DCOILWTICO", "source": "fred"}}
        start: Start date string (optional).
        end: End date string (optional).
        years: Years of history if start is unspecified.

    Returns:
        Dict mapping covariate name to pd.Series.
    """
    result: dict[str, pd.Series] = {}
    for name, spec in cov_specs.items():
        result[name] = pull_series(
            ticker=spec["ticker"],
            source=spec.get("source", "auto"),
            start=start,
            end=end,
            years=years,
            fred_api_key=spec.get("fred_api_key"),
        )
    return result


def align_covariates(
    series: pd.Series,
    covariates: dict[str, pd.Series],
) -> dict[str, pd.Series]:
    """Align covariate series to the same index as the target series."""
    aligned: dict[str, pd.Series] = {}
    for name, cov in covariates.items():
        aligned[name] = cov.reindex(series.index, method="nearest").ffill()
    return aligned
