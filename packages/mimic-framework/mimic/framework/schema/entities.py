"""Canonical Entity / Instrument / Event models — Plan §5.

These are the target shapes for every translator in `schema/translate/`.
Bind to FIBO IRIs; do not invent new types.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AnyUrl, BaseModel


class Entity(BaseModel):
    iri: AnyUrl
    name: str
    entity_type_iri: AnyUrl  # e.g. fibo-fbc-fct-fse:FinancialInstitution
    country_iso: str | None = None
    equity: float | None = None
    total_assets: float | None = None
    systemic_score: float | None = None


class Instrument(BaseModel):
    iri: AnyUrl
    instrument_type_iri: AnyUrl  # e.g. fibo-fbc-dae-dbt:DebtInstrument
    issuer_iri: AnyUrl
    notional: float
    currency: str  # ISO 4217
    maturity: datetime | None = None


class Event(BaseModel):
    iri: AnyUrl
    event_type_iri: AnyUrl  # e.g. fibo-fnd-arr-rep:ReportingEvent
    occurred_at: datetime
    affected_entity_iris: list[AnyUrl]
    payload: dict
