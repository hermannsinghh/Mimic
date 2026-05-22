"""ISO 20022 → canonical translator — Plan §5.2.

ISO 20022 message types (e.g. pacs.008 customer credit transfer) map to
canonical Event records with payment-leg payloads.
"""
from __future__ import annotations

from datetime import datetime

from ..entities import Event

ISO20022_MSG_TO_FIBO = {
    "pacs.008": "https://spec.edmcouncil.org/fibo/ontology/FBC/ProductsAndServices/PaymentsAndServices/CustomerCreditTransfer",
    "camt.054": "https://spec.edmcouncil.org/fibo/ontology/FBC/ProductsAndServices/PaymentsAndServices/AccountNotification",
}


def to_canonical_event(record: dict) -> Event:
    """Map an ISO 20022 message envelope to a canonical Event."""
    msg_type = record["BizMsgEnvlp"]["Hdr"]["MsgDefIdr"].split(".")[0]
    msg_key = ".".join(record["BizMsgEnvlp"]["Hdr"]["MsgDefIdr"].split(".")[:2])
    body = record["BizMsgEnvlp"]["Body"]
    return Event(
        iri=record["@id"],
        event_type_iri=ISO20022_MSG_TO_FIBO.get(msg_key, "https://mimic.ai/events/iso20022/unknown"),
        occurred_at=datetime.fromisoformat(record["BizMsgEnvlp"]["Hdr"]["CreDt"]),
        affected_entity_iris=[p["@id"] for p in body.get("Parties", [])],
        payload=body,
    )


def to_native_event(event: Event) -> dict:
    """Reverse mapping — round-trip-stable subset only."""
    msg_key_to_type = {v: k for k, v in ISO20022_MSG_TO_FIBO.items()}
    msg_def_idr = msg_key_to_type.get(str(event.event_type_iri), "unknown.0.0")
    return {
        "@id": str(event.iri),
        "BizMsgEnvlp": {
            "Hdr": {
                "MsgDefIdr": f"{msg_def_idr}.001.08",
                "CreDt": event.occurred_at.isoformat(),
            },
            "Body": event.payload,
        },
    }
