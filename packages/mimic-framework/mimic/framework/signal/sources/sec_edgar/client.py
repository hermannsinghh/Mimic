"""SEC EDGAR client — Plan §4.1.

Implementation note: this is the connector contract + scaffold. The HTTP
client lives in `_transport.py` and is mocked in tests via a VCR-style
fixture loader. Live HTTP in CI is forbidden per `.claude/skills/mimic-connector-author.md`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from .._base import Connector, HealthResult, RateLimitPolicy

FORM_TYPES = frozenset({"10-K", "10-Q", "8-K", "DEF 14A"})


class SECEdgarConnector(Connector):
    source_name = "sec_edgar"
    tier = "T0"

    def __init__(self, *, transport=None, user_agent: str = "Mimic dev@mimic.ai") -> None:
        from ._transport import DefaultTransport
        self._transport = transport if transport is not None else DefaultTransport(user_agent=user_agent)
        self._user_agent = user_agent

    def fetch(self, query: str, since: datetime, until: datetime) -> Iterator[dict]:
        """Yield filings matching `query` (CIK or ticker) in the time window.

        Each record is a dict shaped like::
            {
              "iri": "https://www.sec.gov/Archives/edgar/data/.../0001-...",
              "cik": "0000320193",
              "form": "10-K",
              "filed_at": "2024-11-01T00:00:00",
              "accession_no": "0000320193-24-000123",
              "summary": "...",
            }
        """
        for raw in self._transport.list_filings(query, since=since, until=until):
            form = raw.get("form")
            if form not in FORM_TYPES:
                continue
            yield {
                "iri": raw["filing_url"],
                "cik": raw["cik"],
                "form": form,
                "filed_at": raw["filed_at"],
                "accession_no": raw["accession_no"],
                "summary": raw.get("summary", ""),
            }

    def schema(self) -> dict:
        return {
            "type": "object",
            "required": ["iri", "cik", "form", "filed_at", "accession_no"],
            "properties": {
                "iri": {"type": "string", "format": "uri"},
                "cik": {"type": "string"},
                "form": {"type": "string", "enum": sorted(FORM_TYPES)},
                "filed_at": {"type": "string", "format": "date-time"},
                "accession_no": {"type": "string"},
                "summary": {"type": "string"},
            },
        }

    def health(self) -> HealthResult:
        try:
            ms = self._transport.ping()
            return HealthResult(ok=True, latency_ms=ms)
        except Exception as e:  # pragma: no cover - exercised when transport flaps
            return HealthResult(ok=False, latency_ms=0, notes=str(e))

    def rate_limit_policy(self) -> RateLimitPolicy:
        return RateLimitPolicy(
            requests_per_second=10.0,
            burst=10,
            notes="SEC EDGAR fair-access policy — UA header required",
        )
