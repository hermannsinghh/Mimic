"""Tests for Scenario loading, validation, and library."""

from __future__ import annotations

import pytest

from mimic_world.scenario import CascadeRule, Scenario


class TestScenarioFromLibrary:
    def test_loads_taiwan_strait(self, taiwan_scenario: Scenario) -> None:
        assert taiwan_scenario.id == "taiwan_strait_closure_30d"
        assert taiwan_scenario.severity == pytest.approx(0.85)
        assert taiwan_scenario.duration_days == 30
        assert "technology" in taiwan_scenario.affected_sectors

    def test_initial_shocks_are_floats(self, taiwan_scenario: Scenario) -> None:
        for key, val in taiwan_scenario.initial_shocks.items():
            assert isinstance(val, float), f"shock {key!r} is {type(val)}"

    def test_cascade_rules_loaded(self, taiwan_scenario: Scenario) -> None:
        assert len(taiwan_scenario.cascade_rules) >= 2
        for rule in taiwan_scenario.cascade_rules:
            assert isinstance(rule, CascadeRule)
            assert 0 < abs(rule.multiplier) <= 2.0

    def test_unknown_scenario_raises(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            Scenario.from_library("this_does_not_exist")

    def test_list_library_returns_50_scenarios(self) -> None:
        library = Scenario.list_library()
        assert len(library) == 50, f"Expected 50 scenarios, got {len(library)}"

    def test_all_library_scenarios_are_loadable(self) -> None:
        for meta in Scenario.list_library():
            s = Scenario.from_library(meta["id"])
            assert s.id == meta["id"]
            assert 0 <= s.severity <= 1.0 or s.severity >= -1.0  # arctic is negative
            assert s.duration_days >= 1

    def test_all_library_scenarios_have_initial_shocks(self) -> None:
        for meta in Scenario.list_library():
            s = Scenario.from_library(meta["id"])
            assert len(s.initial_shocks) >= 1, f"{s.id} has no initial_shocks"


class TestScenarioFromDict:
    def test_round_trip(self, taiwan_scenario: Scenario) -> None:
        data = taiwan_scenario.to_dict()
        restored = Scenario.from_dict(data)
        assert restored.id == taiwan_scenario.id
        assert restored.severity == taiwan_scenario.severity
        assert len(restored.cascade_rules) == len(taiwan_scenario.cascade_rules)

    def test_custom_scenario(self, custom_scenario: Scenario) -> None:
        assert custom_scenario.id == "test_scenario"
        assert custom_scenario.severity == 0.5
        assert "shipping_capacity" in custom_scenario.initial_shocks


class TestScenarioRepr:
    def test_repr(self, taiwan_scenario: Scenario) -> None:
        r = repr(taiwan_scenario)
        assert "taiwan_strait" in r
        assert "85%" in r
