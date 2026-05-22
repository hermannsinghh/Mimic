"""Visualization helpers — cascade timeline charts and world graph rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .result import WorldResult
    from .world import World


def visualize_cascade(result: WorldResult) -> None:
    """
    Two-panel chart:
      Top: horizontal bar chart of financial impacts per company
      Bottom: line chart of world_state variable evolution over time
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Install matplotlib: pip install matplotlib")
        return

    steps = [r.step for r in result.cascade_timeline]
    tickers = result.most_affected or list(result.financial_impacts.keys())

    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    # Panel 1 — financial impact bars
    ax1 = axes[0]
    impacts = [result.financial_impacts.get(t) for t in tickers[:10]]
    mids = [i.mid if i else 0.0 for i in impacts]
    colors = ["tomato" if m < 0 else "steelblue" for m in mids]

    bars = ax1.barh(tickers[:10], mids, color=colors, alpha=0.85)
    ax1.axvline(0, color="black", linewidth=0.8)
    ax1.set_xlabel("Financial Impact (P50, $M)")
    ax1.set_title(f"Financial Impacts: {result.scenario.title}", fontweight="bold")
    ax1.grid(axis="x", alpha=0.3)

    # Error bars for P10/P90
    for i, (ticker, impact) in enumerate(zip(tickers[:10], impacts)):
        if impact:
            ax1.barh(
                ticker,
                impact.high - impact.mid,
                left=impact.mid,
                color=colors[i],
                alpha=0.3,
            )
            ax1.barh(
                ticker,
                impact.mid - impact.low,
                left=impact.low,
                color=colors[i],
                alpha=0.3,
            )

    # Panel 2 — world_state evolution
    ax2 = axes[1]
    world_state_keys: set[str] = set()
    for step_result in result.cascade_timeline:
        world_state_keys.update(
            k
            for k, v in step_result.world_state.items()
            if isinstance(v, float) and not k.startswith("_")
        )

    # Pick up to 8 most impactful keys
    sorted_keys = sorted(
        world_state_keys,
        key=lambda k: max(
            abs(sr.world_state.get(k, 0.0)) for sr in result.cascade_timeline
        ),
        reverse=True,
    )[:8]

    for key in sorted_keys:
        values = [sr.world_state.get(key, 0.0) for sr in result.cascade_timeline]
        ax2.plot(steps, values, marker="o", linewidth=2, label=key)

    ax2.set_xlabel("Days")
    ax2.set_ylabel("Shock Magnitude (fraction)")
    ax2.set_title("World State Evolution", fontweight="bold")
    ax2.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    ax2.grid(alpha=0.3)
    ax2.axhline(0, color="black", linewidth=0.6)

    plt.suptitle(
        f"mimic-world  ·  {result.scenario.title}"
        f"  ·  Stability: {result.system_stability}",
        fontsize=13,
        fontweight="bold",
    )
    plt.tight_layout()
    plt.show()


def visualize_world(world: World, shock_map: Optional[dict[str, float]] = None) -> None:
    """
    Render the world's relationship graph with NetworkX.

    Args:
        world: the World instance
        shock_map: optional {ticker: shock_magnitude} to color nodes by exposure
    """
    world.graph.visualize()


def visualize_shock_propagation(
    world: World, origin: str, shock: float = -0.5, decay: float = 0.6
) -> None:
    """
    Show how a shock at `origin` propagates through the graph.
    Node color intensity represents shock magnitude.
    """
    try:
        import matplotlib.pyplot as plt
        import networkx as nx
    except ImportError:
        print("Install matplotlib and networkx: pip install matplotlib networkx")
        return

    propagated = world.graph.propagate_shock(origin, shock, decay)

    G = nx.DiGraph()
    for edge in world.graph.edges:
        G.add_edge(edge.from_ticker, edge.to_ticker, weight=edge.weight)

    pos = nx.spring_layout(G, k=2.5, seed=42)

    all_nodes = list(G.nodes)
    node_colors = []
    for node in all_nodes:
        mag = abs(propagated.get(node, 0.0))
        # Red gradient: high shock = deep red, no shock = light gray
        node_colors.append((1.0, max(0, 1 - mag * 2), max(0, 1 - mag * 2)))

    plt.figure(figsize=(12, 8))
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=1800, alpha=0.9)
    nx.draw_networkx_labels(G, pos, font_weight="bold", font_size=9)
    nx.draw_networkx_edges(G, pos, arrows=True, arrowsize=20, alpha=0.6)

    labels = {
        node: f"{node}\n{propagated[node]:+.0%}" if node in propagated else node
        for node in all_nodes
    }
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=7, font_color="black")

    plt.title(
        f"Shock Propagation from {origin} (initial: {shock:+.0%})",
        fontsize=14,
        fontweight="bold",
    )
    plt.axis("off")
    plt.tight_layout()
    plt.show()
