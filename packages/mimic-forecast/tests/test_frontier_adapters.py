"""Tests for the 2026-frontier adapter scaffolds (FC-01/02/03)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mimic_forecast import TimerS1Adapter, TiRexAdapter, Toto2Adapter
from mimic_forecast.base import ForecasterAdapter


def _series(n: int = 64):
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.Series(np.linspace(100, 110, n), index=idx)


@pytest.mark.parametrize("cls,name", [
    (Toto2Adapter,  "toto-open-base-1.0"),
    (TimerS1Adapter, "timer-s1"),
    (TiRexAdapter,   "tirex"),
])
def test_adapter_implements_forecaster_contract(cls, name):
    adapter = cls()
    assert isinstance(adapter, ForecasterAdapter)
    assert adapter.name == name


@pytest.mark.parametrize("cls", [Toto2Adapter, TimerS1Adapter, TiRexAdapter])
def test_adapter_raises_install_message_until_dep_present(cls):
    adapter = cls()
    with pytest.raises((ImportError, NotImplementedError)) as exc:
        adapter.forecast(_series(), horizon=5)
    msg = str(exc.value).lower()
    assert "install" in msg or "implemented" in msg


@pytest.mark.parametrize("cls", [Toto2Adapter, TimerS1Adapter, TiRexAdapter])
def test_adapter_validates_series_length(cls):
    adapter = cls()
    with pytest.raises(ValueError, match="at least"):
        adapter.forecast(_series(n=4), horizon=5)
