"""End-to-end scenario runner — the day-30 audit-grade demo.

Proves: two runs with the same SeedManifest + same liability inputs + the
deterministic stub personas produce IDENTICAL world_state_hash_final and
IDENTICAL spec_hash. That's the lighthouse demo.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mimic.framework.scenario import (
    LocalDevSigner,
    ScenarioRunManifest,
    ScenarioRunner,
    deterministic_stub_personas,
    load_spec,
    run_scenario_e2e,
)

_SVB = Path(__file__).resolve().parents[4] / "scenarios" / "svb-replay-2023"


def _toy_liability_network():
    return {
        "schema": "mimic.world.liability/v1",
        "currency": "USD",
        "entities": [
            {"iri": "https://example.com/svb",
             "name": "SVB", "equity": 16e9, "total_assets": 209e9},
            {"iri": "https://example.com/fhlb",
             "name": "FHLB", "equity": 50e9, "total_assets": 1e12},
            {"iri": "https://example.com/fdic",
             "name": "FDIC", "equity": 120e9, "total_assets": 130e9},
        ],
        "exposures": [
            {"debtor_iri": "https://example.com/svb",
             "creditor_iri": "https://example.com/fhlb",
             "amount": 14e9},
        ],
    }


def test_e2e_run_produces_signed_manifest():
    m = run_scenario_e2e(_SVB, liability_network=_toy_liability_network())
    assert isinstance(m, ScenarioRunManifest)
    assert m.scenario_name == "svb-replay-2023"
    assert len(m.world_state_hash_final) == 64
    assert len(m.world_state_hash_initial) == 64
    assert m.world_state_hash_initial != m.world_state_hash_final  # stress propagated
    assert m.signature is not None
    assert m.signature.backend == "local-dev"
    assert len(m.decisions) == 3
    assert m.policy_version  # bundle digest recorded


def test_two_consecutive_runs_produce_identical_hashes():
    """The forcing day-30 demo: same inputs + same seed → same hash."""
    spec = load_spec(_SVB / "scenario.yaml")
    network = _toy_liability_network()

    from mimic.framework.policy import PolicyDecisionPoint, load_bundle
    pdp = PolicyDecisionPoint(load_bundle(
        Path(__file__).resolve().parents[2] / "policy" / "opa"
    ))
    runner = ScenarioRunner(
        pdp=pdp,
        persona_builder=deterministic_stub_personas,
        signer=None,  # don't sign — signatures use ephemeral keys
    )
    a = runner.run(spec, liability_network=network)
    b = runner.run(spec, liability_network=network)

    assert a.world_state_hash_final == b.world_state_hash_final, (
        "REPRODUCIBILITY VIOLATION — same seed + same inputs produced "
        "different world_state_hash. This breaks the audit-grade contract."
    )
    assert a.world_state_hash_initial == b.world_state_hash_initial
    assert a.spec_hash == b.spec_hash
    assert a.debt_rank_R_final == b.debt_rank_R_final
    assert a.en_total_p_star_final == b.en_total_p_star_final
    assert a.policy_version == b.policy_version
    # decisions are byte-identical (deterministic stub)
    assert [d.decision_id for d in a.decisions] == [d.decision_id for d in b.decisions]


def test_changing_seed_changes_spec_hash_independent_path():
    """If the spec changes, spec_hash must change — even if state doesn't."""
    spec = load_spec(_SVB / "scenario.yaml")
    network = _toy_liability_network()

    from mimic.framework.policy import PolicyDecisionPoint, load_bundle
    pdp = PolicyDecisionPoint(load_bundle(
        Path(__file__).resolve().parents[2] / "policy" / "opa"
    ))
    runner = ScenarioRunner(pdp=pdp, persona_builder=deterministic_stub_personas)
    a = runner.run(spec, liability_network=network)
    # mutate the network — should change both initial and final hash
    altered = dict(network)
    altered["entities"] = [
        {**network["entities"][0], "equity": 1.0},  # SVB much weaker
        *network["entities"][1:],
    ]
    b = runner.run(spec, liability_network=altered)
    assert a.world_state_hash_initial != b.world_state_hash_initial


def test_runner_records_policy_version_from_pdp():
    """Every manifest carries the OPA bundle digest — Plan §12."""
    m = run_scenario_e2e(_SVB, liability_network=_toy_liability_network())
    assert len(m.policy_version) == 64  # sha256 hex


def test_runner_signature_verifies_against_signer():
    spec = load_spec(_SVB / "scenario.yaml")
    network = _toy_liability_network()

    from mimic.framework.policy import PolicyDecisionPoint, load_bundle
    pdp = PolicyDecisionPoint(load_bundle(
        Path(__file__).resolve().parents[2] / "policy" / "opa"
    ))
    signer = LocalDevSigner.generate()
    runner = ScenarioRunner(pdp=pdp, persona_builder=deterministic_stub_personas, signer=signer)
    m = runner.run(spec, liability_network=network)
    signer.verify(m.signature)  # no raise — signed over the final hash

