"""
mimic-sim: Monte Carlo simulation engine for the Mimic ecosystem.

10,000 runs. LLM-agent decisions. Economically-coherent distributions.
"""

from mimic_sim.parameter_space import Distribution, ParameterSpace, SampledParams
from mimic_sim.simulation import Simulation
from mimic_sim.result import SimulationResult

__version__ = "0.1.0"
__all__ = [
    "Distribution",
    "ParameterSpace",
    "SampledParams",
    "Simulation",
    "SimulationResult",
]
