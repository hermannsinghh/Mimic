"""Tests for the SEC EDGAR connector — Plan §4.1.

No live HTTP — fixture cassettes only.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mimic.framework.signal.sources.sec_edgar import SECEdgarConnector
from mimic.framework.signal.sources.sec_edgar._transport import FixtureTransport

_FIXTURES = Path(__file__).parent / "fixtures" / "sec_edgar"


@pytest.fixture
def connector():
    return SECEdgarConnector(transport=FixtureTransport(_FIXTURES))


def test_fetch_returns_filings_in_window(connector):
    records = list(connector.fetch("AAPL", since=datetime(2024, 1, 1), until=datetime(2024, 12, 31)))
    assert len(records) == 2  # SC 13D filtered out
    assert all(r["cik"] == "0000320193" for r in records)
    assert {r["form"] for r in records} == {"10-K", "10-Q"}


def test_fetch_filters_to_supported_form_types(connector):
    records = list(connector.fetch("AAPL", since=datetime(2024, 9, 1), until=datetime(2024, 9, 30)))
    assert records == []  # only the SC 13D falls in this window


def test_fetch_window_excludes_out_of_range(connector):
    records = list(connector.fetch("AAPL", since=datetime(2024, 10, 1), until=datetime(2024, 12, 31)))
    assert len(records) == 1
    assert records[0]["form"] == "10-K"


def test_fetch_unknown_ticker_returns_empty(connector):
    records = list(connector.fetch("XYZ", since=datetime(2024, 1, 1), until=datetime(2024, 12, 31)))
    assert records == []


def test_schema_describes_required_fields(connector):
    s = connector.schema()
    for f in ("iri", "cik", "form", "filed_at", "accession_no"):
        assert f in s["required"]


def test_health(connector):
    h = connector.health()
    assert h.ok is True
    assert h.latency_ms >= 0


def test_rate_limit_policy_is_real(connector):
    pol = connector.rate_limit_policy()
    assert pol.requests_per_second > 0
    assert pol.notes  # never empty
