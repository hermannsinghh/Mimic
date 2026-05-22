"""Tests for data/series.py — mock network calls."""

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch


def _make_fake_series(n=500):
    index = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.Series(range(n), index=index, dtype=float, name="FAKE")


def test_pull_series_yfinance_success():
    fake = _make_fake_series()
    fake_df = pd.DataFrame({"Close": fake})

    with patch("yfinance.download", return_value=fake_df):
        from mimic_forecast.data.series import _pull_yfinance
        result = _pull_yfinance("FAKE", fake.index[0], fake.index[-1])

    assert isinstance(result, pd.Series)
    assert isinstance(result.index, pd.DatetimeIndex)
    assert len(result) == len(fake)


def test_pull_series_yfinance_empty_raises():
    empty_df = pd.DataFrame()
    with patch("yfinance.download", return_value=empty_df):
        from mimic_forecast.data.series import _pull_yfinance
        with pytest.raises(ValueError, match="No data returned"):
            _pull_yfinance("NOTREAL", pd.Timestamp("2020-01-01"), pd.Timestamp("2024-01-01"))


def test_pull_series_fred_missing_key_raises():
    from mimic_forecast.data.series import _pull_fred
    import os
    # Ensure env var is unset
    env = {k: v for k, v in os.environ.items() if k != "FRED_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(EnvironmentError, match="FRED API key"):
            _pull_fred("FEDFUNDS", pd.Timestamp("2020-01-01"), pd.Timestamp("2024-01-01"), None)


def test_pull_series_fred_success():
    fake = _make_fake_series(100)
    mock_fred = MagicMock()
    mock_fred.get_series.return_value = fake

    with patch("fredapi.Fred", return_value=mock_fred):
        from mimic_forecast.data.series import _pull_fred
        result = _pull_fred(
            "FEDFUNDS",
            pd.Timestamp("2020-01-01"),
            pd.Timestamp("2024-01-01"),
            api_key="fake_key",
        )

    assert isinstance(result, pd.Series)


def test_looks_like_fred():
    from mimic_forecast.data.series import _looks_like_fred
    assert _looks_like_fred("DCOILWTICO")
    assert _looks_like_fred("FEDFUNDS")
    assert not _looks_like_fred("WMT")
    assert not _looks_like_fred("^GSPC")
