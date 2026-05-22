"""GDELT transport — DefaultTransport hits live API, FixtureTransport replays."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class DefaultTransport:
    def articles(self, query, *, since, until):  # pragma: no cover - live HTTP
        raise NotImplementedError("DefaultTransport.articles is the live GDELT DOC API; use FixtureTransport in CI")

    def ping(self) -> int:  # pragma: no cover
        raise NotImplementedError("DefaultTransport.ping calls live GDELT; mock in tests")


class FixtureTransport:
    def __init__(self, fixture_dir: str | Path) -> None:
        self.fixture_dir = Path(fixture_dir)
        if not self.fixture_dir.is_dir():
            raise FileNotFoundError(f"no fixture dir: {fixture_dir}")

    def articles(self, query, *, since, until):
        cassette = self.fixture_dir / f"{query}.json"
        if not cassette.exists():
            return iter([])
        records = json.loads(cassette.read_text())
        for r in records:
            published = datetime.fromisoformat(r["published_at"])
            if since <= published <= until:
                yield r

    def ping(self) -> int:
        return 3
