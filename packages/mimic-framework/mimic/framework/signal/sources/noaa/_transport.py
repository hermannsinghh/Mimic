"""NOAA transport — DefaultTransport hits live API, FixtureTransport replays."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class DefaultTransport:
    def events(self, query, *, since, until):  # pragma: no cover - live HTTP
        raise NotImplementedError("DefaultTransport.events is the live NOAA NCEI client; use FixtureTransport in CI")

    def ping(self) -> int:  # pragma: no cover
        raise NotImplementedError("DefaultTransport.ping calls live NOAA; mock in tests")


class FixtureTransport:
    def __init__(self, fixture_dir: str | Path) -> None:
        self.fixture_dir = Path(fixture_dir)
        if not self.fixture_dir.is_dir():
            raise FileNotFoundError(f"no fixture dir: {fixture_dir}")

    def events(self, query, *, since, until):
        cassette = self.fixture_dir / f"{query}.json"
        if not cassette.exists():
            return iter([])
        records = json.loads(cassette.read_text())
        for r in records:
            occurred = datetime.fromisoformat(r["occurred_at"])
            if since <= occurred <= until:
                yield r

    def ping(self) -> int:
        return 2
