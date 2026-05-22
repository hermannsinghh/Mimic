"""LLM provider interface — Plan §4.2.

Every provider adapter exposes the same interface. Every call MUST emit
`model_fingerprint = sha256(provider|model|version|system_prompt|temperature|tool_schema)`.

Frozen-run mode (MIMIC_FROZEN_RUN=1) is enforced at the provider boundary:
cache miss raises FrozenRunCacheMiss — never silently re-call (Plan §7.3).
"""
from __future__ import annotations

import hashlib
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class FrozenRunCacheMiss(RuntimeError):
    """Raised when MIMIC_FROZEN_RUN=1 and no cached response exists."""


class BudgetExceeded(RuntimeError):
    """Raised when a workflow's max_cost_usd would be exceeded by the next call."""


class StructuredResponse(BaseModel):
    """The only shape a provider may return.

    `content` is JSON-validated against the caller's schema by the routing layer.
    """
    content: dict[str, Any]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    confidence: float
    model_fingerprint: str


def compute_model_fingerprint(
    *,
    provider: str,
    model: str,
    version: str,
    system_prompt: str,
    temperature: float,
    tool_schema: dict | None,
) -> str:
    """Plan §4.2: sha256(provider|model|version|system_prompt|temperature|tool_schema).

    Stable across runs; the same inputs always produce the same fingerprint, so
    cached responses can be keyed by fingerprint + sha256(messages).
    """
    import json

    tool_str = json.dumps(tool_schema, sort_keys=True, separators=(",", ":")) if tool_schema else ""
    payload = f"{provider}|{model}|{version}|{system_prompt}|{temperature:.6f}|{tool_str}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@runtime_checkable
class LLMProvider(Protocol):
    """All model provider adapters implement this."""

    provider_name: str
    model_name: str
    model_version: str

    def estimate_cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        """Cost estimate used by the routing layer to enforce the budget."""

    def complete(
        self,
        *,
        messages: list[dict],
        schema: dict | None,
        tools: list[dict] | None,
        temperature: float,
        seed: int | None,
        system_prompt: str = "",
    ) -> StructuredResponse:
        """Generate a structured response. Must emit `model_fingerprint`."""
