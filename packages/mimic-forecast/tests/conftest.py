"""Shared fixtures for all tests."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def daily_series() -> pd.Series:
    """500 days of synthetic daily data (random walk)."""
    rng = np.random.default_rng(42)
    n = 500
    prices = 100 + np.cumsum(rng.normal(0, 1, n))
    index = pd.date_range("2022-01-01", periods=n, freq="D")
    return pd.Series(prices, index=index, name="synthetic")


@pytest.fixture
def monthly_series() -> pd.Series:
    """60 months of synthetic monthly data."""
    rng = np.random.default_rng(42)
    n = 60
    values = 3.0 + np.cumsum(rng.normal(0, 0.1, n))
    index = pd.date_range("2019-01-01", periods=n, freq="MS")
    return pd.Series(values, index=index, name="synthetic_monthly")


@pytest.fixture
def short_series() -> pd.Series:
    """Short series (10 points) to test minimum-length guards."""
    index = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.Series(range(10), index=index, dtype=float, name="short")
