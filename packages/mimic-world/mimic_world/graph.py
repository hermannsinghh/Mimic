"""RelationshipGraph — directed graph of inter-company supply/demand relationships."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Edge:
    from_ticker: str
    to_ticker: str
    relationship: str  # "supplier" | "customer" | "competitor" | "input_shared"
    weight: float      # 0–1 strength of dependency
    commodity: Optional[str] = None


class RelationshipGraph:
    """
    Directed graph encoding supplier/customer relationships between company twins.

    Built automatically from 10-K disclosures and BEA I-O tables (Phase 3),
    or constructed manually via add_edge().
    """

    def __init__(self) -> None:
        self._edges: list[Edge] = []
        self._nodes: set[str] = set()

    def add_edge(
        self,
        from_ticker: str,
        to_ticker: str,
        relationship: str = "supplier",
        weight: float = 0.5,
        commodity: Optional[str] = None,
    ) -> None:
        """Add a directed relationship edge."""
        self._edges.append(
            Edge(
                from_ticker=from_ticker,
                to_ticker=to_ticker,
                relationship=relationship,
                weight=weight,
                commodity=commodity,
            )
        )
        self._nodes.add(from_ticker)
        self._nodes.add(to_ticker)

    def get_upstream(self, ticker: str, hops: int = 2) -> list[str]:
        """Companies that supply to ticker (upstream in supply chain)."""
        result: set[str] = set()
        frontier = {ticker}

        for _ in range(hops):
            next_frontier: set[str] = set()
            for edge in self._edges:
                if edge.to_ticker in frontier and edge.relationship in (
                    "supplier",
                    "input_shared",
                ):
                    if edge.from_ticker != ticker:
                        result.add(edge.from_ticker)
                        next_frontier.add(edge.from_ticker)
            frontier = next_frontier

        return list(result)

    def get_downstream(self, ticker: str, hops: int = 2) -> list[str]:
        """Companies that depend on ticker (downstream in supply chain)."""
        result: set[str] = set()
        frontier = {ticker}

        for _ in range(hops):
            next_frontier: set[str] = set()
            for edge in self._edges:
                if edge.from_ticker in frontier and edge.relationship in (
                    "supplier",
                    "input_shared",
                ):
                    if edge.to_ticker != ticker:
                        result.add(edge.to_ticker)
                        next_frontier.add(edge.to_ticker)
            frontier = next_frontier

        return list(result)

    def get_neighbors(self, ticker: str) -> list[str]:
        """All directly connected tickers (both directions)."""
        neighbors: set[str] = set()
        for edge in self._edges:
            if edge.from_ticker == ticker:
                neighbors.add(edge.to_ticker)
            elif edge.to_ticker == ticker:
                neighbors.add(edge.from_ticker)
        return list(neighbors)

    def get_edges_for(self, ticker: str) -> list[Edge]:
        return [e for e in self._edges if e.from_ticker == ticker or e.to_ticker == ticker]

    def propagate_shock(
        self, origin: str, shock: float, decay: float = 0.6
    ) -> dict[str, float]:
        """
        BFS shock propagation from origin through the graph.
        Each hop attenuates the shock by `decay * edge.weight`.
        Returns {ticker: shock_magnitude} for all reachable nodes.
        """
        affected: dict[str, float] = {origin: shock}
        frontier: dict[str, float] = {origin: shock}
        visited: set[str] = {origin}

        while frontier:
            next_frontier: dict[str, float] = {}
            for edge in self._edges:
                if edge.from_ticker in frontier and edge.to_ticker not in visited:
                    source, target = edge.from_ticker, edge.to_ticker
                elif edge.to_ticker in frontier and edge.from_ticker not in visited:
                    source, target = edge.to_ticker, edge.from_ticker
                else:
                    continue

                propagated = frontier[source] * decay * edge.weight
                if abs(propagated) > 0.01:  # prune tiny shocks
                    next_frontier[target] = propagated
                    affected[target] = propagated
                    visited.add(target)

            frontier = next_frontier

        return affected

    def visualize(self) -> None:
        """Render graph using NetworkX + matplotlib."""
        try:
            import matplotlib.pyplot as plt
            import networkx as nx
        except ImportError:
            print("Install dependencies: pip install networkx matplotlib")
            return

        G = nx.DiGraph()
        for edge in self._edges:
            G.add_edge(
                edge.from_ticker,
                edge.to_ticker,
                weight=edge.weight,
                label=edge.commodity or edge.relationship,
            )

        pos = nx.spring_layout(G, k=2.5, seed=42)
        plt.figure(figsize=(14, 9))

        nx.draw_networkx_nodes(G, pos, node_size=1800, node_color="steelblue", alpha=0.9)
        nx.draw_networkx_labels(G, pos, font_color="white", font_weight="bold", font_size=9)
        nx.draw_networkx_edges(
            G, pos, arrows=True, arrowsize=20, edge_color="gray", alpha=0.7, width=2
        )

        edge_labels = {
            (e.from_ticker, e.to_ticker): f"{e.commodity or e.relationship}\n({e.weight:.0%})"
            for e in self._edges
        }
        nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=7)

        plt.title("Supply Chain Relationship Graph", fontsize=16, fontweight="bold")
        plt.axis("off")
        plt.tight_layout()
        plt.show()

    @property
    def nodes(self) -> list[str]:
        return list(self._nodes)

    @property
    def edges(self) -> list[Edge]:
        return list(self._edges)

    def __len__(self) -> int:
        return len(self._nodes)

    def __repr__(self) -> str:
        return f"RelationshipGraph(nodes={len(self._nodes)}, edges={len(self._edges)})"
