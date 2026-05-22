"""World — the top-level simulation container."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from .cascade import CascadeEngine
from .graph import RelationshipGraph
from .macro import MacroEnvironment
from .result import WorldResult, WorldState

if TYPE_CHECKING:
    from .scenario import Scenario


class World:
    """
    A collection of company twins connected by a supply-chain relationship graph.

    This is the core abstraction of mimic-world.
    Twins react to a scenario, their reactions update a shared world_state,
    and the cascade propagates through the graph.

    Example::

        world = World()
        world.add_twin(Twin.from_ticker("AAPL"))
        world.add_twin(Twin.from_ticker("WMT"))
        world.connect("TSMC", "AAPL", relationship="supplier", weight=0.95, commodity="chips")

        scenario = Scenario.from_library("taiwan_strait_closure_30d")
        result = world.run(scenario)
        result.print_summary()
    """

    def __init__(self) -> None:
        self.twins: dict[str, Any] = {}
        self.graph: RelationshipGraph = RelationshipGraph()
        self.macro: MacroEnvironment = MacroEnvironment()
        self._engine: CascadeEngine = CascadeEngine()

    def add_twin(self, twin: Any) -> None:
        """
        Add a company twin. Accepts any object with a `ticker` attribute
        and a `simulate(world_state, step)` method.
        """
        ticker = twin.ticker if hasattr(twin, "ticker") else str(twin)
        self.twins[ticker] = twin
        # Auto-register in graph so neighbors can be discovered.
        self.graph._nodes.add(ticker)

    def connect(
        self,
        supplier: str,
        customer: str,
        relationship: str = "supplier",
        weight: float = 0.5,
        commodity: Optional[str] = None,
    ) -> None:
        """
        Create a directed edge from supplier → customer in the relationship graph.

        Args:
            supplier: ticker of the upstream company
            customer: ticker of the downstream company
            relationship: "supplier" | "customer" | "competitor" | "input_shared"
            weight: 0–1 strength of dependency (1 = sole source)
            commodity: what flows between them (e.g. "chips", "jet_fuel", "shipping")
        """
        self.graph.add_edge(
            from_ticker=supplier,
            to_ticker=customer,
            relationship=relationship,
            weight=weight,
            commodity=commodity,
        )

    def run(
        self,
        scenario: Scenario,
        time_steps: list[int] = [1, 7, 30, 90],
    ) -> WorldResult:
        """
        Run a scenario through the world and return cascade results.

        At each time step:
          1. Apply scenario shocks to initially affected companies
          2. Each affected twin calls simulate() with shared world_state
          3. Twin decisions update world_state (visible to subsequent twins)
          4. Scenario cascade rules derive secondary propagations
          5. Graph neighbors with sufficient exposure are pulled in
          6. Repeat for next time step

        Args:
            scenario: the shock to apply
            time_steps: days at which to evaluate (default: 1, 7, 30, 90)

        Returns:
            WorldResult with cascade_timeline, financial_impacts, system_stability, etc.
        """
        if not self.twins:
            raise ValueError("World has no twins. Add companies with world.add_twin()")

        return self._engine.run(self, scenario, time_steps)

    def snapshot(self) -> WorldState:
        """Capture the current world state (macro + twin summaries)."""
        return WorldState(
            macro=self.macro.get_state(),
            twins={ticker: {"ticker": ticker} for ticker in self.twins},
        )

    def __repr__(self) -> str:
        return (
            f"World(twins={list(self.twins.keys())}, "
            f"edges={len(self.graph.edges)})"
        )
