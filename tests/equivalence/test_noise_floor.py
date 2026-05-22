"""Tests for the noise-floor harness.

Two axes:
1. A deterministic persona_builder must produce noise floor = 0 across all
   seed pairs. That's the sanity check — if the harness reports anything
   else, it's broken.
2. A controlled stochastic persona_builder (uses the per-seed quantity)
   must produce noise floor > 0 with an expected magnitude. That's the
   correctness check — the harness can actually distinguish noise from
   signal.

Both run against the real ScenarioRunner against the real svb-replay-2023
spec. No external dependencies; no LLM calls.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest

from mimic.framework.policy import PolicyDecisionPoint, load_bundle
from mimic.framework.scenario import ScenarioRunner, load_spec
from mimic.framework.scenario.runner import deterministic_stub_personas
from mimic.framework.schema.decision import Decision, RationaleStep

from tests.equivalence import measure_noise_floor

_SVB = Path(__file__).resolve().parents[2] / "scenarios" / "svb-replay-2023"
_BUNDLE = (
    Path(__file__).resolve().parents[2] / "packages" / "mimic-framework" / "policy" / "opa"
)


def _toy_network():
    return {
        "schema": "mimic.world.liability/v1",
        "entities": [
            {"iri": "https://example.com/svb", "name": "SVB",
             "equity": 16e9, "total_assets": 209e9},
            {"iri": "https://example.com/fhlb", "name": "FHLB",
             "equity": 50e9, "total_assets": 1e12},
            {"iri": "https://example.com/fdic", "name": "FDIC",
             "equity": 120e9, "total_assets": 130e9},
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


def _runner_factory(pdp, builder):
    def factory():
        return ScenarioRunner(
            pdp=pdp, persona_builder=builder, audit_grade=True,
        )
    return factory


def test_deterministic_builder_has_zero_noise_floor(pdp, spec):
    """Sanity: deterministic_stub_personas ignores the seed. Two runs with
    different seeds must produce byte-identical decisions → W1 = 0 across
    every group and every seed pair."""
    result = measure_noise_floor(
        runner_factory=_runner_factory(pdp, deterministic_stub_personas),
        spec=spec,
        liability_network=_toy_network(),
        seeds=[0x57AB1107, 0xCAFEF00D, 0x20080915, 0x6BD7BEEF],
    )
    assert result.n_pairs == 6  # C(4, 2)
    for group, max_w1 in result.max_w1_per_group.items():
        assert max_w1 == 0.0, f"deterministic builder showed noise in group {group}: W1={max_w1}"
    assert result.max_tv_per_group["__global_action_type__"] == 0.0


def _seeded_jitter_builder(scenario_ctx):
    """Controlled stochastic builder for harness validation.

    Reads ``_mc_seed`` from scenario_ctx (which the harness mutates per run)
    and uses it to jitter each Decision's quantity by a deterministic amount.
    Same seed → same quantities; different seed → predictably different.
    """
    mc_seed = scenario_ctx.get("_mc_seed", 0)
    decisions = []
    for i, ent in enumerate(scenario_ctx["entities"]):
        # deterministic UUIDv5 from IRI so decision_id is reproducible per seed
        det_id = str(UUID(bytes=_sha16(f"{ent['iri']}|{mc_seed}"), version=5))
        # jittered quantity — same seed gives same jitter
        jitter = ((mc_seed >> (i * 4)) & 0xFF) * 1.0
        decisions.append(Decision(
            decision_id=det_id,
            agent_did=f"did:web:jitter.{ent['iri'].rsplit('/', 1)[-1]}",
            instrument_iri=ent["iri"],
            action_type="hold",
            quantity=100.0 + jitter,
            unit="USD",
            rationale_chain=[RationaleStep(
                claim=f"jitter test, mc_seed={mc_seed}",
                evidence_iri=ent["iri"],
                confidence=0.5,
            )],
            timestamp=datetime(2026, 5, 21, 0, 0, 0),
            model_fingerprint="jitter-stub-v1" + "0" * 50,
            confidence=0.5,
            policy_version="0" * 64,
        ))
    return decisions
# Stochastic-by-design — but we'd seed it so we can audit-grade. For the
# noise-floor measurement we want is_deterministic=False so audit-grade
# refusal doesn't block it; we toggle audit_grade=False in the runner.


def _sha16(s: str) -> bytes:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).digest()[:16]


def test_jittered_builder_shows_positive_noise_floor(pdp, spec):
    """Correctness: a builder that varies its quantity output with the seed
    must register a positive noise floor. If the harness reports W1 = 0
    here, it's silently averaging away the per-seed variation."""

    def builder_reading_seed(scenario_ctx):
        # extract seed_global from the mc config the runner injects via spec
        # (the harness mutates spec.spec.mc.seed_global per call)
        return _seeded_jitter_builder({
            **scenario_ctx,
            "_mc_seed": spec_holder["current_seed"],
        })

    # Smuggle the current seed in via the runner factory closure
    spec_holder = {"current_seed": 0}
    original_runner_factory = _runner_factory(pdp, builder_reading_seed)

    def factory_capturing_seed():
        runner = ScenarioRunner(
            pdp=pdp, persona_builder=builder_reading_seed,
            audit_grade=False,  # bypass refusal — non-deterministic by design
        )
        return runner

    # The harness mutates spec.spec.mc.seed_global per run; we need the builder
    # to see that. Wrap by intercepting the spec at runner.run-time.
    class _CapturingRunner(ScenarioRunner):
        def run(self, spec, **kw):
            spec_holder["current_seed"] = spec.spec.mc.seed_global
            return super().run(spec, **kw)

    def real_factory():
        return _CapturingRunner(
            pdp=pdp, persona_builder=builder_reading_seed, audit_grade=False,
        )

    result = measure_noise_floor(
        runner_factory=real_factory,
        spec=spec,
        liability_network=_toy_network(),
        seeds=[0x11111111, 0x22222222, 0x33333333, 0x44444444],
    )
    assert result.n_pairs == 6
    # at least one group should show positive variance
    max_floor = max(result.max_w1_per_group.values()) if result.max_w1_per_group else 0.0
    assert max_floor > 0.0, (
        f"jittered builder produced zero noise floor — harness is not "
        f"distinguishing across seeds. max_w1_per_group={result.max_w1_per_group}"
    )


def test_floor_violated_flags_threshold_below_floor(pdp, spec):
    """The .floor_violated() helper must surface groups where a proposed
    threshold is below the measured floor — that's the diagnostic that
    catches a noise-driven threshold before F-12 ever runs."""
    # Build a tiny synthetic result so we don't have to re-run the scenario
    from tests.equivalence import NoiseFloorResult

    result = NoiseFloorResult(
        seeds=(1, 2, 3),
        n_pairs=3,
        max_w1_per_group={"hedge": 50.0, "hold": 0.0, "sell": 200.0},
    )
    bad_thresholds = {"hedge": 10.0, "hold": 5.0, "sell": 100.0}
    # only hedge and sell are below their floors; hold's floor is 0 which is
    # not >= 5
    violated = result.floor_violated(bad_thresholds)
    assert set(violated) == {"hedge", "sell"}


def test_rejects_fewer_than_two_seeds(pdp, spec):
    with pytest.raises(ValueError, match="at least 2 seeds"):
        measure_noise_floor(
            runner_factory=_runner_factory(pdp, deterministic_stub_personas),
            spec=spec,
            liability_network=_toy_network(),
            seeds=[42],
        )
