"""BrokerCedentAdvisor — Plan §9.2 (T2).

Input:  Client portfolio, market quotes
Output: recommended placement
"""
from __future__ import annotations

from ...routing.provider import StructuredResponse
from ...schema.decision import Decision, RationaleStep
from ._base import Prefab, PrefabRunError


class BrokerCedentAdvisor(Prefab):
    name = "BrokerCedentAdvisor"
    tier_entry = "T2"

    def system_prompt(self) -> str:
        return (
            "You are a reinsurance broker advising a cedent. Given the client "
            "portfolio and current market quotes, recommend placement. "
            "Return strict JSON: "
            '{"action": "cede"|"retain", "cession_pct": float, '
            '"premium_target_usd": float, "confidence": float, "rationale": str}'
        )

    def _build_messages(self, *, entity: dict, inputs: dict) -> list[dict]:
        return [{
            "role": "user",
            "content": (
                f"Cedent: {entity.get('name')} ({entity.get('iri')})\n"
                f"Gross premium volume: ${inputs.get('gpv_usd', 0):,.0f}\n"
                f"Market rate-on-line: {inputs.get('rol_pct')}%\n"
                f"Reinsurer appetite: {inputs.get('appetite')}"
            ),
        }]

    def _response_to_decision(
        self, *, response: StructuredResponse, entity: dict, agent_did: str,
    ) -> Decision:
        c = response.content
        action = c.get("action")
        if action not in {"cede", "retain"}:
            raise PrefabRunError(f"unexpected action {action!r} from model")
        rationale = [RationaleStep(
            claim=c.get("rationale", ""),
            evidence_iri=entity.get("iri") or "https://mimic.ai/evidence/unknown",
            confidence=float(c.get("confidence", response.confidence)),
        )]
        return self._make_decision(
            agent_did=agent_did,
            action_type=action,
            quantity=float(c.get("premium_target_usd", 0.0)),
            unit="USD",
            rationale=rationale,
            confidence=float(c.get("confidence", response.confidence)),
            instrument_iri=f"{entity.get('iri', 'https://mimic.ai/instruments/unknown')}/treaty-placement",
            model_fingerprint=response.model_fingerprint,
        )
