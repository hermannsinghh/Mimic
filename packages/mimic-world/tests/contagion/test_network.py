"""Tests for LiabilityNetwork — Plan §3.3 W-04."""
from __future__ import annotations

import numpy as np
import pytest

from mimic_world.contagion.network import LiabilityNetwork


class TestLiabilityNetworkBasic:
    def test_empty_network(self):
        net = LiabilityNetwork()
        net.add_node("A", equity=10.0, total_assets=100.0)
        L, v, names = net.to_matrix()
        assert L.shape == (1, 1)
        assert L[0, 0] == 0.0
        assert v[0] == 100.0
        assert names == ["A"]

    def test_bilateral_exposure(self):
        net = LiabilityNetwork()
        net.add_node("A", equity=50.0, total_assets=200.0)
        net.add_node("B", equity=30.0, total_assets=150.0)
        net.add_bilateral_exposure("A", "B", 10.0)

        L, v, names = net.to_matrix()
        assert names == ["A", "B"]
        assert L[0, 1] == 10.0   # A owes B
        assert L[1, 0] == 0.0    # B owes A nothing yet

    def test_mutual_exposures(self):
        net = LiabilityNetwork()
        net.add_node("A", equity=50.0, total_assets=200.0)
        net.add_node("B", equity=30.0, total_assets=150.0)
        net.add_bilateral_exposure("A", "B", 10.0)
        net.add_bilateral_exposure("B", "A", 8.0)

        L, v, names = net.to_matrix()
        assert L[0, 1] == 10.0
        assert L[1, 0] == 8.0

    def test_external_assets_equity(self):
        net = LiabilityNetwork()
        net.add_node("A", equity=50.0, total_assets=200.0)
        net.add_node("B", equity=30.0, total_assets=150.0)
        e = net.external_assets()
        np.testing.assert_allclose(e, [50.0, 30.0])

    def test_duplicate_node_raises(self):
        net = LiabilityNetwork()
        net.add_node("A", equity=50.0, total_assets=200.0)
        with pytest.raises(ValueError, match="already registered"):
            net.add_node("A", equity=10.0, total_assets=100.0)

    def test_unknown_node_raises(self):
        net = LiabilityNetwork()
        net.add_node("A", equity=50.0, total_assets=200.0)
        with pytest.raises(ValueError, match="Unknown debtor"):
            net.add_bilateral_exposure("Z", "A", 5.0)

    def test_negative_exposure_raises(self):
        net = LiabilityNetwork()
        net.add_node("A", equity=50.0, total_assets=200.0)
        net.add_node("B", equity=30.0, total_assets=150.0)
        with pytest.raises(ValueError, match="non-negative"):
            net.add_bilateral_exposure("A", "B", -1.0)

    def test_fibo_iri_stored(self):
        net = LiabilityNetwork()
        net.add_node("A", equity=50.0, total_assets=200.0,
                     fibo_iri="https://spec.edmcouncil.org/fibo/ontology/FBC/FunctionalEntities/FinancialServicesEntities/Bank")
        assert net._nodes["A"].fibo_iri is not None

    def test_en_pipeline(self):
        from mimic_world.contagion.eisenberg_noe import eisenberg_noe_clearing

        net = LiabilityNetwork()
        net.add_node("A", equity=20.0, total_assets=100.0)
        net.add_node("B", equity=15.0, total_assets=80.0)
        net.add_bilateral_exposure("A", "B", 5.0)
        net.add_bilateral_exposure("B", "A", 3.0)

        L, _v, _names = net.to_matrix()
        e = net.external_assets()
        r = eisenberg_noe_clearing(L, e)

        assert r.converged
        assert not np.any(r.defaulted)   # both solvent
