"""Eisenberg-Noe clearing vector — Plan §3.3 W-01.

Reference: Eisenberg & Noe, "Systemic Risk in Financial Systems", Management
Science 47(2), 2001.

The clearing vector p* is the greatest fixed point of:
    p*[i] = min(p_bar[i],  e[i] + sum_j Pi[j,i] * p*[j])

where:
    L[i,j]    = nominal liability from node i to node j
    p_bar[i]  = total nominal liabilities of i  = sum_j L[i,j]
    Pi[i,j]   = L[i,j] / p_bar[i]  (relative liability matrix, rows sum to <= 1)
    e[i]      = external assets of node i (positive = healthy)

Iteration converges monotonically from above to p* (Theorem 1 of EN 2001).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ENResult:
    """Output of the Eisenberg-Noe clearing computation."""
    p_star: np.ndarray
    """Clearing payments vector (n,). p_star[i] <= p_bar[i]."""
    p_bar: np.ndarray
    """Nominal total liabilities (n,)."""
    defaulted: np.ndarray
    """Boolean mask (n,): True where p_star[i] < p_bar[i]."""
    equity: np.ndarray
    """Post-clearing equity (n,): e[i] + inflow - p_star[i]. May be negative."""
    converged: bool
    iterations: int


def eisenberg_noe_clearing(
    L: np.ndarray,
    e: np.ndarray,
    max_iter: int = 1_000,
    tol: float = 1e-9,
) -> ENResult:
    """Compute the Eisenberg-Noe clearing vector.

    Args:
        L: (n, n) float array. L[i,j] = liability from i to j. L[i,i] must be 0.
        e: (n,) float array. External assets of each node.
        max_iter: Maximum fixed-point iterations.
        tol: Convergence tolerance (sup-norm on p change).

    Returns:
        ENResult with clearing payments, default set, equity, convergence info.

    Raises:
        ValueError: If L or e have incompatible shapes, or L has negative entries.
    """
    L = np.asarray(L, dtype=float)
    e = np.asarray(e, dtype=float)
    n = e.shape[0]

    if L.shape != (n, n):
        raise ValueError(f"L must be ({n},{n}), got {L.shape}")
    if np.any(L < 0):
        raise ValueError("L must be non-negative")
    if np.any(np.diag(L) != 0):
        raise ValueError("L diagonal (self-liabilities) must be zero")

    # Total nominal liabilities of each node
    p_bar = L.sum(axis=1)  # (n,)

    # Relative liability matrix Pi[i,j] = L[i,j] / p_bar[i]
    # (fraction of i's total obligations owed to j)
    Pi = np.zeros((n, n))
    nonzero = p_bar > 0
    Pi[nonzero] = L[nonzero] / p_bar[nonzero, np.newaxis]

    # Fixed-point iteration: start from p = p_bar (maximum), iterate down
    p = p_bar.copy()
    converged = False
    iters = 0

    for iters in range(1, max_iter + 1):
        # Inflow to each node from others' payments
        inflow = Pi.T @ p  # (n,): sum_j Pi[j,i] * p[j]
        p_new = np.minimum(p_bar, e + inflow)
        p_new = np.maximum(p_new, 0.0)  # payments are non-negative

        if np.max(np.abs(p_new - p)) < tol:
            p = p_new
            converged = True
            break
        p = p_new

    inflow_final = Pi.T @ p
    equity = e + inflow_final - p

    return ENResult(
        p_star=p,
        p_bar=p_bar,
        defaulted=p < p_bar - tol,
        equity=equity,
        converged=converged,
        iterations=iters,
    )
