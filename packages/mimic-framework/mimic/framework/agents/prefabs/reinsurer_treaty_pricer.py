"""ReinsurerTreatyPricer — Plan §9.2 (T1).

Input:  10-K extracts, treaty wordings, cat-model output
Output: bid/no-bid + price + retention (Decision with action_type='reinsure' | 'hold')
"""
from __future__ import annotations

from ...routing.provider import StructuredResponse
from ...schema.decision import Decision, RationaleStep
from ._base import Prefab, PrefabRunError


class ReinsurerTreatyPricer(Prefab):
    name = "ReinsurerTreatyPricer"
    tier_entry = "T1"

    def system_prompt(self) -> str:
        return (
            "You are a reinsurance treaty pricer. Given the cedent profile, "
            "wording, and cat-model output, decide bid/no-bid; if bid, set "
            "premium and retention. Return strict JSON: "
            '{"action": "reinsure"|"hold", "premium_usd": float, '
            '"retention_usd": float, "confidence": float, "rationale": str}'
        )

    def _build_messages(self, *, entity: dict, inputs: dict) -> list[dict]:
        return [{
            "role": "user",
            "content": (
                f"Cedent: {entity.get('name')} ({entity.get('iri')})\n"
                f"Treaty: {inputs.get('treaty_summary')}\n"
                f"Cat-model OEP/AEP: {inputs.get('cat_model')}\n"
                f"Recent loss ratio: {inputs.get('loss_ratio')}"
            ),
        }]

    def _response_to_decision(
        self, *, response: StructuredResponse, entity: dict, agent_did: str,
    ) -> Decision:
        c = response.content
        action = c.get("action")
        if action not in {"reinsure", "hold"}:
            raise PrefabRunError(f"unexpected action {action!r} from model")
        rationale = [RationaleStep(
            claim=c.get("rationale", ""),
            evidence_iri=entity.get("iri") or "https://mimic.ai/evidence/unknown",
            confidence=float(c.get("confidence", response.confidence)),
        )]
        return self._make_decision(
            agent_did=agent_did,
            action_type=action,
            quantity=float(c.get("premium_usd", 0.0)),
            unit="USD",
            rationale=rationale,
            confidence=float(c.get("confidence", response.confidence)),
            instrument_iri=inputs_to_instrument_iri(entity, "reinsurance-treaty"),
            model_fingerprint=response.model_fingerprint,
        )


def inputs_to_instrument_iri(entity: dict, suffix: str) -> str:
    base = entity.get("iri", "https://mimic.ai/instruments/unknown")
    return f"{base}/{suffix}"
