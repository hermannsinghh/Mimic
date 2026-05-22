"""Tests for World class construction and snapshot."""

from __future__ import annotations

import pytest

from mimic_world.world import World
from tests.conftest import MockTwin


class TestWorldConstruction:
    def test_empty_world(self) -> None:
        world = World()
        assert world.twins == {}
        assert len(world.graph.edges) == 0

    def test_add_twin(self, mock_twin_a: MockTwin) -> None:
        world = World()
        world.add_twin(mock_twin_a)
        assert "AAA" in world.twins

    def test_add_multiple_twins(self, mock_twin_a: MockTwin, mock_twin_b: MockTwin) -> None:
        world = World()
        world.add_twin(mock_twin_a)
        world.add_twin(mock_twin_b)
        assert "AAA" in world.twins
        assert "BBB" in world.twins

    def test_connect_creates_edge(self, mock_twin_a: MockTwin, mock_twin_b: MockTwin) -> None:
        world = World()
        world.add_twin(mock_twin_a)
        world.add_twin(mock_twin_b)
        world.connect("AAA", "BBB", relationship="supplier", weight=0.8, commodity="parts")
        assert len(world.graph.edges) == 1
        edge = world.graph.edges[0]
        assert edge.from_ticker == "AAA"
        assert edge.to_ticker == "BBB"
        assert edge.weight == pytest.approx(0.8)
        assert edge.commodity == "parts"

    def test_run_raises_on_empty_world(self, custom_scenario) -> None:
        world = World()
        with pytest.raises(ValueError, match="no twins"):
            world.run(custom_scenario)

    def test_repr(self, mock_twin_a: MockTwin) -> None:
        world = World()
        world.add_twin(mock_twin_a)
        r = repr(world)
        assert "AAA" in r


class TestWorldSnapshot:
    def test_snapshot_has_twins(self, mock_twin_a: MockTwin) -> None:
        world = World()
        world.add_twin(mock_twin_a)
        snap = world.snapshot()
        assert "AAA" in snap.twins

    def test_snapshot_has_macro(self, mock_twin_a: MockTwin) -> None:
        world = World()
        world.add_twin(mock_twin_a)
        snap = world.snapshot()
        assert "interest_rates" in snap.macro
        assert "commodity_prices" in snap.macro
