"""Tests for the FIBO-shaped network builder — Plan §3.3 W-04."""
from __future__ import annotations

import json

import numpy as np
import pytest

from mimic_world.contagion import (
    FIBOValidationError,
    eisenberg_noe_clearing,
    from_fibo_dict,
    from_fibo_json,
)


def _svb_like_doc():
    return {
        "schema": "mimic.world.liability/v1",
        "currency": "USD",
        "entities": [
            {
                "iri": "https://example.com/svb",
                "name": "SVB",
                "type": "fibo-fbc-fct-fse:FinancialInstitution",
                "equity": 16e9,
                "total_assets": 209e9,
            },
            {
                "iri": "https://example.com/fhlb",
                "name": "FHLB",
                "type": "fibo-fbc-fct-fse:FinancialInstitution",
                "equity": 50e9,
                "total_assets": 1e12,
            },
        ],
        "exposures": [
            {
                "debtor_iri": "https://example.com/svb",
                "creditor_iri": "https://example.com/fhlb",
                "amount": 14e9,
                "instrument_iri": "fibo-fbc-dae-dbt:DebtInstrument",
            }
        ],
    }


def test_from_fibo_dict_builds_network():
    net = from_fibo_dict(_svb_like_doc())
    names = net.node_names()
    assert set(names) == {"https://example.com/svb", "https://example.com/fhlb"}
    L, v, ordered = net.to_matrix()
    svb_idx = ordered.index("https://example.com/svb")
    fhlb_idx = ordered.index("https://example.com/fhlb")
    assert L[svb_idx, fhlb_idx] == 14e9
    assert L[fhlb_idx, svb_idx] == 0


def test_built_network_runs_through_en_clearing():
    net = from_fibo_dict(_svb_like_doc())
    L, _, _ = net.to_matrix()
    e = net.external_assets()
    r = eisenberg_noe_clearing(L, e)
    assert r.converged
    # SVB owes 14e9; equity 16e9 covers it without inflow, so should pay in full.
    np.testing.assert_allclose(r.p_star.sum(), 14e9, atol=1e-3)


def test_rejects_unknown_schema():
    doc = _svb_like_doc()
    doc["schema"] = "rolled-my-own/v0"
    with pytest.raises(FIBOValidationError, match="unsupported schema"):
        from_fibo_dict(doc)


def test_rejects_missing_entity_field():
    doc = _svb_like_doc()
    del doc["entities"][0]["equity"]
    with pytest.raises(FIBOValidationError, match="missing required field 'equity'"):
        from_fibo_dict(doc)


def test_rejects_duplicate_iri():
    doc = _svb_like_doc()
    doc["entities"].append(doc["entities"][0])
    with pytest.raises(FIBOValidationError, match="duplicate entity IRI"):
        from_fibo_dict(doc)


def test_rejects_dangling_exposure():
    doc = _svb_like_doc()
    doc["exposures"][0]["creditor_iri"] = "https://example.com/ghost"
    with pytest.raises(FIBOValidationError, match="unknown creditor IRI"):
        from_fibo_dict(doc)


def test_from_fibo_json_round_trip(tmp_path):
    doc = _svb_like_doc()
    p = tmp_path / "net.json"
    p.write_text(json.dumps(doc))
    net = from_fibo_json(p)
    assert set(net.node_names()) == {
        "https://example.com/svb",
        "https://example.com/fhlb",
    }


def test_empty_exposures_allowed():
    doc = {
        "schema": "mimic.world.liability/v1",
        "entities": [
            {"iri": "a", "equity": 10, "total_assets": 100},
            {"iri": "b", "equity": 5, "total_assets": 50},
        ],
        "exposures": [],
    }
    net = from_fibo_dict(doc)
    L, _, _ = net.to_matrix()
    assert L.sum() == 0
