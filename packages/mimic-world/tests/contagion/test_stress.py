"""Tests for combined stress propagation — Plan §3.3 W-05."""
from __future__ import annotations

import numpy as np
import pytest

from mimic_world.contagion import (
    LiabilityNetwork,
    PersonaAction,
    StressResult,
    apply_actions_to_external_assets,
    from_fibo_dict,
    propagate_stress,
)


def _toy_network():
    net = LiabilityNetwork()
    net.add_node("A", equity=20.0, total_assets=200.0)
    net.add_node("B", equity=15.0, total_assets=150.0)
    net.add_node("C", equity=8.0, total_assets=80.0)
    net.add_bilateral_exposure("A", "B", 10.0)
    net.add_bilateral_exposure("B", "C", 8.0)
    net.add_bilateral_exposure("C", "A", 5.0)
    L, v, names = net.to_matrix()
    e = net.external_assets()
    return L, e, v, names


def test_apply_actions_modifies_only_named_nodes():
    L, e, v, names = _toy_network()
    actions = [
        PersonaAction("A", "raise_capital", quantity_usd=50.0, confidence=0.9),
        PersonaAction("C", "cut_exposure",  quantity_usd=20.0, confidence=0.8),
        PersonaAction("ghost", "hedge",     quantity_usd=99.0, confidence=0.9),
    ]
    out = apply_actions_to_external_assets(e, names, actions)
    assert out[names.index("A")] == e[names.index("A")] + 50.0
    assert out[names.index("C")] == e[names.index("C")] - 20.0
    assert out[names.index("B")] == e[names.index("B")]
    # ghost action ignored — vector should still sum correctly
    assert out.sum() == e.sum() + 50.0 - 20.0


def test_hold_actions_are_no_ops():
    L, e, v, names = _toy_network()
    actions = [
        PersonaAction("A", "hold",   quantity_usd=1e9, confidence=0.9),
        PersonaAction("B", "buy",    quantity_usd=1e9, confidence=0.9),
        PersonaAction("C", "retain", quantity_usd=1e9, confidence=0.9),
    ]
    out = apply_actions_to_external_assets(e, names, actions)
    np.testing.assert_array_equal(out, e)


def test_propagate_stress_runs_all_four_engines():
    L, e, v, names = _toy_network()
    actions = [
        PersonaAction("A", "raise_capital", quantity_usd=30.0, confidence=0.9),
    ]
    result = propagate_stress(L, e, v, names, actions)
    assert isinstance(result, StressResult)
    assert result.baseline_en.converged
    assert result.overlaid_en.converged
    assert result.baseline_debt_rank.converged
    assert result.overlaid_debt_rank.converged
    assert result.actions_applied == tuple(actions)


def test_raise_capital_reduces_defaults():
    """A meaningful capital raise should reduce node A's default shortfall."""
    L, e, v, names = _toy_network()
    # heavy A overhang scenario — make A insolvent
    e_thin = np.array([0.0, 15.0, 8.0])
    base = propagate_stress(L, e_thin, v, names, [])
    rescued = propagate_stress(
        L, e_thin, v, names,
        [PersonaAction("A", "raise_capital", quantity_usd=20.0, confidence=0.95)],
    )
    a_idx = names.index("A")
    assert rescued.overlaid_en.p_star[a_idx] >= base.overlaid_en.p_star[a_idx]


def test_cut_exposure_can_make_things_worse():
    """Cutting external assets reduces the EN inflow — overlaid p_star should drop."""
    L, e, v, names = _toy_network()
    result = propagate_stress(
        L, e, v, names,
        [PersonaAction("A", "cut_exposure", quantity_usd=15.0, confidence=0.85)],
    )
    assert result.delta_p_star[names.index("A")] <= 0


def test_propagate_stress_emits_delta_R():
    L, e, v, names = _toy_network()
    result = propagate_stress(L, e, v, names, [])
    # baseline run only — both DR runs use the same shock, so delta_R should be 0
    assert result.delta_R == 0.0


def test_propagate_stress_works_on_fibo_built_network():
    doc = {
        "schema": "mimic.world.liability/v1",
        "entities": [
            {"iri": "x:a", "equity": 10, "total_assets": 100},
            {"iri": "x:b", "equity": 5,  "total_assets": 50},
        ],
        "exposures": [{"debtor_iri": "x:a", "creditor_iri": "x:b", "amount": 8}],
    }
    net = from_fibo_dict(doc)
    L, v, names = net.to_matrix()
    e = net.external_assets()
    result = propagate_stress(
        L, e, v, names,
        [PersonaAction("x:a", "hedge", quantity_usd=2.0, confidence=0.9)],
    )
    assert result.overlaid_en.converged
