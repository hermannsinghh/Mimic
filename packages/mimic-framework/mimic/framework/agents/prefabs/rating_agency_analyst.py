"""RatingAgencyAnalyst — Plan §9.2 (T2).

Input:  Rating methodology, financials
Output: watch / downgrade / no-action
"""
from __future__ import annotations

from ...routing.provider import StructuredResponse
from ...schema.decision import Decision, RationaleStep
from ._base import Prefab, PrefabRunError


class RatingAgencyAnalyst(Prefab):
    name = "RatingAgencyAnalyst"
    tier_entry = "T2"

    def system_prompt(self) -> str:
        return (
            "You are a rating-agency analyst. Given the issuer's financials and "
            "the rating methodology trigger, decide watch / downgrade / no-action. "
            "Return strict JSON: "
            '{"action": "cut_exposure"|"hold", "notches": int, '
            '"confidence": float, "rationale": str}'
        )

    def _build_messages(self, *, entity: dict, inputs: dict) -> list[dict]:
        return [{
            "role": "user",
            "content": (
                f"Issuer: {entity.get('name')} ({entity.get('iri')})\n"
                f"Current rating: {inputs.get('current_rating')}\n"
                f"Trigger fired: {inputs.get('trigger')}\n"
                f"Recent EBITDA / interest: {inputs.get('icr')}x"
            ),
        }]

    def _response_to_decision(
        self, *, response: StructuredResponse, entity: dict, agent_did: str,
    ) -> Decision:
        c = response.content
        action = c.get("action")
        if action not in {"cut_exposure", "hold"}:
            raise PrefabRunError(f"unexpected action {action!r} from model")
        rationale = [RationaleStep(
            claim=c.get("rationale", ""),
            evidence_iri=entity.get("iri") or "https://mimic.ai/evidence/unknown",
            confidence=float(c.get("confidence", response.confidence)),
        )]
        return self._make_decision(
            agent_did=agent_did,
            action_type=action,
            quantity=float(c.get("notches", 0)),
            unit="rating_notch",
            rationale=rationale,
            confidence=float(c.get("confidence", response.confidence)),
            instrument_iri=f"{entity.get('iri', 'https://mimic.ai/instruments/unknown')}/credit-rating",
            model_fingerprint=response.model_fingerprint,
        )
