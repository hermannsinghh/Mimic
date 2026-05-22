"""
mimic-world — Multi-company scenario engine for supply chain cascade simulation.

Simulate what happens to an entire system when a shock hits.

    mimic          → single company twin
    mimic-bench    → grades predictions
    mimic-forecast → real quantitative forecasts
    mimic-world    → multi-company system + scenarios  ← YOU ARE HERE
    mimic-sim      → 10,000-run Monte Carlo over worlds
    mimic-signal   → real-time event detection

Quick start::

    from mimic_world import World, Scenario, Twin

    world = World()
    world.add_twin(Twin.from_ticker("AAPL"))
    world.add_twin(Twin.from_ticker("WMT"))
    world.connect("TSMC", "AAPL", relationship="supplier", weight=0.95, commodity="chips")

    scenario = Scenario.from_library("taiwan_strait_closure_30d")
    result = world.run(scenario)
    result.print_summary()
"""

from .cascade import CascadeEngine
from .graph import RelationshipGraph
from .macro import MacroEnvironment
from .result import Decision, ImpactRange, TimeStepResult, WorldResult, WorldState
from .scenario import CascadeRule, Scenario
from .twin import Twin
from .world import World

__version__ = "0.1.0"
__author__ = "mimic-world team"

__all__ = [
    "World",
    "Scenario",
    "CascadeRule",
    "Twin",
    "WorldResult",
    "WorldState",
    "TimeStepResult",
    "Decision",
    "ImpactRange",
    "RelationshipGraph",
    "MacroEnvironment",
    "CascadeEngine",
]
