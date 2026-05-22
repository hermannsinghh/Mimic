"""Routing telemetry tests — Plan §6.3."""
from __future__ import annotations

from mimic.framework.routing.telemetry import (
    HAS_OTEL,
    REQUIRED_ATTRS,
    build_attrs,
    route_span,
)


def test_build_attrs_has_all_required_keys():
    attrs = build_attrs(
        tier="T1", provider="anthropic", model="claude-opus-4-5",
        input_tokens=500, output_tokens=200, cost_usd=0.04,
        confidence=0.92, escalated_to=None,
    )
    for key in REQUIRED_ATTRS:
        assert key in attrs


def test_build_attrs_normalises_escalated_to_empty_string():
    attrs = build_attrs(
        tier="T3", provider="p", model="m",
        input_tokens=0, output_tokens=0, cost_usd=0.0,
        confidence=0.5, escalated_to=None,
    )
    assert attrs["escalated_to"] == ""


def test_route_span_is_noop_when_otel_missing():
    # If otel isn't installed, route_span yields a no-op shim that accepts attributes.
    with route_span({"entry_tier": "T3"}) as span:
        span.set_attribute("x", 1)
        span.set_attributes({"y": "z"})
    # If otel IS installed, this still passes — the real Span accepts these calls.


def test_route_span_passes_exceptions_through():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        with route_span({"entry_tier": "T1"}):
            raise ValueError("oops")
