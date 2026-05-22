"""Combined EN + DebtRank + persona-decision overlay — Plan §3.3 W-05.

Wires the three together:

    1. Run EN clearing → which nodes default, how much they actually pay.
    2. Run DebtRank → which nodes are systemically important under stress.
    3. Overlay persona Decisions → reduce/expand each node's external assets
       per the agent's announced action (e.g. 'cut_exposure' shrinks e[i]),
       then re-run EN.

The overlay is a numerical projection of qualitative actions onto the EN
inputs. It does NOT redefine the contagion math — both engines remain the
single source of truth for default propagation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .debt_rank import DebtRankResult, debt_rank
from .eisenberg_noe import ENResult, eisenberg_noe_clearing


@dataclass(frozen=True)
class PersonaAction:
    """A reduced view of a Decision that the contagion engine can consume."""
    node_name: str            # must match a name in LiabilityNetwork.node_names()
    action_type: str          # one of: hedge, raise_capital, cut_exposure, hold, sell, buy, reinsure, cede, retain
    quantity_usd: float       # signed: positive = adds external assets, negative = removes
    confidence: float


@dataclass(frozen=True)
class StressResult:
    """Output of combined stress propagation."""
    baseline_en: ENResult
    baseline_debt_rank: DebtRankResult
    overlaid_en: ENResult
    overlaid_debt_rank: DebtRankResult
    actions_applied: tuple[PersonaAction, ...]
    delta_p_star: np.ndarray   # overlaid.p_star - baseline.p_star
    delta_h: np.ndarray        # overlaid.h_final - baseline.h_final
    delta_R: float             # overlaid.R - baseline.R (aggregate systemic impact)


# Mapping from action_type → sign on the external-asset shock.
# - raise_capital: adds external assets (positive)
# - cut_exposure / sell: shrinks balance sheet (negative)
# - hedge: locks in losses (small negative)
# - reinsure / cede: transfers exposure off-book (negative)
# - hold / buy / retain: identity
_ACTION_SIGNS: dict[str, float] = {
    "raise_capital": +1.0,
    "cut_exposure":  -1.0,
    "sell":          -1.0,
    "hedge":         -0.1,
    "reinsure":      -1.0,
    "cede":          -1.0,
    "hold":           0.0,
    "buy":            0.0,
    "retain":         0.0,
    "lobby":          0.0,
}


def apply_actions_to_external_assets(
    e: np.ndarray,
    names: list[str],
    actions: list[PersonaAction],
) -> np.ndarray:
    """Project persona actions onto the EN external-assets vector."""
    e_out = e.copy()
    name_to_idx = {n: i for i, n in enumerate(names)}
    for act in actions:
        idx = name_to_idx.get(act.node_name)
        if idx is None:
            continue
        sign = _ACTION_SIGNS.get(act.action_type, 0.0)
        e_out[idx] += sign * act.quantity_usd
    return e_out


def propagate_stress(
    L: np.ndarray,
    e: np.ndarray,
    v: np.ndarray,
    names: list[str],
    actions: list[PersonaAction],
    *,
    shocked_nodes: dict[int, float] | None = None,
) -> StressResult:
    """Run baseline + overlaid EN + DebtRank.

    Args:
        L:      (n,n) liability matrix
        e:      (n,) external assets
        v:      (n,) economic value (used by DebtRank)
        names:  list of node names corresponding to indices
        actions: persona Decisions reduced to PersonaAction
        shocked_nodes: optional {idx: stress} for DebtRank; defaults to a
                       uniform tiny shock on node 0 (every run needs *some*
                       seed shock or DebtRank raises).
    """
    n = e.shape[0]
    if shocked_nodes is None:
        shocked_nodes = {0: 0.05}

    baseline_en = eisenberg_noe_clearing(L, e)
    baseline_dr = debt_rank(L, v, shocked_nodes)

    e_overlay = apply_actions_to_external_assets(e, names, actions)
    overlaid_en = eisenberg_noe_clearing(L, e_overlay)
    overlaid_dr = debt_rank(L, v, shocked_nodes)

    return StressResult(
        baseline_en=baseline_en,
        baseline_debt_rank=baseline_dr,
        overlaid_en=overlaid_en,
        overlaid_debt_rank=overlaid_dr,
        actions_applied=tuple(actions),
        delta_p_star=overlaid_en.p_star - baseline_en.p_star,
        delta_h=overlaid_dr.h_final - baseline_dr.h_final,
        delta_R=overlaid_dr.R - baseline_dr.R,
    )
