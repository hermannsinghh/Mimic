"""BankTreasuryALM — Plan §9.2 (T1).

Input:  Y-14 disclosures, call reports, liquidity ratios
Output: liquidity actions, repo / discount-window usage
"""
from __future__ import annotations

from ...routing.provider import StructuredResponse
from ...schema.decision import Decision, RationaleStep
from ._base import Prefab, PrefabRunError


class BankTreasuryALM(Prefab):
    name = "BankTreasuryALM"
    tier_entry = "T1"

    def system_prompt(self) -> str:
        return (
            "You are the ALM treasury team for a regulated bank. Given the "
            "balance-sheet snapshot and liquidity ratios, decide the next "
            "action under stress. Return strict JSON: "
            '{"action": "hedge"|"raise_capital"|"cut_exposure"|"hold", '
            '"quantity_usd": float, "confidence": float, "rationale": str}'
        )

    def _build_messages(self, *, entity: dict, inputs: dict) -> list[dict]:
        return [{
            "role": "user",
            "content": (
                f"Bank: {entity.get('name')} ({entity.get('iri')})\n"
                f"LCR: {inputs.get('lcr')}, NSFR: {inputs.get('nsfr')}\n"
                f"Uninsured deposits: ${inputs.get('uninsured_deposits_usd', 0):,.0f}\n"
                f"AOCI: ${inputs.get('aoci_usd', 0):,.0f}"
            ),
        }]

    def _response_to_decision(
        self, *, response: StructuredResponse, entity: dict, agent_did: str,
    ) -> Decision:
        c = response.content
        action = c.get("action")
        if action not in {"hedge", "raise_capital", "cut_exposure", "hold"}:
            raise PrefabRunError(f"unexpected action {action!r} from model")
        rationale = [RationaleStep(
            claim=c.get("rationale", ""),
            evidence_iri=entity.get("iri") or "https://mimic.ai/evidence/unknown",
            confidence=float(c.get("confidence", response.confidence)),
        )]
        return self._make_decision(
            agent_did=agent_did,
            action_type=action,
            quantity=float(c.get("quantity_usd", 0.0)),
            unit="USD",
            rationale=rationale,
            confidence=float(c.get("confidence", response.confidence)),
            instrument_iri=f"{entity.get('iri', 'https://mimic.ai/instruments/unknown')}/treasury-action",
            model_fingerprint=response.model_fingerprint,
        )
