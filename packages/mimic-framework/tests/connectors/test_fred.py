"""Tests for the FRED connector — Plan §4.1."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mimic.framework.signal.sources.fred import FREDConnector
from mimic.framework.signal.sources.fred._transport import FixtureTransport

_FIXTURES = Path(__file__).parent / "fixtures" / "fred"


@pytest.fixture
def connector():
    return FREDConnector(transport=FixtureTransport(_FIXTURES))


def test_fetch_emits_canonical_records(connector):
    out = list(connector.fetch("DGS10", since=datetime(2024, 1, 1), until=datetime(2024, 2, 28)))
    assert len(out) == 4
    assert all(r["series_id"] == "DGS10" for r in out)
    assert all(r["iri"].startswith("https://fred.stlouisfed.org/series/DGS10#") for r in out)


def test_fetch_handles_missing_value_marker(connector):
    out = list(connector.fetch("DGS10", since=datetime(2024, 1, 1), until=datetime(2024, 2, 28)))
    missing = [r for r in out if r["value"] is None]
    assert len(missing) == 1


def test_fetch_window_filters(connector):
    out = list(connector.fetch("DGS10", since=datetime(2024, 1, 4), until=datetime(2024, 1, 31)))
    assert len(out) == 1
    assert out[0]["date"] == "2024-01-04T00:00:00"


def test_constructor_requires_key_or_transport(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FRED_API_KEY"):
        FREDConnector()


def test_schema_has_value_nullable(connector):
    s = connector.schema()
    assert s["properties"]["value"]["type"] == ["number", "null"]


def test_rate_limit_policy_documented(connector):
    pol = connector.rate_limit_policy()
    assert pol.requests_per_second == 20.0
    assert "FRED" in pol.notes
