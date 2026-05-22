"""NOAA client — Plan §4.1.

Emits weather and storm-event records (NHC active-storm feed + Storm Events
Database) as canonical Event-shaped dicts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from .._base import Connector, HealthResult, RateLimitPolicy

EVENT_KINDS = frozenset({"hurricane", "tornado", "flood", "wildfire", "extreme_cold"})


class NOAAConnector(Connector):
    source_name = "noaa"
    tier = "T1"

    def __init__(self, *, transport=None) -> None:
        from ._transport import DefaultTransport
        self._transport = transport if transport is not None else DefaultTransport()

    def fetch(self, query: str, since: datetime, until: datetime) -> Iterator[dict]:
        """Yield storm events matching `query` (basin or US state) in window.

        Each record::
            {
              "iri": "https://www.ncei.noaa.gov/.../event/<id>",
              "event_kind": "hurricane" | "tornado" | ...,
              "occurred_at": "2024-09-26T...",
              "intensity": "cat_4" | "ef_3" | ...,
              "affected_region": "FL" | "Atlantic" | ...,
            }
        """
        for raw in self._transport.events(query, since=since, until=until):
            kind = raw.get("event_kind")
            if kind not in EVENT_KINDS:
                continue
            yield {
                "iri": raw["event_url"],
                "event_kind": kind,
                "occurred_at": raw["occurred_at"],
                "intensity": raw.get("intensity", ""),
                "affected_region": raw.get("region", ""),
            }

    def schema(self) -> dict:
        return {
            "type": "object",
            "required": ["iri", "event_kind", "occurred_at"],
            "properties": {
                "iri": {"type": "string", "format": "uri"},
                "event_kind": {"type": "string", "enum": sorted(EVENT_KINDS)},
                "occurred_at": {"type": "string", "format": "date-time"},
                "intensity": {"type": "string"},
                "affected_region": {"type": "string"},
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
            requests_per_second=5.0,
            burst=10,
            notes="NOAA NCEI public API; no documented hard cap, self-throttle",
        )
