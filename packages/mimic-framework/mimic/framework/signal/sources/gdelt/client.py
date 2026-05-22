"""GDELT client — Plan §4.1.

Emits news event records as candidates for the signal pipeline (F-10).
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from .._base import Connector, HealthResult, RateLimitPolicy


class GDELTConnector(Connector):
    source_name = "gdelt"
    tier = "T1"

    def __init__(self, *, transport=None) -> None:
        from ._transport import DefaultTransport
        self._transport = transport if transport is not None else DefaultTransport()

    def fetch(self, query: str, since: datetime, until: datetime) -> Iterator[dict]:
        """Yield news events matching `query` (keyword search) in the window.

        Each record::
            {
              "iri": "https://www.gdeltproject.org/.../article/<id>",
              "url": "https://...",
              "published_at": "2024-...",
              "source_country": "US",
              "tone": -3.5,         # GDELT tone score, -10 to 10
              "themes": ["FIN", "BANK", "ECON_BANKRUPTCY"],
            }
        """
        for raw in self._transport.articles(query, since=since, until=until):
            yield {
                "iri": raw["article_id"],
                "url": raw["url"],
                "published_at": raw["published_at"],
                "source_country": raw.get("source_country", ""),
                "tone": float(raw.get("tone", 0.0)),
                "themes": list(raw.get("themes", [])),
            }

    def schema(self) -> dict:
        return {
            "type": "object",
            "required": ["iri", "url", "published_at"],
            "properties": {
                "iri": {"type": "string", "format": "uri"},
                "url": {"type": "string", "format": "uri"},
                "published_at": {"type": "string", "format": "date-time"},
                "source_country": {"type": "string"},
                "tone": {"type": "number"},
                "themes": {"type": "array", "items": {"type": "string"}},
            },
        }

    def health(self) -> HealthResult:
        try:
            ms = self._transport.ping()
            return HealthResult(ok=True, latency_ms=ms)
        except Exception as e:  # pragma: no cover
            return HealthResult(ok=False, latency_ms=0, notes=str(e))

    def rate_limit_policy(self) -> RateLimitPolicy:
        return RateLimitPolicy(
            requests_per_second=2.0,
            burst=5,
            notes="GDELT 2.0 DOC API; self-throttle conservatively",
        )
