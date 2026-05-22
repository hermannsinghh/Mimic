"""Provably-correct financial contagion math — Plan §3.3 W-01/W-02.

Primary API:
    eisenberg_noe_clearing  — fixed-point clearing vector
    debt_rank               — iterative systemic importance scoring
    LiabilityNetwork        — build a liability matrix from entity data

The legacy CascadeEngine (heuristic) is now a descriptive overlay in
mimic_world.narrative — it composes over these primitives.
"""
from .debt_rank import DebtRankResult, debt_rank  # noqa: F401
from .eisenberg_noe import ENResult, eisenberg_noe_clearing  # noqa: F401
from .fibo_builder import FIBOValidationError, from_fibo_dict, from_fibo_json  # noqa: F401
from .network import LiabilityNetwork  # noqa: F401
from .stress import (  # noqa: F401
    PersonaAction,
    StressResult,
    apply_actions_to_external_assets,
    propagate_stress,
)

__all__ = [
    "eisenberg_noe_clearing",
    "ENResult",
    "debt_rank",
    "DebtRankResult",
    "LiabilityNetwork",
    "from_fibo_dict",
    "from_fibo_json",
    "FIBOValidationError",
    "PersonaAction",
    "StressResult",
    "propagate_stress",
    "apply_actions_to_external_assets",
]
