"""Tests for Eisenberg-Noe clearing vector — Plan §3.3 W-01.

Golden vectors in this file ARE the source of truth for determinism.yml CI.
Any change to eisenberg_noe_clearing() must update these values and
bump mimic-world to the next major version.
"""
from __future__ import annotations

import numpy as np
import pytest

from mimic_world.contagion.eisenberg_noe import ENResult, eisenberg_noe_clearing


# ── helpers ──────────────────────────────────────────────────────────────────

def _L2(l01: float, l10: float) -> np.ndarray:
    return np.array([[0, l01], [l10, 0]], dtype=float)


# ── golden test vectors ───────────────────────────────────────────────────────

class TestENGoldenVectors:
    """These exact values must never change without a major version bump."""

    def test_no_default_all_solvent(self):
        """Both nodes healthy — clearing vector equals nominal liabilities."""
        L = _L2(10.0, 8.0)
        e = np.array([20.0, 15.0])
        r = eisenberg_noe_clearing(L, e)

        np.testing.assert_allclose(r.p_star, [10.0, 8.0], atol=1e-8)
        assert not np.any(r.defaulted)
        assert r.converged

    def test_single_default(self):
        """Node 0 is insolvent. p_star[0] < p_bar[0]."""
        # Node 0 owes 10, has external assets 2; Node 1 owes 5, has assets 20
        L = _L2(10.0, 5.0)
        e = np.array([2.0, 20.0])
        r = eisenberg_noe_clearing(L, e)

        # Node 0: p_bar=10; e=2; inflow from node 1 = (5/5)*p*[1]=p*[1]=5
        # p*[0] = min(10, 2+5) = 7
        # Node 1: p_bar=5; e=20; inflow from node 0 = (10/10)*p*[0]=7
        # p*[1] = min(5, 20+7) = 5
        np.testing.assert_allclose(r.p_star, [7.0, 5.0], atol=1e-8)
        assert r.defaulted[0]
        assert not r.defaulted[1]

    def test_cascade_default(self):
        """Node 0 defaults → reduces node 1's inflow → node 1 defaults too.

        Node 2 receives full payment from node 1 (it's owed 80, node 1 pays 70,
        but node 2's external 5 + 70 = 75 covers its own 60 obligation). So node
        2 stays solvent. Golden p_star = [65, 70, 60]. See ADR
        2026-05-21-en-golden-correction.md.
        """
        L = np.array([
            [0, 100, 0],
            [0,   0, 80],
            [60,  0,  0],
        ], dtype=float)
        e = np.array([5.0, 5.0, 5.0])
        r = eisenberg_noe_clearing(L, e)

        np.testing.assert_allclose(r.p_star, [65.0, 70.0, 60.0], atol=1e-8)
        assert r.defaulted[0]
        assert r.defaulted[1]
        assert not r.defaulted[2]
        assert r.converged
        assert np.all(r.p_star >= 0)
        assert np.all(r.p_star <= r.p_bar + 1e-8)

    def test_zero_liabilities(self):
        """No inter-bank connections — each clears independently."""
        L = np.zeros((3, 3))
        e = np.array([10.0, -5.0, 20.0])
        r = eisenberg_noe_clearing(L, e)

        # p_bar = 0 for all; p_star = 0 for all (nothing owed)
        np.testing.assert_allclose(r.p_star, [0.0, 0.0, 0.0], atol=1e-8)
        assert not np.any(r.defaulted)

    def test_three_node_ring_golden(self):
        """3-node ring — node 0 defaults; nodes 1 and 2 pay in full.

        Node 0: e=10, inflow=30 → pays 40 of 50 owed (defaults by 10).
        Node 1: e=15, inflow=40 → pays 40 of 40 owed.
        Node 2: e=8,  inflow=40 → pays 30 of 30 owed.
        See ADR 2026-05-21-en-golden-correction.md.
        """
        L = np.array([
            [0,  50,  0],
            [0,   0, 40],
            [30,  0,  0],
        ], dtype=float)
        e = np.array([10.0, 15.0, 8.0])
        r = eisenberg_noe_clearing(L, e)

        np.testing.assert_allclose(r.p_star, [40.0, 40.0, 30.0], atol=1e-7)
        assert r.defaulted[0]
        assert not r.defaulted[1]
        assert not r.defaulted[2]
        assert r.converged


# ── behavioural properties ────────────────────────────────────────────────────

class TestENProperties:
    """Mathematical properties that must hold for any valid input."""

    def test_clearing_vector_in_bounds(self):
        rng = np.random.default_rng(42)
        L = rng.uniform(0, 50, (5, 5))
        np.fill_diagonal(L, 0)
        e = rng.uniform(0, 100, 5)
        r = eisenberg_noe_clearing(L, e)

        assert np.all(r.p_star >= 0)
        assert np.all(r.p_star <= r.p_bar + 1e-8)

    def test_convergence_random(self):
        rng = np.random.default_rng(0)
        L = rng.uniform(0, 100, (10, 10))
        np.fill_diagonal(L, 0)
        e = rng.uniform(-20, 200, 10)
        r = eisenberg_noe_clearing(L, e)

        assert r.converged

    def test_default_flag_consistent(self):
        L = _L2(10.0, 5.0)
        e = np.array([2.0, 20.0])
        r = eisenberg_noe_clearing(L, e)

        assert r.defaulted[0] == (r.p_star[0] < r.p_bar[0] - 1e-9)
        assert r.defaulted[1] == (r.p_star[1] < r.p_bar[1] - 1e-9)

    def test_raises_on_negative_L(self):
        L = np.array([[0, -5], [3, 0]], dtype=float)
        e = np.array([10.0, 10.0])
        with pytest.raises(ValueError, match="non-negative"):
            eisenberg_noe_clearing(L, e)

    def test_raises_on_nonzero_diagonal(self):
        L = np.array([[1, 5], [3, 0]], dtype=float)
        e = np.array([10.0, 10.0])
        with pytest.raises(ValueError, match="diagonal"):
            eisenberg_noe_clearing(L, e)


# ── integration with LiabilityNetwork ────────────────────────────────────────

class TestENWithNetwork:
    def test_network_to_en_round_trip(self):
        from mimic_world.contagion.network import LiabilityNetwork

        net = LiabilityNetwork()
        net.add_node("A", equity=50.0, total_assets=200.0)
        net.add_node("B", equity=30.0, total_assets=150.0)
        net.add_bilateral_exposure("A", "B", 10.0)
        net.add_bilateral_exposure("B", "A", 8.0)

        L, _v, names = net.to_matrix()
        e = net.external_assets()
        r = eisenberg_noe_clearing(L, e)

        assert r.converged
        assert len(r.p_star) == 2
        assert names == ["A", "B"]
