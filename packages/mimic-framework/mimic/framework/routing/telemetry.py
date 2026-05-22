"""Routing telemetry — Plan §6.3.

Every cascade.route() call emits an OTEL span `mimic.route` with attributes::

    {tier, provider, model, input_tokens, output_tokens,
     cost_usd, confidence, escalated_to}

`opentelemetry` is an optional dependency. When it's not installed, the
context manager below is a no-op — code behaves identically, just without
telemetry. Install `opentelemetry-sdk` and configure an exporter to emit
spans to Tempo/Honeycomb (Plan §4.3).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

try:
    from opentelemetry import trace as _otel_trace  # type: ignore[import-not-found]

    _TRACER = _otel_trace.get_tracer("mimic.framework.routing")
    HAS_OTEL = True
except ImportError:
    _TRACER = None
    HAS_OTEL = False


_SPAN_NAME = "mimic.route"


class _NoopSpan:
    def set_attribute(self, key: str, value: Any) -> None: ...
    def set_attributes(self, attrs: dict[str, Any]) -> None: ...
    def record_exception(self, exc: BaseException) -> None: ...
    def set_status(self, *_args, **_kwargs) -> None: ...


@contextmanager
def route_span(initial_attrs: dict[str, Any]) -> Iterator[Any]:
    """Context manager yielding an OTEL span (or no-op shim).

    Always sets attributes from `initial_attrs` at entry; the caller is
    responsible for `set_attributes` updates as the cascade progresses
    (e.g. when an escalation happens).
    """
    if not HAS_OTEL:
        yield _NoopSpan()
        return

    with _TRACER.start_as_current_span(_SPAN_NAME) as span:  # pragma: no cover - exercised when otel installed
        span.set_attributes(initial_attrs)
        try:
            yield span
        except BaseException as e:
            span.record_exception(e)
            span.set_status(_otel_trace.Status(_otel_trace.StatusCode.ERROR))
            raise


REQUIRED_ATTRS = (
    "tier", "provider", "model",
    "input_tokens", "output_tokens",
    "cost_usd", "confidence", "escalated_to",
)


def build_attrs(
    *,
    tier: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    confidence: float,
    escalated_to: str | None,
) -> dict[str, Any]:
    """Build the canonical attribute set for a `mimic.route` span."""
    return {
        "tier": tier,
        "provider": provider,
        "model": model,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "cost_usd": float(cost_usd),
        "confidence": float(confidence),
        "escalated_to": escalated_to or "",
    }
