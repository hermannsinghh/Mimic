"""End-to-end: record cassettes against a stub provider, then replay them
under frozen-run mode with ``audit_grade=True`` and confirm:

  * the inner provider is never called during replay;
  * the runner emits both ``world_state_hash_initial`` and
    ``world_state_hash_final`` from the cached responses;
  * decision counts and policy_version match across record and replay.

This is the scenario-level analogue of the provider-level tests in
``tests/determinism/test_recording_provider.py``. It exists because
``ConcordiaPersonaBuilder`` wires the cassette infrastructure through
*two* call paths in one scenario (the Concordia LM adapter for agent
reasoning + the prefab cascade for structured emission), and we want a
regression that fails loudly if either path drifts from the cache-key
contract.

The test does NOT use ``mimic-concordia`` lazily — it imports
``ConcordiaPersonaBuilder`` eagerly. If concordia is missing the test is
skipped with a clear reason.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

try:
    from mimic.framework.agents.concordia_runtime import ConcordiaPersonaBuilder
    _CONCORDIA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CONCORDIA_AVAILABLE = False

from mimic.framework.agents.prefabs import ReinsurerTreatyPricer
from mimic.framework.determinism import (
    FrozenRunProvider,
    LocalFSBackend,
    RecordingProvider,
)
from mimic.framework.policy import PolicyDecisionPoint, load_bundle
from mimic.framework.routing import (
    RoutingCascade,
    StructuredResponse,
    compute_model_fingerprint,
)
from mimic.framework.scenario import ScenarioRunner, load_spec

pytestmark = pytest.mark.skipif(
    not _CONCORDIA_AVAILABLE,
    reason="mimic-concordia not installed; install with mimic-framework[concordia]",
)

_SVB = Path(__file__).resolve().parents[4] / "scenarios" / "svb-replay-2023"
_BUNDLE = Path(__file__).resolve().parents[2] / "policy" / "opa"


class _StubInner:
    """Pretends to be Claude. Returns a context-appropriate JSON shape."""

    provider_name = "anthropic"
    model_name = "claude-opus-4-5"
    model_version = "2026-04-test"

    def __init__(self) -> None:
        self.calls = 0

    def estimate_cost_usd(self, i: int, o: int) -> float:
        return 0.0

    def complete(self, *, messages, schema, tools, temperature, seed, system_prompt=""):
        self.calls += 1
        sp = (system_prompt or "").lower()
        if "reinsur" in sp or "treaty" in sp:
            content: dict[str, Any] = {
                "action": "hold", "premium_usd": 0.0, "retention_usd": 0.0,
                "confidence": 0.7, "rationale": "stub",
            }
        else:
            content = {"text": "I would proceed cautiously.", "confidence": 0.7}
        return StructuredResponse(
            content=content, input_tokens=10, output_tokens=5, cost_usd=0.0,
            confidence=float(content.get("confidence", 0.7)),
            model_fingerprint=compute_model_fingerprint(
                provider=self.provider_name, model=self.model_name,
                version=self.model_version, system_prompt=system_prompt,
                temperature=temperature, tool_schema=tools[0] if tools else None,
            ),
        )


class _RaisingInner:
    """Used during replay; must never be called."""

    provider_name = "anthropic"
    model_name = "claude-opus-4-5"
    model_version = "2026-04-test"

    def estimate_cost_usd(self, i: int, o: int) -> float:
        return 0.0

    def complete(self, **kwargs):
        raise AssertionError(
            "replay must not invoke the inner provider — frozen-run cache miss "
            "indicates record/replay key drift"
        )


def _toy_net() -> dict:
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


def _build_runner(provider, *, audit_grade: bool) -> ScenarioRunner:
    pdp = PolicyDecisionPoint(load_bundle(_BUNDLE))
    cascade = RoutingCascade(t3=None, t2_a=None, t1=provider, max_cost_usd=50.0)
    prefab = ReinsurerTreatyPricer(cascade=cascade, pdp=pdp)
    builder = ConcordiaPersonaBuilder(prefab=prefab, llm_provider=provider)
    return ScenarioRunner(pdp=pdp, persona_builder=builder, audit_grade=audit_grade)


def test_record_then_replay_full_runner(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("MIMIC_FROZEN_RUN", raising=False)
    spec = load_spec(_SVB / "scenario.yaml")
    net = _toy_net()

    # ── record pass ────────────────────────────────────────────────────
    inner = _StubInner()
    recorder = RecordingProvider(inner, LocalFSBackend(tmp_path))
    rec_runner = _build_runner(recorder, audit_grade=False)
    rec_manifest = rec_runner.run(spec, liability_network=net)
    assert recorder.recorded_count > 0
    assert rec_manifest.audit_grade is False
    assert rec_manifest.world_state_hash_initial is None
    assert rec_manifest.world_state_hash_final is None
    assert len(rec_manifest.decisions) == 2

    cassettes = list(tmp_path.glob("*.json"))
    assert len(cassettes) == recorder.recorded_count, "every recorded call → one cassette"

    # ── replay pass (audit-grade) ──────────────────────────────────────
    monkeypatch.setenv("MIMIC_FROZEN_RUN", "1")
    frozen = FrozenRunProvider(_RaisingInner(), LocalFSBackend(tmp_path))
    play_runner = _build_runner(frozen, audit_grade=True)
    play_manifest = play_runner.run(spec, liability_network=net)

    assert play_manifest.audit_grade is True
    assert play_manifest.world_state_hash_initial is not None
    assert play_manifest.world_state_hash_final is not None
    assert len(play_manifest.decisions) == 2
    assert play_manifest.policy_version == rec_manifest.policy_version
    assert play_manifest.spec_hash == rec_manifest.spec_hash


def test_replay_is_reproducible_across_runs(tmp_path, monkeypatch) -> None:
    """Two consecutive frozen-run replays MUST produce identical hashes —
    that's the day-30 demo invariant, now proven through ConcordiaPersonaBuilder."""
    monkeypatch.delenv("MIMIC_FROZEN_RUN", raising=False)
    spec = load_spec(_SVB / "scenario.yaml")
    net = _toy_net()

    # prime cassettes
    inner = _StubInner()
    rec = RecordingProvider(inner, LocalFSBackend(tmp_path))
    _build_runner(rec, audit_grade=False).run(spec, liability_network=net)

    # replay twice
    monkeypatch.setenv("MIMIC_FROZEN_RUN", "1")
    runs = []
    for _ in range(2):
        frozen = FrozenRunProvider(_RaisingInner(), LocalFSBackend(tmp_path))
        runs.append(_build_runner(frozen, audit_grade=True).run(spec, liability_network=net))

    assert runs[0].world_state_hash_initial == runs[1].world_state_hash_initial
    assert runs[0].world_state_hash_final == runs[1].world_state_hash_final
    assert runs[0].spec_hash == runs[1].spec_hash
    assert runs[0].policy_version == runs[1].policy_version
    assert [d.action_type for d in runs[0].decisions] == [d.action_type for d in runs[1].decisions]
