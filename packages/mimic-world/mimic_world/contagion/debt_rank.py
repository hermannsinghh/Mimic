"""DebtRank — iterative systemic importance measure — Plan §3.3 W-02.

Reference: Battiston et al., "DebtRank: Too Central to Fail?", Scientific
Reports 2, 541, 2012.

DebtRank measures how much economic value is lost when an initial set of nodes
is shocked. Unlike EN (which finds a single clearing), DebtRank produces a
continuous stress propagation and a scalar R ∈ [0, 1] for systemic impact.

State per node:
    h_i(t) ∈ [0, 1]   stress level (0=healthy, 1=fully distressed)
    s_i(t) ∈ {U, D, I}  Undistressed, Distressed, Inactive (already propagated)

Update rule (for node i in state Distressed at time t):
    h_j(t+1) = min(1,  h_j(t) + W_ij * h_i(t))   for j in Undistressed
    s_i(t+1) = Inactive  (i can only propagate once)

Vulnerability matrix:
    W_ij = L_ij / V_j
    L_ij = liability from i to j (j is owed by i)
    V_j  = economic value of j (equity or total assets)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np


class NodeState(IntEnum):
    UNDISTRESSED = 0
    DISTRESSED = 1
    INACTIVE = 2  # already propagated; cannot propagate again


@dataclass(frozen=True)
class DebtRankResult:
    """Output of the DebtRank computation."""
    h_final: np.ndarray
    """Final stress vector (n,). h[i] ∈ [0,1]."""
    R: float
    """Aggregate systemic impact ∈ [0, 1]. R = sum_i h_i * v_i / sum_i v_i."""
    impacted_fraction: float
    """Fraction of nodes with h_final > 0."""
    iterations: int
    converged: bool


def debt_rank(
    L: np.ndarray,
    v: np.ndarray,
    shocked_nodes: dict[int, float],
    max_iter: int = 1_000,
    tol: float = 1e-9,
) -> DebtRankResult:
    """Run the DebtRank algorithm.

    Args:
        L: (n, n) float. L[i,j] = liability from i to j (j is creditor).
        v: (n,) float. Economic value (equity or total assets) of each node.
        shocked_nodes: {node_index: initial_stress_level}. Stress ∈ [0, 1].
        max_iter: Maximum propagation rounds.
        tol: Convergence tolerance on h change.

    Returns:
        DebtRankResult with final stress vector and scalar impact R.
    """
    L = np.asarray(L, dtype=float)
    v = np.asarray(v, dtype=float)
    n = v.shape[0]

    if L.shape != (n, n):
        raise ValueError(f"L must be ({n},{n}), got {L.shape}")
    if np.any(v <= 0):
        raise ValueError("Economic values v must be strictly positive")
    if not shocked_nodes:
        raise ValueError("shocked_nodes must be non-empty")

    # Vulnerability matrix: W[i,j] = L[i,j] / v[j]
    # Capped at 1 per the original paper
    W = np.minimum(L / v[np.newaxis, :], 1.0)  # (n, n)

    # Initialise state
    h = np.zeros(n)
    for idx, stress in shocked_nodes.items():
        h[idx] = float(np.clip(stress, 0.0, 1.0))

    state = np.full(n, NodeState.UNDISTRESSED, dtype=int)
    for idx in shocked_nodes:
        state[idx] = NodeState.DISTRESSED

    converged = False
    iters = 0

    for iters in range(1, max_iter + 1):
        h_prev = h.copy()
        newly_inactive: list[int] = []

        for i in range(n):
            if state[i] != NodeState.DISTRESSED:
                continue
            # Propagate i's stress to all undistressed neighbours
            for j in range(n):
                if state[j] == NodeState.UNDISTRESSED and W[i, j] > 0:
                    h[j] = min(1.0, h[j] + W[i, j] * h[i])
                    if h[j] > 0:
                        state[j] = NodeState.DISTRESSED
            newly_inactive.append(i)

        for i in newly_inactive:
            state[i] = NodeState.INACTIVE

        delta = np.max(np.abs(h - h_prev))
        if delta < tol or not np.any(state == NodeState.DISTRESSED):
            converged = True
            break

    v_total = v.sum()
    R = float(np.dot(h, v) / v_total) if v_total > 0 else 0.0

    return DebtRankResult(
        h_final=h,
        R=R,
        impacted_fraction=float(np.mean(h > 0)),
        iterations=iters,
        converged=converged,
    )
