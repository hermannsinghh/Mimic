"""Tests for RelationshipGraph."""

from __future__ import annotations

import pytest

from mimic_world.graph import Edge, RelationshipGraph


@pytest.fixture
def chip_graph() -> RelationshipGraph:
    g = RelationshipGraph()
    g.add_edge("TSMC", "AAPL", relationship="supplier", weight=0.95, commodity="chips")
    g.add_edge("TSMC", "NVDA", relationship="supplier", weight=0.90, commodity="chips")
    g.add_edge("TSMC", "AMD", relationship="supplier", weight=0.85, commodity="chips")
    g.add_edge("XOM", "FDX", relationship="supplier", weight=0.40, commodity="jet_fuel")
    g.add_edge("MAERSK", "WMT", relationship="supplier", weight=0.30, commodity="shipping")
    return g


class TestAddEdge:
    def test_edge_added(self, chip_graph: RelationshipGraph) -> None:
        assert len(chip_graph.edges) == 5

    def test_nodes_registered(self, chip_graph: RelationshipGraph) -> None:
        assert "TSMC" in chip_graph.nodes
        assert "AAPL" in chip_graph.nodes
        assert "WMT" in chip_graph.nodes

    def test_len_is_node_count(self, chip_graph: RelationshipGraph) -> None:
        assert len(chip_graph) == len(chip_graph.nodes)


class TestUpstreamDownstream:
    def test_downstream_from_tsmc(self, chip_graph: RelationshipGraph) -> None:
        downstream = chip_graph.get_downstream("TSMC", hops=1)
        assert "AAPL" in downstream
        assert "NVDA" in downstream
        assert "AMD" in downstream

    def test_upstream_of_aapl(self, chip_graph: RelationshipGraph) -> None:
        upstream = chip_graph.get_upstream("AAPL", hops=1)
        assert "TSMC" in upstream

    def test_no_upstream_for_root(self, chip_graph: RelationshipGraph) -> None:
        # TSMC has no suppliers in this graph
        upstream = chip_graph.get_upstream("TSMC", hops=1)
        assert "TSMC" not in upstream


class TestGetNeighbors:
    def test_tsmc_neighbors(self, chip_graph: RelationshipGraph) -> None:
        neighbors = chip_graph.get_neighbors("TSMC")
        assert set(neighbors) == {"AAPL", "NVDA", "AMD"}

    def test_aapl_neighbors(self, chip_graph: RelationshipGraph) -> None:
        neighbors = chip_graph.get_neighbors("AAPL")
        assert "TSMC" in neighbors


class TestPropagateShock:
    def test_origin_has_full_shock(self, chip_graph: RelationshipGraph) -> None:
        affected = chip_graph.propagate_shock("TSMC", -0.65, decay=0.6)
        assert affected["TSMC"] == pytest.approx(-0.65)

    def test_downstream_has_attenuated_shock(self, chip_graph: RelationshipGraph) -> None:
        affected = chip_graph.propagate_shock("TSMC", -0.65, decay=0.6)
        # AAPL shock = -0.65 * 0.6 * 0.95 ≈ -0.3705
        assert "AAPL" in affected
        assert affected["AAPL"] == pytest.approx(-0.65 * 0.6 * 0.95, abs=0.01)

    def test_unconnected_company_not_affected(self, chip_graph: RelationshipGraph) -> None:
        affected = chip_graph.propagate_shock("TSMC", -0.65, decay=0.6)
        # WMT is not connected to TSMC in this graph
        assert "WMT" not in affected

    def test_tiny_shocks_pruned(self) -> None:
        g = RelationshipGraph()
        g.add_edge("A", "B", weight=0.01)
        g.add_edge("B", "C", weight=0.01)
        # A→B→C with tiny weights; C should be pruned
        affected = g.propagate_shock("A", -0.10, decay=0.1)
        assert "C" not in affected


class TestGetEdgesFor:
    def test_edges_for_tsmc(self, chip_graph: RelationshipGraph) -> None:
        edges = chip_graph.get_edges_for("TSMC")
        tickers = {(e.from_ticker, e.to_ticker) for e in edges}
        assert ("TSMC", "AAPL") in tickers
        assert ("TSMC", "NVDA") in tickers


class TestRepr:
    def test_repr_shows_counts(self, chip_graph: RelationshipGraph) -> None:
        r = repr(chip_graph)
        assert "nodes=" in r
        assert "edges=" in r
