"""
Tier 2 execution: formula engine with LLM-cached behavioral anchoring.

Same formula engine as Tier 3, but company_behavior comes from a pre-computed
DecisionCache rather than random distributions. This replaces behavioral noise
with LLM-calibrated responses, producing narrower, more realistic distributions.

The narrowing vs Tier 3 is the core result: behaviorally-anchored simulations
carry less model uncertainty than pure-formula Monte Carlo.
"""

from __future__ import annotations

from mimic_sim.execution.tier3_formulas import CompanyProfile, RunOutcome, run_tier3
from mimic_sim.parameter_space import SampledParams


def run_tier2(
    profiles: list[CompanyProfile],
    params: SampledParams,
    run_id: int,
    cache: object,  # DecisionCache — imported lazily to avoid circular imports
) -> RunOutcome:
    """
    Execute one Tier 2 run: Tier 3 formula engine + cached behavioral modifiers.

    The sampled severity and duration are used to look up the nearest grid point
    in the cache, replacing the random company_behavior with calibrated deltas.
    All other parameters (macro, intervention) are preserved from the Monte Carlo draw.
    """
    behavioral = cache.lookup(params.severity, params.duration_days)

    anchored = SampledParams(
        severity=params.severity,
        duration_days=params.duration_days,
        macro_conditions=params.macro_conditions,
        company_behavior=behavioral,
        intervention_triggered=params.intervention_triggered,
        run_seed=params.run_seed,
    )

    return run_tier3(profiles, anchored, run_id)
