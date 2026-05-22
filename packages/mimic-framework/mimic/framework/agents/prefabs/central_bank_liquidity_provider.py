"""CentralBankLiquidityProvider — Plan §9.2 (T1).

Input:  Policy stance, balance sheet, system stress indicators
Output: facility opening / rate decision
"""
from __future__ import annotations

from ...routing.provider import StructuredResponse
from ...schema.decision import Decision, RationaleStep
from ._base import Prefab, PrefabRunError


class CentralBankLiquidityProvider(Prefab):
    name = "CentralBankLiquidityProvider"
    tier_entry = "T1"

    def system_prompt(self) -> str:
        return (
            "You are a central-bank liquidity-policy committee. Given the "
            "system stress snapshot, decide whether to open a facility, hold, "
            "or change rates. Return strict JSON: "
            '{"action": "raise_capital"|"hold", "facility_size_usd": float, '
            '"rate_change_bp": float, "confidence": float, "rationale": str}'
        )

    def _build_messages(self, *, entity: dict, inputs: dict) -> list[dict]:
        return [{
            "role": "user",
            "content": (
                f"Authority: {entity.get('name')} ({entity.get('iri')})\n"
                f"FRA-OIS spread (bp): {inputs.get('fra_ois_bp')}\n"
                f"Treasury market dysfunction index: {inputs.get('treasury_dysfunction')}\n"
                f"MMF gates triggered: {inputs.get('mmf_gates_count', 0)}"
            ),
        }]

    def _response_to_decision(
        self, *, response: StructuredResponse, entity: dict, agent_did: str,
    ) -> Decision:
        c = response.content
        action = c.get("action")
        if action not in {"raise_capital", "hold"}:
            raise PrefabRunError(f"unexpected action {action!r} from model")
        rationale = [RationaleStep(
            claim=c.get("rationale", ""),
            evidence_iri=entity.get("iri") or "https://mimic.ai/evidence/unknown",
            confidence=float(c.get("confidence", response.confidence)),
        )]
        return self._make_decision(
            agent_did=agent_did,
            action_type=action,
            quantity=float(c.get("facility_size_usd", 0.0)),
            unit="USD",
            rationale=rationale,
            confidence=float(c.get("confidence", response.confidence)),
            instrument_iri=f"{entity.get('iri', 'https://mimic.ai/instruments/unknown')}/liquidity-facility",
            model_fingerprint=response.model_fingerprint,
        )
