"""Tests for DebtRank — Plan §3.3 W-02."""
from __future__ import annotations

import numpy as np
import pytest

from mimic_world.contagion.debt_rank import DebtRankResult, debt_rank, NodeState


def _simple_net() -> tuple[np.ndarray, np.ndarray]:
    """3-node chain: 0→1→2, v=[100,80,60]."""
    L = np.array([
        [0, 20,  0],
        [0,  0, 15],
        [0,  0,  0],
    ], dtype=float)
    v = np.array([100.0, 80.0, 60.0])
    return L, v


class TestDebtRankGolden:
    """Pinned golden values — never change without a major version bump."""

    def test_single_node_full_distress(self):
        """Node 0 fully distressed propagates to 1 then 2."""
        L, v = _simple_net()
        r = debt_rank(L, v, shocked_nodes={0: 1.0})

        # W[0,1] = L[0,1]/v[1] = 20/80 = 0.25
        # h[1] after round 1: min(1, 0 + 0.25*1.0) = 0.25
        # W[1,2] = L[1,2]/v[2] = 15/60 = 0.25
        # h[2] after round 2: min(1, 0 + 0.25*0.25) = 0.0625
        np.testing.assert_allclose(r.h_final[0], 1.0, atol=1e-9)
        np.testing.assert_allclose(r.h_final[1], 0.25, atol=1e-9)
        np.testing.assert_allclose(r.h_final[2], 0.0625, atol=1e-9)
        assert r.converged

    def test_R_scalar_golden(self):
        L, v = _simple_net()
        r = debt_rank(L, v, shocked_nodes={0: 1.0})

        # R = (1.0*100 + 0.25*80 + 0.0625*60) / 240
        expected_R = (1.0 * 100 + 0.25 * 80 + 0.0625 * 60) / 240.0
        np.testing.assert_allclose(r.R, expected_R, atol=1e-9)

    def test_no_propagation_isolated_shock(self):
        """Shock to a node with no outgoing liabilities stays local."""
        L = np.zeros((3, 3))
        v = np.array([100.0, 80.0, 60.0])
        r = debt_rank(L, v, shocked_nodes={1: 0.5})

        np.testing.assert_allclose(r.h_final[0], 0.0, atol=1e-9)
        np.testing.assert_allclose(r.h_final[1], 0.5, atol=1e-9)
        np.testing.assert_allclose(r.h_final[2], 0.0, atol=1e-9)

    def test_partial_shock_propagation(self):
        """Partial initial stress propagates proportionally."""
        L, v = _simple_net()
        r = debt_rank(L, v, shocked_nodes={0: 0.5})

        np.testing.assert_allclose(r.h_final[0], 0.5, atol=1e-9)
        np.testing.assert_allclose(r.h_final[1], 0.125, atol=1e-9)
        np.testing.assert_allclose(r.h_final[2], 0.03125, atol=1e-9)


class TestDebtRankProperties:
    def test_h_bounded_to_unit_interval(self):
        rng = np.random.default_rng(7)
        L = rng.uniform(0, 50, (6, 6))
        np.fill_diagonal(L, 0)
        v = rng.uniform(10, 200, 6)
        r = debt_rank(L, v, shocked_nodes={0: 1.0, 1: 0.8})

        assert np.all(r.h_final >= 0.0)
        assert np.all(r.h_final <= 1.0 + 1e-9)

    def test_R_bounded_to_unit_interval(self):
        L = np.array([[0, 100], [100, 0]], dtype=float)
        v = np.array([10.0, 10.0])
        r = debt_rank(L, v, shocked_nodes={0: 1.0})
        assert 0.0 <= r.R <= 1.0 + 1e-9

    def test_raises_on_non_positive_v(self):
        L = np.zeros((2, 2))
        v = np.array([100.0, 0.0])
        with pytest.raises(ValueError, match="strictly positive"):
            debt_rank(L, v, shocked_nodes={0: 1.0})

    def test_raises_on_empty_shocked_nodes(self):
        L = np.zeros((2, 2))
        v = np.array([100.0, 80.0])
        with pytest.raises(ValueError, match="non-empty"):
            debt_rank(L, v, shocked_nodes={})

    def test_impacted_fraction(self):
        L, v = _simple_net()
        r = debt_rank(L, v, shocked_nodes={0: 1.0})
        # All 3 nodes end up with h > 0
        assert r.impacted_fraction == pytest.approx(1.0)


class TestDebtRankVsEN:
    """Consistency: both agree on the qualitative direction of defaults."""

    def test_same_network_both_show_cascade(self):
        from mimic_world.contagion.eisenberg_noe import eisenberg_noe_clearing

        L = np.array([
            [0, 80,  0],
            [0,  0, 60],
            [50,  0,  0],
        ], dtype=float)
        e = np.array([5.0, 5.0, 5.0])
        v = np.array([100.0, 80.0, 60.0])

        en = eisenberg_noe_clearing(L, e)
        dr = debt_rank(L, v, shocked_nodes={0: 1.0})

        # Both should detect systemic distress
        assert np.any(en.defaulted)
        assert dr.R > 0.1
