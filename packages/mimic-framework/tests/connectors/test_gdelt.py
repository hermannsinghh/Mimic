"""Tests for the GDELT connector — Plan §4.1."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mimic.framework.signal.sources.gdelt import GDELTConnector
from mimic.framework.signal.sources.gdelt._transport import FixtureTransport

_FIXTURES = Path(__file__).parent / "fixtures" / "gdelt"


@pytest.fixture
def connector():
    return GDELTConnector(transport=FixtureTransport(_FIXTURES))


def test_fetch_emits_articles(connector):
    records = list(connector.fetch("svb_collapse",
                                   since=datetime(2023, 3, 1),
                                   until=datetime(2023, 3, 31)))
    assert len(records) == 2
    assert all("tone" in r for r in records)


def test_fetch_window_filters(connector):
    records = list(connector.fetch("svb_collapse",
                                   since=datetime(2023, 3, 10),
                                   until=datetime(2023, 3, 31)))
    assert len(records) == 1


def test_themes_passthrough(connector):
    records = list(connector.fetch("svb_collapse",
                                   since=datetime(2023, 3, 1),
                                   until=datetime(2023, 3, 31)))
    assert "FIN" in records[0]["themes"]


def test_schema_includes_themes_array(connector):
    s = connector.schema()
    assert s["properties"]["themes"]["type"] == "array"


def test_health(connector):
    assert connector.health().ok is True


def test_rate_limit_policy_documented(connector):
    p = connector.rate_limit_policy()
    assert p.requests_per_second == 2.0
    assert "GDELT" in p.notes
