"""Pull historical time series from FRED and Yahoo Finance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)

Source = Literal["fred", "yfinance", "auto"]


def pull_series(
    ticker: str,
    source: Source = "auto",
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    years: int = 5,
    fred_api_key: str | None = None,
) -> pd.Series:
    """Fetch a historical time series from FRED or Yahoo Finance.

    Args:
        ticker: FRED series ID (e.g. 'DCOILWTICO') or yfinance symbol (e.g. 'WMT').
        source: 'fred', 'yfinance', or 'auto' (tries FRED first, falls back).
        start: Start date (default: `years` before `end`).
        end: End date (default: today).
        years: How many years of history to pull when start is not specified.
        fred_api_key: FRED API key. Also read from env var FRED_API_KEY.

    Returns:
        pd.Series with DatetimeIndex, forward-filled to remove weekday gaps.
    """
    end_dt = pd.Timestamp(end) if end else pd.Timestamp.today()
    start_dt = pd.Timestamp(start) if start else end_dt - timedelta(days=365 * years)

    if source == "fred" or (source == "auto" and _looks_like_fred(ticker)):
        return _pull_fred(ticker, start_dt, end_dt, fred_api_key)

    if source == "yfinance" or (source == "auto" and not _looks_like_fred(ticker)):
        return _pull_yfinance(ticker, start_dt, end_dt)

    raise ValueError(f"Unknown source: {source!r}")


def _looks_like_fred(ticker: str) -> bool:
    """FRED tickers are uppercase alphanumeric (letters and digits only), often long codes."""
    return (
        ticker.isalnum()
        and ticker.isupper()
        and len(ticker) > 4
    )


def _pull_fred(
    ticker: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    api_key: str | None,
) -> pd.Series:
    import os

    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        raise EnvironmentError(
            "FRED API key required. Pass fred_api_key= or set FRED_API_KEY env var. "
            "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
        )

    try:
        from fredapi import Fred  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "fredapi is not installed. Run: pip install 'mimic-forecast[data]'"
        ) from e

    fred = Fred(api_key=key)
    logger.info("Fetching FRED series '%s' from %s to %s…", ticker, start.date(), end.date())
    raw = fred.get_series(ticker, observation_start=start, observation_end=end)
    series = raw.dropna().rename(ticker)
    series.index = pd.to_datetime(series.index)
    logger.info("Got %d observations for '%s'.", len(series), ticker)
    return series


def _pull_yfinance(
    ticker: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    try:
        import yfinance as yf  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "yfinance is not installed. Run: pip install 'mimic-forecast[data]'"
        ) from e

    logger.info("Fetching yfinance series '%s' from %s to %s…", ticker, start.date(), end.date())
    data = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if data.empty:
        raise ValueError(f"No data returned from yfinance for ticker '{ticker}'.")

    series = data["Close"].squeeze().rename(ticker)
    series.index = pd.to_datetime(series.index)
    series = series.dropna()
    logger.info("Got %d observations for '%s'.", len(series), ticker)
    return series
