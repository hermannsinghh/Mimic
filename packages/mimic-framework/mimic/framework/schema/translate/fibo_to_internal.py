"""FIBO → canonical translator — Plan §5.2.

FIBO inputs use the EDM Council ontology IRIs directly. Translation is mostly
identity at the type level (we IRI-bind to FIBO terms); this module covers the
canonical field mapping and round-trip stability for the v1 subset.
"""
from __future__ import annotations

from ..entities import Entity, Instrument


def to_canonical_entity(record: dict) -> Entity:
    return Entity(
        iri=record["iri"],
        name=record.get("name") or record.get("fibo:hasName") or record["iri"].rsplit("/", 1)[-1],
        entity_type_iri=record.get("entity_type_iri") or record["type"],
        country_iso=record.get("country_iso") or record.get("fibo:hasCountry"),
        equity=record.get("equity"),
        total_assets=record.get("total_assets") or record.get("fibo:hasTotalAssets"),
        systemic_score=record.get("systemic_score"),
    )


def to_native_entity(entity: Entity) -> dict:
    return {
        "iri": str(entity.iri),
        "name": entity.name,
        "entity_type_iri": str(entity.entity_type_iri),
        "country_iso": entity.country_iso,
        "equity": entity.equity,
        "total_assets": entity.total_assets,
        "systemic_score": entity.systemic_score,
    }


def to_canonical_instrument(record: dict) -> Instrument:
    return Instrument(
        iri=record["iri"],
        instrument_type_iri=record.get("instrument_type_iri") or record["type"],
        issuer_iri=record["issuer_iri"],
        notional=float(record["notional"]),
        currency=record["currency"],
        maturity=record.get("maturity"),
    )


def to_native_instrument(inst: Instrument) -> dict:
    return {
        "iri": str(inst.iri),
        "instrument_type_iri": str(inst.instrument_type_iri),
        "issuer_iri": str(inst.issuer_iri),
        "notional": inst.notional,
        "currency": inst.currency,
        "maturity": inst.maturity.isoformat() if inst.maturity else None,
    }
