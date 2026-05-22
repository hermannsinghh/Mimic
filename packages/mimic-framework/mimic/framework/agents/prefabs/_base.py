"""Prefab base class — Plan §9.2.

Every domain prefab:
  1. Takes structured inputs that bind to FIBO IRIs.
  2. Calls through `mimic.framework.routing` (F-06) at its configured tier.
  3. Runs the candidate decision through `mimic.framework.policy` (F-09).
  4. Emits a `mimic.framework.schema.Decision`.

A prefab that bypasses any of these is not ship-ready (see
.claude/skills/mimic-prefab-author.md).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import uuid4

from ...policy import PolicyDecisionPoint, PolicyViolation
from ...routing.cascade import RoutingCascade
from ...routing.provider import StructuredResponse
from ...schema.decision import ActionType, Decision, RationaleStep
from ..telemetry import build_decision_attrs, decision_span


class PrefabRunError(RuntimeError):
    """Raised when a prefab can't produce a Decision (policy block, malformed LLM output, etc.)."""


class Prefab(ABC):
    """Base class for every domain prefab."""

    name: str
    tier_entry: str  # "T1" | "T2" | "T3" — entry tier into the cascade

    def __init__(self, *, cascade: RoutingCascade, pdp: PolicyDecisionPoint) -> None:
        self.cascade = cascade
        self.pdp = pdp

    def run(self, *, entity: dict, inputs: dict, agent_did: str) -> Decision:
        """Produce a Decision for `entity` given structured `inputs`.

        Wraps the whole emission in a `mimic.decision` OTEL span carrying
        policy_version so post-hoc auditors can prove the Decision was
        governed by a specific signed bundle (Plan §12).
        """
        with decision_span({"agent_did": agent_did, "prefab_name": self.name}) as span:
            messages = self._build_messages(entity=entity, inputs=inputs)
            result = self.cascade.route(
                entry_tier=self.tier_entry,
                messages=messages,
                system_prompt=self.system_prompt(),
                temperature=0.0,
            )
            candidate = self._response_to_decision(
                response=result.response,
                entity=entity,
                agent_did=agent_did,
            )
            try:
                self.pdp.check(candidate.model_dump(), entity)
            except PolicyViolation as e:
                raise PrefabRunError(f"{self.name} policy violation: {e}") from e
            span.set_attributes(build_decision_attrs(
                agent_did=agent_did,
                prefab_name=self.name,
                tier_entry=self.tier_entry,
                action_type=candidate.action_type,
                confidence=candidate.confidence,
                model_fingerprint=candidate.model_fingerprint,
                policy_version=candidate.policy_version,
                instrument_iri=str(candidate.instrument_iri),
            ))
            return candidate

    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def _build_messages(self, *, entity: dict, inputs: dict) -> list[dict]: ...

    @abstractmethod
    def _response_to_decision(
        self, *, response: StructuredResponse, entity: dict, agent_did: str,
    ) -> Decision: ...

    # ── helpers shared across prefabs ────────────────────────────────────

    def _make_decision(
        self,
        *,
        agent_did: str,
        action_type: ActionType,
        quantity: float,
        unit: str,
        rationale: list[RationaleStep],
        confidence: float,
        instrument_iri: str,
        model_fingerprint: str,
    ) -> Decision:
        return Decision(
            decision_id=str(uuid4()),
            agent_did=agent_did,
            instrument_iri=instrument_iri,
            action_type=action_type,
            quantity=quantity,
            unit=unit,
            rationale_chain=rationale,
            timestamp=datetime.utcnow(),
            model_fingerprint=model_fingerprint,
            confidence=confidence,
            policy_version=self.pdp.policy_version,
        )
