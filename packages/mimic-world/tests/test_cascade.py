"""Tests for CascadeEngine using MockTwins (no API calls)."""

from __future__ import annotations

import pytest

from mimic_world.cascade import CascadeEngine
from mimic_world.result import WorldResult
from mimic_world.world import World
from tests.conftest import MockTwin


def build_world(*tickers: str) -> World:
    world = World()
    for ticker in tickers:
        world.add_twin(MockTwin(ticker=ticker, profile={
            "name": ticker,
            "sector": "technology",
            "annual_revenue_bn": 50,
            "key_inputs": ["semiconductors"],
            "key_risks": ["supply_chain"],
        }))
    return world


class TestCascadeEngineBasic:
    def test_single_step_returns_world_result(self, custom_scenario) -> None:
        world = build_world("AAA", "BBB")
        result = world.run(custom_scenario, time_steps=[1])
        assert isinstance(result, WorldResult)

    def test_cascade_timeline_has_correct_steps(self, custom_scenario) -> None:
        world = build_world("AAA", "BBB")
        result = world.run(custom_scenario, time_steps=[1, 7])
        assert len(result.cascade_timeline) == 2
        assert result.cascade_timeline[0].step == 1
        assert result.cascade_timeline[1].step == 7

    def test_decisions_made_for_affected_twins(self, custom_scenario) -> None:
        world = build_world("AAA", "BBB")
        result = world.run(custom_scenario, time_steps=[1])
        step = result.cascade_timeline[0]
        assert len(step.decisions) >= 1

    def test_mock_twins_called(self, custom_scenario) -> None:
        world = build_world("AAA", "BBB")
        result = world.run(custom_scenario, time_steps=[1])
        # At least one twin was called
        total_decisions = sum(len(s.decisions) for s in result.cascade_timeline)
        assert total_decisions >= 1

    def test_system_stability_is_valid(self, custom_scenario) -> None:
        world = build_world("AAA", "BBB")
        result = world.run(custom_scenario, time_steps=[1, 7])
        assert result.system_stability in ("stabilizing", "escalating", "bifurcating", "unknown")

    def test_financial_impacts_computed(self, custom_scenario) -> None:
        world = build_world("AAA", "BBB")
        result = world.run(custom_scenario, time_steps=[1])
        assert isinstance(result.financial_impacts, dict)
        for ticker, impact in result.financial_impacts.items():
            assert hasattr(impact, "low")
            assert hasattr(impact, "mid")
            assert hasattr(impact, "high")

    def test_most_affected_is_ordered_by_magnitude(self, custom_scenario) -> None:
        world = build_world("AAA", "BBB")
        result = world.run(custom_scenario, time_steps=[1])
        # most_affected should be sorted descending by |mid|
        mids = [abs(result.financial_impacts[t].mid) for t in result.most_affected]
        assert mids == sorted(mids, reverse=True)

    def test_who_acted_first_is_subset_of_twins(self, custom_scenario) -> None:
        world = build_world("AAA", "BBB")
        result = world.run(custom_scenario, time_steps=[1])
        for ticker in result.who_acted_first:
            assert ticker in world.twins


class TestCascadePropagation:
    def test_world_state_updates_from_twin_decisions(self, custom_scenario) -> None:
        world = build_world("AAA")
        result = world.run(custom_scenario, time_steps=[1])
        step = result.cascade_timeline[0]
        # MockTwin injects "aaa_decision_signal": -0.05 into world_state
        assert "aaa_decision_signal" in step.world_state

    def test_cascade_rules_apply(self) -> None:
        from mimic_world.scenario import CascadeRule, Scenario

        scenario = Scenario(
            id="cascade_test",
            title="Cascade Test",
            category="test",
            severity=0.5,
            duration_days=7,
            initial_shocks={"key_a": -0.40},
            affected_sectors=["technology"],
            cascade_rules=[
                CascadeRule(from_key="key_a", to_key="key_b", multiplier=0.5)
            ],
        )
        world = build_world("AAA")
        result = world.run(scenario, time_steps=[1])
        step = result.cascade_timeline[0]
        # key_b should appear due to cascade rule
        assert "key_b" in step.world_state
        assert step.world_state["key_b"] == pytest.approx(-0.40 * 0.5, abs=0.01)

    def test_second_order_effects_detected(self) -> None:
        from mimic_world.scenario import CascadeRule, Scenario

        scenario = Scenario(
            id="second_order_test",
            title="Second Order Test",
            category="test",
            severity=0.6,
            duration_days=14,
            initial_shocks={"primary_shock": -0.50},
            affected_sectors=["technology"],
            cascade_rules=[
                CascadeRule(from_key="primary_shock", to_key="secondary_effect", multiplier=0.3)
            ],
        )
        world = build_world("AAA", "BBB")
        result = world.run(scenario, time_steps=[1, 7])
        # secondary_effect emerges beyond primary_shock key
        assert any("secondary_effect" in e for e in result.second_order_effects)


class TestWorldResultExport:
    def test_export_json(self, custom_scenario) -> None:
        import json

        world = build_world("AAA")
        result = world.run(custom_scenario, time_steps=[1])
        exported = result.export("json")
        data = json.loads(exported)
        assert "scenario" in data
        assert "cascade_timeline" in data
        assert "system_stability" in data

    def test_export_unsupported_format_raises(self, custom_scenario) -> None:
        world = build_world("AAA")
        result = world.run(custom_scenario, time_steps=[1])
        with pytest.raises(ValueError, match="Unsupported"):
            result.export("csv")

    def test_compare_two_results(self, custom_scenario) -> None:
        world = build_world("AAA")
        result_a = world.run(custom_scenario, time_steps=[1])
        result_b = world.run(custom_scenario, time_steps=[1])
        comparison = result_a.compare(result_b)
        assert "scenario_a" in comparison
        assert "scenario_b" in comparison
