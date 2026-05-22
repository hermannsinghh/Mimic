"""Tests for the audit-grade refusal contract.

ADR 2026-05-21-audit-grade-refusal: non-deterministic persona_builder +
frozen-run off + audit_grade=True → ScenarioRunner raises FrozenRunRequired.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from mimic.framework.policy import PolicyDecisionPoint, load_bundle
from mimic.framework.scenario import (
    FrozenRunRequired,
    ScenarioRunner,
    deterministic_stub_personas,
    load_spec,
)
from mimic.framework.scenario.runner import _is_deterministic

_SVB = Path(__file__).resolve().parents[4] / "scenarios" / "svb-replay-2023"
_BUNDLE = Path(__file__).resolve().parents[2] / "policy" / "opa"


def _toy_network():
    return {
        "schema": "mimic.world.liability/v1",
        "entities": [
            {"iri": "https://example.com/svb", "name": "SVB",
             "equity": 16e9, "total_assets": 209e9},
            {"iri": "https://example.com/fhlb", "name": "FHLB",
             "equity": 50e9, "total_assets": 1e12},
        ],
        "exposures": [{"debtor_iri": "https://example.com/svb",
                       "creditor_iri": "https://example.com/fhlb",
                       "amount": 14e9}],
    }


@pytest.fixture
def pdp():
    return PolicyDecisionPoint(load_bundle(_BUNDLE))


@pytest.fixture
def spec():
    return load_spec(_SVB / "scenario.yaml")


@pytest.fixture
def _no_frozen_run(monkeypatch):
    monkeypatch.delenv("MIMIC_FROZEN_RUN", raising=False)


def _undeclared_builder(scenario_ctx):
    """Bare callable — no is_deterministic attribute. Treated as non-deterministic."""
    return []


def _non_deterministic_builder(scenario_ctx):
    return []
_non_deterministic_builder.is_deterministic = False  # type: ignore[attr-defined]


def test_deterministic_stub_is_marked_deterministic():
    assert _is_deterministic(deterministic_stub_personas) is True


def test_bare_callable_defaults_to_non_deterministic():
    assert _is_deterministic(_undeclared_builder) is False


def test_refuses_non_deterministic_without_frozen_run(pdp, spec, _no_frozen_run):
    runner = ScenarioRunner(pdp=pdp, persona_builder=_non_deterministic_builder)
    with pytest.raises(FrozenRunRequired) as exc:
        runner.run(spec, liability_network=_toy_network())
    msg = str(exc.value)
    assert "MIMIC_FROZEN_RUN" in msg
    assert "audit_grade=False" in msg
    assert "2026-05-21-audit-grade-refusal" in msg


def test_refuses_bare_callable_without_frozen_run(pdp, spec, _no_frozen_run):
    """Default-safe: an undeclared builder gets the same treatment as non-deterministic."""
    runner = ScenarioRunner(pdp=pdp, persona_builder=_undeclared_builder)
    with pytest.raises(FrozenRunRequired):
        runner.run(spec, liability_network=_toy_network())


def test_deterministic_builder_runs_in_audit_mode(pdp, spec, _no_frozen_run):
    runner = ScenarioRunner(pdp=pdp, persona_builder=deterministic_stub_personas)
    m = runner.run(spec, liability_network=_toy_network())
    assert m.world_state_hash_initial is not None
    assert m.world_state_hash_final is not None
    assert m.audit_grade is True


def test_frozen_run_unblocks_non_deterministic_builder(pdp, spec, monkeypatch):
    monkeypatch.setenv("MIMIC_FROZEN_RUN", "1")
    runner = ScenarioRunner(pdp=pdp, persona_builder=_non_deterministic_builder)
    m = runner.run(spec, liability_network=_toy_network())
    assert m.world_state_hash_initial is not None
    assert m.world_state_hash_final is not None
    assert m.audit_grade is True


def test_audit_grade_false_runs_but_emits_no_hash(pdp, spec, _no_frozen_run):
    runner = ScenarioRunner(
        pdp=pdp,
        persona_builder=_non_deterministic_builder,
        audit_grade=False,
    )
    m = runner.run(spec, liability_network=_toy_network())
    assert m.audit_grade is False
    assert m.world_state_hash_initial is None
    assert m.world_state_hash_final is None
    # but everything else is present
    assert m.spec_hash is not None
    assert m.policy_version is not None
    assert m.signature is None  # no hash to sign


def test_signer_only_signs_in_audit_grade_mode(pdp, spec, _no_frozen_run):
    from mimic.framework.scenario import LocalDevSigner
    signer = LocalDevSigner.generate()
    runner = ScenarioRunner(
        pdp=pdp,
        persona_builder=_non_deterministic_builder,
        signer=signer,
        audit_grade=False,
    )
    m = runner.run(spec, liability_network=_toy_network())
    # explicit downgrade — even with a signer present, no signature emitted
    assert m.signature is None
