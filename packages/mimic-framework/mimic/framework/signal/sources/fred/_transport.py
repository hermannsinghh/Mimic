"""FRED transport — DefaultTransport hits live API, FixtureTransport replays."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterator


class DefaultTransport:
    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    def observations(self, series_id, *, since, until):  # pragma: no cover - live HTTP
        raise NotImplementedError(
            "DefaultTransport.observations is the live FRED client. "
            "Wire httpx + observations endpoint. Forbidden in CI — use FixtureTransport."
        )

    def ping(self) -> int:  # pragma: no cover - live HTTP
        raise NotImplementedError("DefaultTransport.ping calls live FRED; mock in tests")


class FixtureTransport:
    def __init__(self, fixture_dir: str | Path) -> None:
        self.fixture_dir = Path(fixture_dir)
        if not self.fixture_dir.is_dir():
            raise FileNotFoundError(f"no fixture dir: {fixture_dir}")

    def observations(self, series_id, *, since, until):
        cassette = self.fixture_dir / f"{series_id}.json"
        if not cassette.exists():
            return iter([])
        observations = json.loads(cassette.read_text())
        for o in observations:
            d = datetime.fromisoformat(o["date"])
            if since <= d <= until:
                yield o

    def ping(self) -> int:
        return 1
