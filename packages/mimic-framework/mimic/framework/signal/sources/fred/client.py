"""FRED client — Plan §4.1.

API key resolved at runtime via env var FRED_API_KEY. Never hardcoded;
never logged.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Iterator

from .._base import Connector, HealthResult, RateLimitPolicy


class FREDConnector(Connector):
    source_name = "fred"
    tier = "T0"

    def __init__(self, *, transport=None, api_key: str | None = None) -> None:
        from ._transport import DefaultTransport
        resolved = api_key or os.environ.get("FRED_API_KEY")
        if transport is None and not resolved:
            raise RuntimeError(
                "FRED_API_KEY not set. Either set the env var or pass api_key=, "
                "or inject a FixtureTransport for tests."
            )
        self._transport = transport if transport is not None else DefaultTransport(api_key=resolved)

    def fetch(self, query: str, since: datetime, until: datetime) -> Iterator[dict]:
        """Yield observations for FRED series id `query` in the time window.

        Each record::
            {
              "iri": "https://fred.stlouisfed.org/series/<id>#<date>",
              "series_id": "DGS10",
              "date": "2024-01-15",
              "value": 4.05,
            }
        """
        for raw in self._transport.observations(query, since=since, until=until):
            yield {
                "iri": f"https://fred.stlouisfed.org/series/{query}#{raw['date']}",
                "series_id": query,
                "date": raw["date"],
                "value": float(raw["value"]) if raw["value"] not in (None, ".") else None,
            }

    def schema(self) -> dict:
        return {
            "type": "object",
            "required": ["iri", "series_id", "date"],
            "properties": {
                "iri": {"type": "string", "format": "uri"},
                "series_id": {"type": "string"},
                "date": {"type": "string", "format": "date"},
                "value": {"type": ["number", "null"]},
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
            requests_per_second=20.0,
            burst=120,
            notes="FRED publishes 120 reqs/min; we cap at 20/s with burst=120",
        )
