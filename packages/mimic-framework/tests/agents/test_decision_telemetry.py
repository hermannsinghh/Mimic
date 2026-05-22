"""Tests for the decision-emission span — closes Plan §12 audit gap."""
from __future__ import annotations

from mimic.framework.agents.telemetry import (
    HAS_OTEL,
    REQUIRED_ATTRS,
    build_decision_attrs,
    decision_span,
)


def test_required_attrs_include_policy_version():
    assert "policy_version" in REQUIRED_ATTRS


def test_build_decision_attrs_has_every_required_key():
    attrs = build_decision_attrs(
        agent_did="did:web:svb",
        prefab_name="BankTreasuryALM",
        tier_entry="T1",
        action_type="hedge",
        confidence=0.85,
        model_fingerprint="a" * 64,
        policy_version="b" * 64,
        instrument_iri="https://example.com/svb/treasury-action",
    )
    for k in REQUIRED_ATTRS:
        assert k in attrs


def test_decision_span_is_noop_when_otel_missing():
    with decision_span({"agent_did": "did:web:test"}) as span:
        span.set_attribute("x", 1)
        span.set_attributes({"y": "z"})


def test_decision_span_propagates_exceptions():
    import pytest
    with pytest.raises(RuntimeError):
        with decision_span({"agent_did": "did:web:test"}):
            raise RuntimeError("oops")
