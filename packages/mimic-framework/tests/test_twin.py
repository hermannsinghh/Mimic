"""Tests for the Twin class (using pre-built context — no external API calls)."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from mimic.core.twin import Twin, Decision


def test_twin_from_context(context):
    twin = Twin.from_context(context)
    assert twin.context.ticker == "WMT"


def test_twin_repr(context):
    twin = Twin.from_context(context)
    assert "WMT" in repr(twin)
    assert "Walmart" in repr(twin)


def test_twin_simulate_calls_orchestrator(context):
    twin = Twin.from_context(context)

    mock_decision = Decision(
        ticker="WMT",
        event="test event",
        immediate_action_0_24h="Activate backup suppliers",
        short_term_action_1_7d="Increase safety stock",
        medium_term_action_8_30d="Negotiate new contracts",
        financial_impact_low=-500.0,
        financial_impact_mid=-1_000.0,
        financial_impact_high=-2_000.0,
        confidence=0.72,
        reasoning="Based on supply chain exposure...",
        competitive_response_likely=["Costco: similar buffer builds"],
        secondary_risks_created=["Inventory overstock if shock subsides"],
        decision_constraints_hit=[],
        model_used="gpt-4o",
    )

    with patch("mimic.core.orchestrator.run_orchestrator", return_value=mock_decision):
        result = twin.simulate("test event", severity=0.7)

    assert isinstance(result, Decision)
    assert result.ticker == "WMT"
    assert result.financial_impact_mid == -1_000.0


def test_decision_pretty_output(context):
    decision = Decision(
        ticker="WMT",
        event="port closure",
        immediate_action_0_24h="Activate backup suppliers",
        short_term_action_1_7d="Build buffer stock",
        medium_term_action_8_30d="Renegotiate contracts",
        financial_impact_low=-300.0,
        financial_impact_mid=-800.0,
        financial_impact_high=-1_500.0,
        confidence=0.65,
        reasoning="WMT has high China exposure...",
        competitive_response_likely=["Costco builds buffer"],
        secondary_risks_created=["Overstock risk"],
        decision_constraints_hit=["Limited capex budget"],
    )
    pretty = decision.pretty()
    assert "WMT" in pretty
    assert "port closure" in pretty
    assert "$-800" in pretty
    assert "65%" in pretty


def test_twin_benchmark(context):
    twin = Twin.from_context(context)

    mock_decision = Decision(
        ticker="WMT",
        event="tariff shock",
        immediate_action_0_24h="Review sourcing",
        short_term_action_1_7d="Adjust pricing",
        medium_term_action_8_30d="Shift suppliers",
        financial_impact_low=-100.0,
        financial_impact_mid=-300.0,
        financial_impact_high=-600.0,
        confidence=0.5,
        reasoning="Tariff impact analysis.",
        competitive_response_likely=[],
        secondary_risks_created=[],
        decision_constraints_hit=[],
    )

    events = [
        {"description": "tariff shock", "date": "2024-01-01", "ground_truth_response": ""},
    ]

    with patch("mimic.core.orchestrator.run_orchestrator", return_value=mock_decision):
        results = twin.benchmark(events)

    assert len(results) == 1
    assert results[0]["event"] == "tariff shock"
    assert results[0]["fidelity_score"] is None
