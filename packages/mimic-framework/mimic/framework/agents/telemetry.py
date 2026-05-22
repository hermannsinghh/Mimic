"""Decision-emission telemetry — closes the audit-grade gap in Plan §12.

Every Prefab.run() that emits a Decision wraps it in a `mimic.decision` span
carrying:

    {
      agent_did, prefab_name, tier_entry,
      action_type, confidence, model_fingerprint,
      policy_version,                # OPA bundle digest at decision time
      instrument_iri,
    }

Without this span you cannot prove, post-hoc, that a given Decision was
governed by a specific policy bundle. Per Plan §12: "a run is NOT audit-grade
unless every decision has a verified policy_version."

The OTEL import is optional (same pattern as routing/telemetry.py).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

try:
    from opentelemetry import trace as _otel_trace  # type: ignore[import-not-found]

    _TRACER = _otel_trace.get_tracer("mimic.framework.agents")
    HAS_OTEL = True
except ImportError:
    _TRACER = None
    HAS_OTEL = False


_SPAN_NAME = "mimic.decision"


class _NoopSpan:
    def set_attribute(self, key: str, value: Any) -> None: ...
    def set_attributes(self, attrs: dict[str, Any]) -> None: ...
    def record_exception(self, exc: BaseException) -> None: ...
    def set_status(self, *_args, **_kwargs) -> None: ...


REQUIRED_ATTRS = (
    "agent_did", "prefab_name", "tier_entry",
    "action_type", "confidence", "model_fingerprint",
    "policy_version", "instrument_iri",
)


def build_decision_attrs(
    *,
    agent_did: str,
    prefab_name: str,
    tier_entry: str,
    action_type: str,
    confidence: float,
    model_fingerprint: str,
    policy_version: str,
    instrument_iri: str,
) -> dict[str, Any]:
    return {
        "agent_did": agent_did,
        "prefab_name": prefab_name,
        "tier_entry": tier_entry,
        "action_type": action_type,
        "confidence": float(confidence),
        "model_fingerprint": model_fingerprint,
        "policy_version": policy_version,
        "instrument_iri": instrument_iri,
    }


@contextmanager
def decision_span(initial_attrs: dict[str, Any]) -> Iterator[Any]:
    if not HAS_OTEL:
        yield _NoopSpan()
        return

    with _TRACER.start_as_current_span(_SPAN_NAME) as span:  # pragma: no cover
        span.set_attributes(initial_attrs)
        try:
            yield span
        except BaseException as e:
            span.record_exception(e)
            span.set_status(_otel_trace.Status(_otel_trace.StatusCode.ERROR))
            raise
