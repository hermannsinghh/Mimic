"""Routing tests — Plan §6.

Covers:
- tier assignment by systemic_score
- model_fingerprint determinism
- cascade escalation T3 → T2 → T1
- budget guardrail raises BudgetExceeded
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from mimic.framework.routing import (
    BudgetExceeded,
    RoutingCascade,
    StructuredResponse,
    assign_tier,
    compute_model_fingerprint,
)


@dataclass
class _Entity:
    systemic_score: float


def test_assign_tier_thresholds():
    assert assign_tier(_Entity(0.95)) == "T1"
    assert assign_tier(_Entity(0.80)) == "T1"
    assert assign_tier(_Entity(0.79)) == "T2"
    assert assign_tier(_Entity(0.40)) == "T2"
    assert assign_tier(_Entity(0.39)) == "T3"
    assert assign_tier(_Entity(0.0)) == "T3"


def test_model_fingerprint_is_deterministic():
    a = compute_model_fingerprint(
        provider="anthropic", model="claude-opus-4-5", version="2026-01",
        system_prompt="you are a treaty pricer", temperature=0.0, tool_schema=None,
    )
    b = compute_model_fingerprint(
        provider="anthropic", model="claude-opus-4-5", version="2026-01",
        system_prompt="you are a treaty pricer", temperature=0.0, tool_schema=None,
    )
    assert a == b
    assert len(a) == 64  # sha256 hex


def test_model_fingerprint_changes_with_any_input():
    base = compute_model_fingerprint(
        provider="anthropic", model="claude-opus-4-5", version="2026-01",
        system_prompt="x", temperature=0.0, tool_schema=None,
    )
    variants = [
        dict(provider="openai", model="claude-opus-4-5", version="2026-01",
             system_prompt="x", temperature=0.0, tool_schema=None),
        dict(provider="anthropic", model="claude-sonnet-4-5", version="2026-01",
             system_prompt="x", temperature=0.0, tool_schema=None),
        dict(provider="anthropic", model="claude-opus-4-5", version="2026-02",
             system_prompt="x", temperature=0.0, tool_schema=None),
        dict(provider="anthropic", model="claude-opus-4-5", version="2026-01",
             system_prompt="y", temperature=0.0, tool_schema=None),
        dict(provider="anthropic", model="claude-opus-4-5", version="2026-01",
             system_prompt="x", temperature=0.5, tool_schema=None),
        dict(provider="anthropic", model="claude-opus-4-5", version="2026-01",
             system_prompt="x", temperature=0.0, tool_schema={"name": "tool"}),
    ]
    for v in variants:
        assert compute_model_fingerprint(**v) != base


class _FakeProvider:
    def __init__(self, name, cost, confidence, content):
        self.provider_name = name
        self.model_name = name
        self.model_version = "2026-01"
        self._cost = cost
        self._confidence = confidence
        self._content = content
        self.call_count = 0

    def estimate_cost_usd(self, input_tokens, output_tokens):
        return self._cost

    def complete(self, *, messages, schema, tools, temperature, seed, system_prompt=""):
        self.call_count += 1
        return StructuredResponse(
            content=self._content,
            input_tokens=100,
            output_tokens=50,
            cost_usd=self._cost,
            confidence=self._confidence,
            model_fingerprint=compute_model_fingerprint(
                provider=self.provider_name, model=self.model_name,
                version=self.model_version, system_prompt=system_prompt,
                temperature=temperature, tool_schema=None,
            ),
        )


def test_cascade_t3_confident_no_escalation():
    t3 = _FakeProvider("t3", 0.01, 0.9, {"action": "hold"})
    cascade = RoutingCascade(t3=t3, t2_a=None, t1=None, max_cost_usd=1.0)
    result = cascade.route(entry_tier="T3", messages=[])
    assert result.final_tier == "T3"
    assert result.escalated is False
    assert t3.call_count == 1


def test_cascade_t3_low_confidence_escalates_to_t2():
    t3 = _FakeProvider("t3", 0.01, 0.3, {"action": "hold"})
    t2 = _FakeProvider("t2-a", 0.05, 0.85, {"action": "sell"})
    cascade = RoutingCascade(t3=t3, t2_a=t2, t1=None, max_cost_usd=1.0)
    result = cascade.route(entry_tier="T3", messages=[])
    assert result.final_tier == "T2"
    assert result.escalated is True
    assert result.tiers_attempted == ("T3", "T2")


def test_cascade_t2_disagreement_adjudicates_to_t1():
    t2a = _FakeProvider("t2-a", 0.05, 0.8, {"action": "sell", "qty": 100})
    t2b = _FakeProvider("t2-b", 0.05, 0.8, {"action": "hold", "qty": 0})
    t1 = _FakeProvider("t1", 0.20, 0.95, {"action": "sell", "qty": 50})
    cascade = RoutingCascade(t3=None, t2_a=t2a, t2_b=t2b, t1=t1, max_cost_usd=1.0)
    result = cascade.route(entry_tier="T2", messages=[])
    assert result.final_tier == "T1"
    assert result.tiers_attempted == ("T2", "T2", "T1")


def test_cascade_budget_guardrail():
    t3 = _FakeProvider("t3", 0.50, 0.3, {"action": "hold"})  # too expensive to allow escalation
    t2 = _FakeProvider("t2", 0.60, 0.9, {"action": "hold"})
    cascade = RoutingCascade(t3=t3, t2_a=t2, t1=None, max_cost_usd=1.0)
    with pytest.raises(BudgetExceeded):
        cascade.route(entry_tier="T3", messages=[])


def test_cascade_rejects_non_positive_budget():
    with pytest.raises(ValueError):
        RoutingCascade(t3=None, t2_a=None, t1=None, max_cost_usd=0.0)
