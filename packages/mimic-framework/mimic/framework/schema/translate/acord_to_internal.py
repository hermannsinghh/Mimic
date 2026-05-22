"""ACORD → canonical translator — Plan §5.2.

ACORD message-set field names follow the ACORD XML schema; mapping to FIBO
IRIs is many-to-one (multiple ACORD policy types map to one FIBO insurance
instrument type).
"""
from __future__ import annotations

from ..entities import Entity, Instrument

ACORD_TYPE_TO_FIBO = {
    "Carrier": "https://spec.edmcouncil.org/fibo/ontology/FBC/FunctionalEntities/FinancialServicesEntities/Carrier",
    "Reinsurer": "https://spec.edmcouncil.org/fibo/ontology/FBC/FunctionalEntities/FinancialServicesEntities/Reinsurer",
    "Broker": "https://spec.edmcouncil.org/fibo/ontology/FBC/FunctionalEntities/FinancialServicesEntities/Broker",
}


def to_canonical_carrier(record: dict) -> Entity:
    """Map an ACORD Carrier record to a canonical Entity."""
    party_type = record.get("PartyTypeCd", "Carrier")
    return Entity(
        iri=record.get("@id") or f"https://acord.local/carrier/{record['NameInfo']['CommlName']['CommercialName']}",
        name=record["NameInfo"]["CommlName"]["CommercialName"],
        entity_type_iri=ACORD_TYPE_TO_FIBO.get(party_type, ACORD_TYPE_TO_FIBO["Carrier"]),
        country_iso=record.get("Addr", {}).get("Country"),
    )


def to_native_carrier(entity: Entity) -> dict:
    """Reverse mapping — preserves the round-trip-stable subset."""
    return {
        "@id": str(entity.iri),
        "PartyTypeCd": "Carrier",
        "NameInfo": {"CommlName": {"CommercialName": entity.name}},
        "Addr": {"Country": entity.country_iso} if entity.country_iso else {},
    }
