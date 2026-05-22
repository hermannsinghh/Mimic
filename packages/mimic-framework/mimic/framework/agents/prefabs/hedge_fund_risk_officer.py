"""HedgeFundRiskOfficer — Plan §9.2 (T2).

Input:  Form PF, holdings, leverage
Output: position trims, hedges
"""
from __future__ import annotations

from ...routing.provider import StructuredResponse
from ...schema.decision import Decision, RationaleStep
from ._base import Prefab, PrefabRunError


class HedgeFundRiskOfficer(Prefab):
    name = "HedgeFundRiskOfficer"
    tier_entry = "T2"

    def system_prompt(self) -> str:
        return (
            "You are the risk officer for a hedge fund. Given the leverage and "
            "exposure snapshot, propose trim or hedge actions. Return strict JSON: "
            '{"action": "hedge"|"sell"|"hold", "notional_usd": float, '
            '"confidence": float, "rationale": str}'
        )

    def _build_messages(self, *, entity: dict, inputs: dict) -> list[dict]:
        return [{
            "role": "user",
            "content": (
                f"Fund: {entity.get('name')} ({entity.get('iri')})\n"
                f"Gross leverage: {inputs.get('gross_leverage')}x\n"
                f"Top concentration: {inputs.get('top_concentration_pct')}%\n"
                f"Largest counterparty exposure: ${inputs.get('top_cpty_usd', 0):,.0f}"
            ),
        }]

    def _response_to_decision(
        self, *, response: StructuredResponse, entity: dict, agent_did: str,
    ) -> Decision:
        c = response.content
        action = c.get("action")
        if action not in {"hedge", "sell", "hold"}:
            raise PrefabRunError(f"unexpected action {action!r} from model")
        rationale = [RationaleStep(
            claim=c.get("rationale", ""),
            evidence_iri=entity.get("iri") or "https://mimic.ai/evidence/unknown",
            confidence=float(c.get("confidence", response.confidence)),
        )]
        return self._make_decision(
            agent_did=agent_did,
            action_type=action,
            quantity=float(c.get("notional_usd", 0.0)),
            unit="USD",
            rationale=rationale,
            confidence=float(c.get("confidence", response.confidence)),
            instrument_iri=f"{entity.get('iri', 'https://mimic.ai/instruments/unknown')}/risk-action",
            model_fingerprint=response.model_fingerprint,
        )
