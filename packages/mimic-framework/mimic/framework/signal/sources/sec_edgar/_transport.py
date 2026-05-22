"""SEC EDGAR HTTP transport.

Default transport calls live SEC endpoints; tests inject a FixtureTransport
that replays VCR-style JSON cassettes. No live HTTP calls in CI.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterator, Protocol


class _Transport(Protocol):
    def list_filings(self, cik_or_ticker: str, *, since: datetime, until: datetime) -> Iterator[dict]: ...
    def ping(self) -> int: ...


class DefaultTransport:
    """Live HTTP via httpx. NEVER instantiated in CI tests."""

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent

    def list_filings(self, cik_or_ticker, *, since, until):  # pragma: no cover - live HTTP
        raise NotImplementedError(
            "DefaultTransport.list_filings is the live SEC client. "
            "Wire httpx + json submissions API. Forbidden in CI — use FixtureTransport."
        )

    def ping(self) -> int:  # pragma: no cover - live HTTP
        raise NotImplementedError("DefaultTransport.ping calls live SEC; mock in tests")


class FixtureTransport:
    """VCR-style transport — loads cassettes from a fixture directory."""

    def __init__(self, fixture_dir: str | Path) -> None:
        self.fixture_dir = Path(fixture_dir)
        if not self.fixture_dir.is_dir():
            raise FileNotFoundError(f"no fixture dir: {fixture_dir}")

    def list_filings(self, cik_or_ticker, *, since, until):
        cassette = self.fixture_dir / f"{cik_or_ticker}.json"
        if not cassette.exists():
            return iter([])
        records = json.loads(cassette.read_text())
        for r in records:
            filed_at = datetime.fromisoformat(r["filed_at"])
            if since <= filed_at <= until:
                yield r

    def ping(self) -> int:
        return 1
