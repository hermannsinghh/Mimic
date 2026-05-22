"""
Shared test fixtures.

Tests that require the Anthropic API (Twin.simulate) are skipped unless
ANTHROPIC_API_KEY is set. Unit tests of graph, macro, scenario, and
result classes use mock twins and run without any API access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from mimic_world.result import Decision
from mimic_world.scenario import Scenario


@dataclass
class MockTwin:
    """Deterministic twin that returns fixed decisions without calling any API."""

    ticker: str
    profile: dict = field(default_factory=lambda: {
        "name": "Mock Corp",
        "sector": "technology",
        "annual_revenue_bn": 100,
        "key_inputs": ["semiconductors"],
        "key_risks": ["supply_chain"],
    })
    _call_count: int = field(default=0, repr=False)

    def simulate(self, world_state: dict, step: int = 1) -> Decision:
        self._call_count += 1
        return Decision(
            ticker=self.ticker,
            step=step,
            actions=[f"Mock action 1 for {self.ticker}", "Mock action 2"],
            reasoning=f"{self.ticker} responds deterministically at day {step}.",
            world_state_updates={f"{self.ticker.lower()}_decision_signal": -0.05},
            financial_impact={"revenue_impact_pct": -0.03, "severity": "medium"},
        )


@pytest.fixture
def mock_twin_a() -> MockTwin:
    return MockTwin(ticker="AAA")


@pytest.fixture
def mock_twin_b() -> MockTwin:
    return MockTwin(ticker="BBB")


@pytest.fixture
def taiwan_scenario() -> Scenario:
    return Scenario.from_library("taiwan_strait_closure_30d")


@pytest.fixture
def custom_scenario() -> Scenario:
    return Scenario(
        id="test_scenario",
        title="Test port closure",
        category="supply_chain",
        severity=0.5,
        duration_days=14,
        initial_shocks={"shipping_capacity": -0.30, "oil_price": 0.10},
        affected_sectors=["technology", "logistics"],
    )
