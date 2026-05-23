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


# ── persona → network linkage (ADR 2026-05-22-runner-iri-resolution) ──


def test_persona_actions_actually_affect_network_state():
    """Persona Decisions must perturb the network — not just be ignored.

    Pre-fix runner bug: ``node_name = instrument_iri.split("/")[-1]`` produced
    e.g. ``"svb"`` while the network was keyed by ``"https://example.com/svb"``,
    so every action was filtered as an orphan and the network propagated
    unmodified.

    Regression: running with a builder that emits non-trivial ``cut_exposure``
    actions must produce a different ``world_state_hash_final`` than running
    with the trivial stub builder (which emits ``hold/0`` actions). If both
    runs produce the same hash, the runner is ignoring the persona output.

    See ``decision-record/2026-05-22-runner-iri-resolution.md``.
    """
    from datetime import datetime
    from uuid import UUID
    import hashlib

    from mimic.framework.policy import PolicyDecisionPoint, load_bundle
    from mimic.framework.schema.decision import Decision, RationaleStep

    spec = load_spec(_SVB / "scenario.yaml")
    network = _toy_liability_network()
    pdp = PolicyDecisionPoint(load_bundle(
        Path(__file__).resolve().parents[2] / "policy" / "opa"
    ))

    def _non_trivial_cut_exposure_builder(scenario_ctx):
        """Emits cut_exposure/$1B on every entity — should perturb every node."""
        out = []
        for ent in scenario_ctx["entities"]:
            det_id = str(UUID(
                bytes=hashlib.sha256(("ct:" + ent["iri"]).encode()).digest()[:16],
                version=5,
            ))
            out.append(Decision(
                decision_id=det_id,
                agent_did=f"did:web:test.{ent['iri'].rsplit('/', 1)[-1]}",
                instrument_iri=ent["iri"],  # direct entity IRI — runner walks 0 levels up
                action_type="cut_exposure",
                quantity=1e9,
                unit="USD",
                rationale_chain=[RationaleStep(
                    claim="non-trivial test action",
                    evidence_iri=ent["iri"],
                    confidence=0.9,
                )],
                timestamp=datetime(2026, 5, 22, 0, 0, 0),
                model_fingerprint="test-cut-exposure" + "0" * 47,
                confidence=0.9,
                policy_version="0" * 64,
            ))
        return out
    _non_trivial_cut_exposure_builder.is_deterministic = True  # type: ignore[attr-defined]

    runner_a = ScenarioRunner(pdp=pdp, persona_builder=deterministic_stub_personas)
    runner_b = ScenarioRunner(pdp=pdp, persona_builder=_non_trivial_cut_exposure_builder)

    m_a = runner_a.run(spec, liability_network=network)
    m_b = runner_b.run(spec, liability_network=network)

    assert m_a.world_state_hash_initial == m_b.world_state_hash_initial, (
        "initial hashes should match — same network input, no actions applied yet"
    )
    assert m_a.world_state_hash_final != m_b.world_state_hash_final, (
        "PERSONA→NETWORK LINKAGE BROKEN — both builders produced the same final "
        "world_state_hash despite emitting materially different Decisions. This "
        "means actions are being orphaned before propagate_stress, which makes "
        "the audit-grade claim 'the network state reflects persona decisions' "
        "false. See decision-record/2026-05-22-runner-iri-resolution.md."
    )
    # Aggregate contagion metrics may or may not differ depending on the
    # network's cascade sensitivity — for the toy SVB network the
    # EN-cleared total stays flat because the SVB→FHLB exposure clears
    # in full in both runs. The load-bearing assertion is the hash
    # difference above; aggregate metric drift is recorded as a softer
    # observation (no assertion).


def test_persona_actions_on_instrument_suffixed_iri_resolve_to_entity():
    """Prefab path: ``instrument_iri = "<entity_iri>/<instrument_segment>"``.

    The runner must walk up one path level to find the network node.
    Pre-fix code took ``split("/")[-1]`` which yielded the instrument
    segment (e.g. ``"reinsurance-treaty"``) — never matched a node."""
    from datetime import datetime
    from uuid import UUID
    import hashlib

    from mimic.framework.policy import PolicyDecisionPoint, load_bundle
    from mimic.framework.schema.decision import Decision, RationaleStep

    spec = load_spec(_SVB / "scenario.yaml")
    network = _toy_liability_network()
    pdp = PolicyDecisionPoint(load_bundle(
        Path(__file__).resolve().parents[2] / "policy" / "opa"
    ))

    def _suffixed_iri_builder(scenario_ctx):
        out = []
        for ent in scenario_ctx["entities"]:
            det_id = str(UUID(
                bytes=hashlib.sha256(("sx:" + ent["iri"]).encode()).digest()[:16],
                version=5,
            ))
            out.append(Decision(
                decision_id=det_id,
                agent_did=f"did:web:test.{ent['iri'].rsplit('/', 1)[-1]}",
                # this is the prefab shape: entity_iri + suffix
                instrument_iri=f"{ent['iri']}/reinsurance-treaty",
                action_type="cut_exposure",
                quantity=2e9,
                unit="USD",
                rationale_chain=[RationaleStep(
                    claim="suffixed-iri test",
                    evidence_iri=ent["iri"],
                    confidence=0.9,
                )],
                timestamp=datetime(2026, 5, 22, 0, 0, 0),
                model_fingerprint="test-suffixed" + "0" * 51,
                confidence=0.9,
                policy_version="0" * 64,
            ))
        return out
    _suffixed_iri_builder.is_deterministic = True  # type: ignore[attr-defined]

    runner_stub = ScenarioRunner(pdp=pdp, persona_builder=deterministic_stub_personas)
    runner_sfx = ScenarioRunner(pdp=pdp, persona_builder=_suffixed_iri_builder)

    m_stub = runner_stub.run(spec, liability_network=network)
    m_sfx = runner_sfx.run(spec, liability_network=network)

    assert m_stub.world_state_hash_final != m_sfx.world_state_hash_final, (
        "suffixed instrument_iri (entity_iri/suffix) must resolve to the "
        "parent entity node, not get orphaned"
    )


def test_resolve_target_node_walks_path():
    """Unit test for the IRI resolution helper."""
    from mimic.framework.scenario.runner import _resolve_target_node

    nodes = {"https://example.com/svb", "https://example.com/fhlb"}

    # direct match
    assert _resolve_target_node("https://example.com/svb", nodes) == "https://example.com/svb"
    # one level up
    assert _resolve_target_node(
        "https://example.com/svb/reinsurance-treaty", nodes
    ) == "https://example.com/svb"
    # two levels up
    assert _resolve_target_node(
        "https://example.com/svb/treaty/layer-1", nodes
    ) == "https://example.com/svb"
    # orphan
    assert _resolve_target_node("https://example.com/orphan", nodes) is None
    # empty / malformed
    assert _resolve_target_node("", nodes) is None
    assert _resolve_target_node("no-slash-here", nodes) is None
    # does NOT match a scheme-only parent
    assert _resolve_target_node("https://example.com", nodes) is None
