"""In-process scenario runner — the day-30 audit-grade demo.

Takes a scenario directory, runs personas (via Prefab cascade) → emits Decisions →
overlays them onto a LiabilityNetwork → propagates contagion (EN + DebtRank) →
hashes the final world state → signs the run manifest.

Two consecutive runs with the same SeedManifest + frozen LLM cache MUST produce
the same world_state_hash and the same signed manifest payload. That's the
forcing demo: a reinsurer's CRO replays from inputs and gets the same hash.

This runner does NOT require Temporal or a vendored Concordia. It exercises the
already-landed F-01/02/03/04/06/07/08/09 + W-01/02/04/05 contracts as one
composed pipeline. F-12 (real Concordia) and F-05 (Temporal worker) become
drop-in replacements for the persona-builder and the workflow harness, without
changing the contract surface this runner depends on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np

from ..determinism import SeedManifest, is_frozen_run, world_state_hash
from ..policy import PolicyDecisionPoint, load_bundle
from ..schema import Decision
from .signing import LocalDevSigner, Signature
from .spec import ScenarioSpec, load_spec


# ── PersonaBuilder protocol ──────────────────────────────────────────────────

PersonaBuilder = Callable[[dict], list[Decision]]
"""Given the scenario context (entities, event, mc config), return a list of
Decisions.

A PersonaBuilder is treated as *deterministic* only if it carries an
``is_deterministic = True`` attribute. Bare callables and lambdas default to
non-deterministic — see decision-record/2026-05-21-audit-grade-refusal.md.

Real prefabs (ReinsurerTreatyPricer, BankTreasuryALM, etc.) plug in here when
Concordia (F-12) lands. They declare ``is_deterministic = False`` because they
call an LLM; the runner then requires either ``MIMIC_FROZEN_RUN=1`` or an
explicit ``audit_grade=False`` opt-out."""


class FrozenRunRequired(RuntimeError):
    """Raised by ScenarioRunner when a non-deterministic persona_builder is
    used outside frozen-run mode without an explicit ``audit_grade=False`` opt-out.

    See decision-record/2026-05-21-audit-grade-refusal.md for the contract.
    """


def _is_deterministic(builder: PersonaBuilder) -> bool:
    return bool(getattr(builder, "is_deterministic", False))


# ── result types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScenarioRunManifest:
    """Output of one scenario run.

    When ``audit_grade=True`` (default), both ``world_state_hash_*`` fields are
    set. When the operator explicitly downgrades to ``audit_grade=False``, both
    are ``None`` — no hash without earning it.
    """
    scenario_name: str
    scenario_version: str
    spec_hash: str
    seed_manifest: SeedManifest
    decisions: tuple[Decision, ...]
    world_state_hash_initial: str | None
    world_state_hash_final: str | None
    debt_rank_R_initial: float
    debt_rank_R_final: float
    en_total_p_star_initial: float
    en_total_p_star_final: float
    policy_version: str
    audit_grade: bool = True
    signature: Signature | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── runner ──────────────────────────────────────────────────────────────────

class ScenarioRunner:
    """Compose all the audit-grade primitives into one in-process pipeline."""

    def __init__(
        self,
        *,
        pdp: PolicyDecisionPoint,
        persona_builder: PersonaBuilder,
        signer: LocalDevSigner | None = None,
        audit_grade: bool = True,
    ) -> None:
        self.pdp = pdp
        self.persona_builder = persona_builder
        self.signer = signer
        self.audit_grade = audit_grade

    def run(
        self,
        spec: ScenarioSpec,
        *,
        liability_network: dict,
        signer_did: str = "did:web:mimic.local",
    ) -> ScenarioRunManifest:
        """Execute one scenario.

        `liability_network` is a FIBO-shaped doc (see W-04 from_fibo_dict).

        Refuses to run when ``audit_grade=True`` (the default) AND the
        persona_builder is non-deterministic AND ``MIMIC_FROZEN_RUN`` is off.
        Pass ``audit_grade=False`` to bypass — the resulting manifest will
        carry ``None`` for both hash fields and a clear flag. See
        decision-record/2026-05-21-audit-grade-refusal.md.
        """
        self._enforce_audit_grade_contract()

        from mimic_world.contagion import (
            from_fibo_dict, PersonaAction, propagate_stress,
        )

        # 1. Build the liability network
        net = from_fibo_dict(liability_network)
        L, v, names = net.to_matrix()
        e = net.external_assets()

        # 2. Hash the initial world state — emitted only in audit-grade mode
        initial_state = self._snapshot_state(names, e, L)
        hash_initial = world_state_hash(**initial_state) if self.audit_grade else None

        # 3. Build personas — Decisions returned in canonical schema
        scenario_ctx = {
            "event": spec.spec.event.model_dump(),
            "entities": liability_network["entities"],
            "scope": spec.spec.scope.model_dump(),
        }
        decisions = self.persona_builder(scenario_ctx)

        # 4. Convert Decisions → PersonaActions for the contagion engine
        actions = [
            PersonaAction(
                node_name=str(d.instrument_iri).split("/")[-1] if "/" in str(d.instrument_iri) else d.agent_did,
                action_type=d.action_type,
                quantity_usd=d.quantity,
                confidence=d.confidence,
            )
            for d in decisions
        ]
        # match actions to known network nodes (skip orphans)
        actions = [a for a in actions if a.node_name in names]

        # 5. Propagate stress (W-05)
        stress = propagate_stress(L, e, v, names, actions)

        # 6. Hash the final world state — emitted only in audit-grade mode
        final_state = self._snapshot_state(
            names, stress.overlaid_en.equity, L,
            extra={"defaulted": stress.overlaid_en.defaulted.tolist(),
                   "h_final": stress.overlaid_debt_rank.h_final.tolist()},
        )
        hash_final = world_state_hash(**final_state) if self.audit_grade else None

        # 7. Build the seed manifest from the spec
        seed_manifest = SeedManifest(global_seed=spec.spec.mc.seed_global)

        # 8. Manifest + (optional) signature
        # spec_hash is always emitted — it's a hash of the inputs, not of state
        spec_hash = world_state_hash(
            entity_graph_state=liability_network,
            agent_memory_state={},
            market_state={},
            time_step=spec.metadata.version,
        )
        manifest = ScenarioRunManifest(
            scenario_name=spec.metadata.name,
            scenario_version=spec.metadata.version,
            spec_hash=spec_hash,
            seed_manifest=seed_manifest,
            decisions=tuple(decisions),
            world_state_hash_initial=hash_initial,
            world_state_hash_final=hash_final,
            debt_rank_R_initial=stress.baseline_debt_rank.R,
            debt_rank_R_final=stress.overlaid_debt_rank.R,
            en_total_p_star_initial=float(stress.baseline_en.p_star.sum()),
            en_total_p_star_final=float(stress.overlaid_en.p_star.sum()),
            policy_version=self.pdp.policy_version,
            audit_grade=self.audit_grade,
            metadata={"node_count": len(names), "action_count": len(actions)},
        )
        if self.signer is not None and self.audit_grade:
            # only sign in audit-grade mode — there's no hash to sign otherwise
            manifest = self._sign(manifest, signer_did=signer_did)
        return manifest

    def _enforce_audit_grade_contract(self) -> None:
        """Refuse to run when the operator hasn't earned a hash. ADR 2026-05-21-audit-grade-refusal."""
        if not self.audit_grade:
            return  # explicit downgrade — no hash will be emitted
        if _is_deterministic(self.persona_builder):
            return  # deterministic builder, no LLM in path → reproducible
        if is_frozen_run():
            return  # frozen-run cache enforces LLM reproducibility
        raise FrozenRunRequired(
            "ScenarioRunner is in audit-grade mode (default) but the configured "
            "persona_builder is non-deterministic and MIMIC_FROZEN_RUN is not set. "
            "Two options:\n"
            "  (a) set MIMIC_FROZEN_RUN=1 after warming the cache against the "
            "      LLM provider; or\n"
            "  (b) pass audit_grade=False explicitly — the manifest will then "
            "      carry world_state_hash_initial=None and world_state_hash_final=None.\n"
            "See decision-record/2026-05-21-audit-grade-refusal.md."
        )

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _snapshot_state(
        names: list[str], e: np.ndarray, L: np.ndarray,
        extra: dict | None = None,
    ) -> dict:
        state = {
            "nodes": {name: float(e[i]) for i, name in enumerate(names)},
            "liability_total": float(L.sum()),
        }
        if extra:
            state.update(extra)
        return {
            "entity_graph_state": state,
            "agent_memory_state": {},
            "market_state": {},
            "time_step": 0,
        }

    def _sign(self, manifest: ScenarioRunManifest, *, signer_did: str) -> ScenarioRunManifest:
        # sign over the final hash; the signature recordable separately
        sig = self.signer.sign(manifest.world_state_hash_final, signer_did=signer_did)
        return ScenarioRunManifest(
            scenario_name=manifest.scenario_name,
            scenario_version=manifest.scenario_version,
            spec_hash=manifest.spec_hash,
            seed_manifest=manifest.seed_manifest,
            decisions=manifest.decisions,
            world_state_hash_initial=manifest.world_state_hash_initial,
            world_state_hash_final=manifest.world_state_hash_final,
            debt_rank_R_initial=manifest.debt_rank_R_initial,
            debt_rank_R_final=manifest.debt_rank_R_final,
            en_total_p_star_initial=manifest.en_total_p_star_initial,
            en_total_p_star_final=manifest.en_total_p_star_final,
            policy_version=manifest.policy_version,
            signature=sig,
            metadata=manifest.metadata,
        )


# ── convenience persona builder for the e2e demo ─────────────────────────────

def deterministic_stub_personas(scenario_ctx: dict) -> list[Decision]:
    """Stub persona builder that produces deterministic Decisions.

    Used by the day-30 demo where the contract is "same inputs → same hash" —
    we deliberately don't call an LLM here so the demo runs without API keys
    and is bit-reproducible. F-12 replaces this with a real Concordia + Prefab
    cascade.
    """
    from uuid import UUID
    from ..schema.decision import RationaleStep

    decisions: list[Decision] = []
    for i, ent in enumerate(scenario_ctx["entities"]):
        # deterministic decision_id derived from the entity IRI
        # (UUIDv5 from a constant namespace + the IRI)
        det_id = str(UUID(bytes=__seeded_uuid_bytes(ent["iri"]), version=5))
        decisions.append(Decision(
            decision_id=det_id,
            agent_did=f"did:web:stub.{ent['iri'].rsplit('/', 1)[-1]}",
            instrument_iri=ent["iri"],
            action_type="hold",
            quantity=0.0,
            unit="USD",
            rationale_chain=[RationaleStep(
                claim="stub persona — deterministic hold",
                evidence_iri=ent["iri"],
                confidence=0.5,
            )],
            timestamp=datetime(2026, 5, 21, 0, 0, 0),  # fixed for reproducibility
            model_fingerprint="deterministic-stub-v1" + "0" * 44,
            confidence=0.5,
            policy_version="0" * 64,  # replaced by PDP at emission in real prefabs
        ))
    return decisions


# Mark the stub as deterministic so the runner allows it in audit-grade mode.
deterministic_stub_personas.is_deterministic = True  # type: ignore[attr-defined]


def __seeded_uuid_bytes(s: str) -> bytes:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).digest()[:16]


# ── one-shot CLI-style entry point ──────────────────────────────────────────

def run_scenario_e2e(
    scenario_dir: str | Path,
    *,
    liability_network: dict,
    sign: bool = True,
) -> ScenarioRunManifest:
    """End-to-end run convenience: spec + PDP + signer + stub persona."""
    scenario_dir = Path(scenario_dir)
    spec = load_spec(scenario_dir / "scenario.yaml")

    pdp = PolicyDecisionPoint(load_bundle(
        Path(__file__).resolve().parents[3] / "policy" / "opa"
    ))
    signer = LocalDevSigner.generate() if sign else None
    runner = ScenarioRunner(
        pdp=pdp,
        persona_builder=deterministic_stub_personas,
        signer=signer,
    )
    return runner.run(spec, liability_network=liability_network)
