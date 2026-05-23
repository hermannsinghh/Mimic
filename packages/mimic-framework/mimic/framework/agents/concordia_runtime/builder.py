"""``ConcordiaPersonaBuilder`` — the F-12 PersonaBuilder slot.

Implements the ``PersonaBuilder`` Protocol from
``mimic.framework.scenario.runner`` by driving DeepMind Concordia agents
through one observe → act cycle per entity in the scenario, then handing
each agent's reasoning to a Mimic ``Prefab`` for canonical ``Decision``
emission.

The builder declares ``is_deterministic = False`` so ``ScenarioRunner``
applies the audit-grade refusal contract (ADR
``decision-record/2026-05-21-audit-grade-refusal.md``): the run is only
allowed under ``MIMIC_FROZEN_RUN=1`` with primed cassettes, or under an
explicit ``audit_grade=False`` opt-out where the hash fields stay ``None``.

This module is the *glue* between two locked surfaces — it does not
re-decide schema, hash, policy, telemetry, refusal, equivalence, cache,
cache-key, or cassette behavior. If you reach for any of those, re-read
the nine sealed surfaces before adding code here.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, ClassVar

import numpy as np

from ...routing.provider import LLMProvider
from ...schema import Decision
from ..prefabs._base import Prefab
from .embedder import SHA256UnitEmbedder
from .language_model import DEFAULT_SYSTEM_PROMPT, MimicProviderAsConcordiaLM


class ConcordiaRuntimeImportError(ImportError):
    """Raised when ``mimic-concordia`` is missing at import time.

    The runtime module is only useful with Concordia present; failing fast
    here is friendlier than failing inside the agent build at runtime.
    """


def _import_concordia():
    """Lazy import of Concordia entrypoints via the mimic-concordia wrapper.

    Returns ``(entity_minimal, basic_associative_memory, entity_typing)`` so
    the builder can construct an agent without leaking ``concordia.*``
    imports into callers that don't have the optional dep installed. All
    submodules are re-exports from the mimic-concordia wrapper — single
    swap point per ADR 2026-05-22-concordia-vendoring-strategy.md.
    """
    try:
        from mimic_concordia import (  # noqa: F401  (presence + version check via __init__)
            basic_associative_memory as _memory,
            entity_minimal as _entity_minimal,
            entity_typing as _entity_typing,
        )
    except ImportError as exc:
        raise ConcordiaRuntimeImportError(
            "ConcordiaPersonaBuilder requires mimic-concordia. "
            "Install with: pip install mimic-framework[concordia] "
            "(or pip install mimic-concordia)."
        ) from exc
    return _entity_minimal, _memory, _entity_typing


class ConcordiaPersonaBuilder:
    """Per-entity observe → act → ``Prefab.run`` orchestrator.

    Args:
        prefab: a Mimic ``Prefab`` (e.g. ``ReinsurerTreatyPricer``). The
            same prefab is applied to every entity in the scenario. Future
            iterations may route by entity type — out of scope for F-12 step 2.
        llm_provider: the LLM provider Concordia uses for its reasoning loop.
            Should be wrapped in ``FrozenRunProvider`` whenever the run is
            audit-grade; ``ScenarioRunner`` enforces that contract.
        concordia_prefab: a Concordia ``Prefab`` recipe controlling the
            agent's component graph. Defaults to ``concordia.prefabs.entity.minimal``
            for a small, prompt-stable surface — Concordia's heavier prefabs
            (e.g. ``basic``) drive significantly more LLM calls per agent.
        embedder: callable producing a numpy vector from text. Defaults to
            the SHA-256 stub — fine for the minimal prefab which never
            retrieves; pass a real embedder when memory-retrieval components
            are in play.
        system_prompt: stable system-prompt string the LM adapter uses for
            every Concordia-routed call. Changing it invalidates every
            cassette by design — see prefab-author skill.
        agent_did_prefix: prefix for the ``agent_did`` recorded on every
            ``Decision``. The entity's IRI tail (or ``unknown``) is
            appended. ``Decision.agent_did`` is part of the audit trail
            and shows up in the OTEL ``mimic.decision`` span.
    """

    is_deterministic: ClassVar[bool] = False

    def __init__(
        self,
        *,
        prefab: Prefab,
        llm_provider: LLMProvider,
        concordia_prefab: Any | None = None,
        embedder: Callable[[str], np.ndarray] | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        agent_did_prefix: str = "did:web:concordia",
    ) -> None:
        self._minimal, self._memory, self._entity_typing = _import_concordia()
        self.prefab = prefab
        self.llm_provider = llm_provider
        self.embedder: Callable[[str], np.ndarray] = embedder or SHA256UnitEmbedder()
        self.system_prompt = system_prompt
        self.agent_did_prefix = agent_did_prefix
        self.concordia_prefab = concordia_prefab or self._minimal.Entity()
        self._lm = MimicProviderAsConcordiaLM(llm_provider, system_prompt=system_prompt)

    # ── PersonaBuilder Protocol ──────────────────────────────────────────

    def __call__(self, scenario_ctx: dict) -> list[Decision]:
        """Produce one ``Decision`` per entity in ``scenario_ctx["entities"]``.

        Failure to produce a Decision (policy violation, malformed model
        output, etc.) propagates as ``PrefabRunError``. The contract is
        list-of-decisions, not best-effort.
        """
        entities = scenario_ctx.get("entities", []) or []
        event = scenario_ctx.get("event", {}) or {}
        scope = scenario_ctx.get("scope", {}) or {}

        observation_text = self._render_observation(event=event, scope=scope)

        decisions: list[Decision] = []
        for entity in entities:
            reasoning = self._concordia_reasoning(
                entity=entity,
                observation_text=observation_text,
            )
            inputs = self._inputs_for_prefab(
                entity=entity, event=event, scope=scope, reasoning=reasoning,
            )
            agent_did = self._agent_did_for(entity)
            decision = self.prefab.run(
                entity=entity, inputs=inputs, agent_did=agent_did,
            )
            decisions.append(decision)
        return decisions

    # ── per-entity Concordia loop ────────────────────────────────────────

    def _concordia_reasoning(self, *, entity: dict, observation_text: str) -> str:
        """Build a fresh agent for ``entity``, observe the event, return action text."""
        memory_bank = self._memory.AssociativeMemoryBank(sentence_embedder=self.embedder)

        # Concordia prefabs take their params from a dataclass field.
        # We construct a fresh prefab instance per entity so the original
        # template isn't mutated across calls.
        agent_name = self._entity_name(entity)
        instance = type(self.concordia_prefab)(
            params={
                **dict(self.concordia_prefab.params),
                "name": agent_name,
                "goal": entity.get("goal", ""),
            }
        )
        agent = instance.build(model=self._lm, memory_bank=memory_bank)

        agent.observe(observation_text)
        action_spec = self._entity_typing.ActionSpec(
            call_to_action=(
                f"What would {agent_name} do in response to this situation? "
                "Reason briefly and state the intended action."
            ),
            output_type=self._entity_typing.OutputType.FREE,
            tag="concordia_reasoning",
        )
        return agent.act(action_spec=action_spec)

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _entity_name(entity: dict) -> str:
        name = entity.get("name")
        if isinstance(name, str) and name:
            return name
        iri = entity.get("iri", "")
        if isinstance(iri, str) and "/" in iri:
            return iri.rsplit("/", 1)[-1]
        return iri or "Entity"

    def _agent_did_for(self, entity: dict) -> str:
        iri = entity.get("iri", "")
        tail = iri.rsplit("/", 1)[-1] if isinstance(iri, str) and "/" in iri else "unknown"
        return f"{self.agent_did_prefix}.{tail}"

    @staticmethod
    def _render_observation(*, event: dict, scope: dict) -> str:
        """Render the scenario event as a short narrative observation.

        Kept compact and stable: this string is part of every Concordia
        prompt, and any churn here invalidates cassettes. Treat changes
        to this method as cassette-bumping.
        """
        parts: list[str] = []
        if event.get("name"):
            parts.append(f"Event: {event['name']}.")
        if event.get("description"):
            parts.append(str(event["description"]))
        if scope.get("name"):
            parts.append(f"Scenario scope: {scope['name']}.")
        if not parts:
            parts.append("A market-stress event has occurred.")
        return " ".join(parts)

    @staticmethod
    def _inputs_for_prefab(
        *, entity: dict, event: dict, scope: dict, reasoning: str,
    ) -> dict[str, Any]:
        """Standard ``inputs`` dict every prefab receives from this builder.

        Prefabs decide which keys to consume; unknown keys are ignored.
        ``concordia_reasoning`` is the Concordia agent's act() output —
        the only data path that carries the persona's reasoning into the
        Decision-emission cascade.

        Cedent-level fields (``cat_model``, ``expected_loss_usd``,
        ``premium_offer_usd``, ``treaty_layer``) are surfaced from the
        entity dict with the event as a fallback. This lets a toy
        liability network attach per-cedent underwriting facts without
        requiring the scenario YAML to carry them at the event level —
        the equivalence-test reinsurance network uses this path.
        """
        return {
            "concordia_reasoning": reasoning,
            "entity_name": entity.get("name", ""),
            "entity_iri": entity.get("iri", ""),
            "event": event,
            "scope": scope,
            "treaty_summary": _summarize_for_treaty(entity, event, reasoning),
            # cedent-level underwriting fields → fall back to event
            "cat_model": entity.get("cat_model") or event.get("cat_model"),
            "loss_ratio": entity.get("loss_ratio"),
            "expected_loss_usd": entity.get("expected_loss_usd"),
            "premium_offer_usd": entity.get("premium_offer_usd"),
            "treaty_layer": entity.get("treaty_layer"),
        }


def _summarize_for_treaty(entity: dict, event: dict, reasoning: str) -> str:
    """Compact prefab-friendly summary string. Stable across runs (no
    randomness, no timestamps), so it does not perturb cassette keys."""
    return json.dumps(
        {
            "cedent": entity.get("name", ""),
            "event": event.get("name", ""),
            "reasoning_excerpt": reasoning[:512],
        },
        sort_keys=True,
    )
