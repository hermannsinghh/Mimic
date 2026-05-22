"""Tests for the NOAA connector — Plan §4.1."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mimic.framework.signal.sources.noaa import NOAAConnector
from mimic.framework.signal.sources.noaa._transport import FixtureTransport

_FIXTURES = Path(__file__).parent / "fixtures" / "noaa"


@pytest.fixture
def connector():
    return NOAAConnector(transport=FixtureTransport(_FIXTURES))


def test_fetch_emits_storm_events(connector):
    records = list(connector.fetch("Atlantic",
                                   since=datetime(2024, 1, 1),
                                   until=datetime(2024, 12, 31)))
    assert len(records) == 2  # press_conference filtered out
    assert all(r["event_kind"] == "hurricane" for r in records)
    assert {r["intensity"] for r in records} == {"cat_4", "cat_5"}


def test_fetch_window(connector):
    records = list(connector.fetch("Atlantic",
                                   since=datetime(2024, 10, 1),
                                   until=datetime(2024, 10, 31)))
    assert len(records) == 1
    assert records[0]["intensity"] == "cat_5"


def test_schema_lists_event_kinds(connector):
    s = connector.schema()
    assert "hurricane" in s["properties"]["event_kind"]["enum"]
    assert "tornado" in s["properties"]["event_kind"]["enum"]


def test_health(connector):
    assert connector.health().ok is True


def test_rate_limit_policy_real(connector):
    p = connector.rate_limit_policy()
    assert p.requests_per_second > 0
