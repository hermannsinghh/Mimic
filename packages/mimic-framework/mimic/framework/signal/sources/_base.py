"""Shared connector base — Plan §4.1.

Every connector under signal/sources/<name>/ implements:
    fetch(query, since, until) -> Iterator[CanonicalRecord]
    schema() -> dict
    health() -> dict
    rate_limit_policy() -> RateLimitPolicy

Tests live alongside the connector and use VCR-style fixtures — no live HTTP
calls in CI.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator


@dataclass(frozen=True)
class RateLimitPolicy:
    requests_per_second: float
    burst: int = 1
    notes: str = ""


@dataclass(frozen=True)
class HealthResult:
    ok: bool
    latency_ms: int
    errors_24h: int = 0
    notes: str = ""


class Connector(ABC):
    """Base interface every connector must implement."""

    source_name: str  # e.g. "sec_edgar"
    tier: str         # "T0" | "T1" | "T2"

    @abstractmethod
    def fetch(self, query: str, since: datetime, until: datetime) -> Iterator[dict]:
        """Yield canonical records for the query in the time window."""

    @abstractmethod
    def schema(self) -> dict:
        """JSON-Schema-ish description of the record shape yielded by fetch()."""

    @abstractmethod
    def health(self) -> HealthResult:
        """Cheap probe; safe to call on every workflow start (<=500ms p99)."""

    @abstractmethod
    def rate_limit_policy(self) -> RateLimitPolicy:
        """Real limit, not None — conservative 1 req/sec default for unknowns."""
