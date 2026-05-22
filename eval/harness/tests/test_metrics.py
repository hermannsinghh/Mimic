"""Tests for the eval harness metrics — Plan §11.1."""
from __future__ import annotations

import numpy as np
import pytest

from eval.harness import crps, directional_accuracy, wasserstein1


# ── directional_accuracy ────────────────────────────────────────────────────

def test_directional_accuracy_perfect_alignment():
    assert directional_accuracy([1, -2, 3], [4, -5, 6]) == 1.0


def test_directional_accuracy_all_wrong():
    assert directional_accuracy([1, 1, 1], [-1, -1, -1]) == 0.0


def test_directional_accuracy_excludes_zero_truth():
    # only the 1st and 3rd truths matter; both correctly signed
    assert directional_accuracy([1, 99, -1], [1, 0, -1]) == 1.0


def test_directional_accuracy_shape_mismatch():
    with pytest.raises(ValueError):
        directional_accuracy([1, 2, 3], [1, 2])


def test_directional_accuracy_all_zero_truth():
    assert directional_accuracy([0, 0], [0, 0]) == 1.0
    assert directional_accuracy([1, 0], [0, 0]) == 0.0


# ── crps ────────────────────────────────────────────────────────────────────

def test_crps_zero_for_constant_correct_forecast():
    assert crps([5.0, 5.0, 5.0], truth=5.0) == pytest.approx(0.0, abs=1e-12)


def test_crps_positive_for_off_forecast():
    val = crps([5.0, 5.0, 5.0, 5.0], truth=10.0)
    assert val == pytest.approx(5.0, abs=1e-9)


def test_crps_lower_for_better_forecast():
    truth = 0.0
    sharp_correct = crps(np.zeros(100), truth=truth)
    broad = crps(np.linspace(-10, 10, 100), truth=truth)
    biased = crps(np.full(100, 5.0), truth=truth)
    assert sharp_correct < broad
    assert sharp_correct < biased


def test_crps_rejects_empty():
    with pytest.raises(ValueError):
        crps([], truth=0.0)


# ── wasserstein1 ────────────────────────────────────────────────────────────

def test_wasserstein1_identical_distributions():
    a = np.linspace(0, 1, 100)
    assert wasserstein1(a, a) == pytest.approx(0.0, abs=1e-12)


def test_wasserstein1_translated_distribution():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 5000)
    b = a + 3.0
    assert wasserstein1(a, b) == pytest.approx(3.0, abs=0.02)


def test_wasserstein1_unequal_sizes():
    rng = np.random.default_rng(1)
    a = rng.uniform(0, 1, 500)
    b = rng.uniform(0, 1, 1500)
    # both unit uniform — should be small
    assert wasserstein1(a, b) < 0.05


def test_wasserstein1_rejects_empty():
    with pytest.raises(ValueError):
        wasserstein1([], [1, 2])
