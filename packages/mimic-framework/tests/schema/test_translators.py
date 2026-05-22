"""Schema translator round-trip tests — Plan §5.2.

Round-trip native → canonical → native MUST be bit-equivalent on the
round-trip-stable subset.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from mimic.framework.schema.translate import (
    acord_to_internal,
    fibo_to_internal,
    fpml_to_internal,
    iso20022_to_internal,
)


# ── FIBO ────────────────────────────────────────────────────────────────────

def test_fibo_entity_round_trip():
    native = {
        "iri": "https://example.com/svb",
        "name": "SVB",
        "entity_type_iri": "https://spec.edmcouncil.org/fibo/.../FinancialInstitution",
        "country_iso": "US",
        "equity": 16e9,
        "total_assets": 209e9,
        "systemic_score": 0.65,
    }
    canonical = fibo_to_internal.to_canonical_entity(native)
    assert canonical.name == "SVB"
    assert canonical.total_assets == 209e9
    back = fibo_to_internal.to_native_entity(canonical)
    assert back == native


def test_fibo_entity_handles_alt_field_names():
    native = {
        "iri": "https://example.com/svb",
        "fibo:hasName": "SVB",
        "type": "https://spec.edmcouncil.org/fibo/.../FinancialInstitution",
        "fibo:hasTotalAssets": 209e9,
    }
    canonical = fibo_to_internal.to_canonical_entity(native)
    assert canonical.name == "SVB"
    assert canonical.total_assets == 209e9


def test_fibo_instrument_round_trip():
    native = {
        "iri": "https://example.com/svb-bond-1",
        "instrument_type_iri": "https://spec.edmcouncil.org/.../DebtInstrument",
        "issuer_iri": "https://example.com/svb",
        "notional": 1e9,
        "currency": "USD",
        "maturity": "2030-01-01T00:00:00",
    }
    canonical = fibo_to_internal.to_canonical_instrument(native)
    back = fibo_to_internal.to_native_instrument(canonical)
    assert back == native


# ── ACORD ───────────────────────────────────────────────────────────────────

def test_acord_carrier_round_trip():
    native = {
        "@id": "https://example.com/acord/munich-re",
        "PartyTypeCd": "Carrier",
        "NameInfo": {"CommlName": {"CommercialName": "Munich Re"}},
        "Addr": {"Country": "DE"},
    }
    canonical = acord_to_internal.to_canonical_carrier(native)
    assert canonical.name == "Munich Re"
    assert canonical.country_iso == "DE"
    back = acord_to_internal.to_native_carrier(canonical)
    assert back == native


def test_acord_carrier_missing_country():
    native = {
        "@id": "https://example.com/acord/abc",
        "PartyTypeCd": "Carrier",
        "NameInfo": {"CommlName": {"CommercialName": "ABC"}},
    }
    canonical = acord_to_internal.to_canonical_carrier(native)
    back = acord_to_internal.to_native_carrier(canonical)
    assert back["Addr"] == {}


# ── ISO 20022 ───────────────────────────────────────────────────────────────

def test_iso20022_event_round_trip():
    native = {
        "@id": "https://example.com/iso/msg-001",
        "BizMsgEnvlp": {
            "Hdr": {
                "MsgDefIdr": "pacs.008.001.08",
                "CreDt": "2024-01-15T10:30:00",
            },
            "Body": {
                "Parties": [
                    {"@id": "https://example.com/bnk/a"},
                    {"@id": "https://example.com/bnk/b"},
                ],
                "Amount": {"value": 1000000, "currency": "EUR"},
            },
        },
    }
    canonical = iso20022_to_internal.to_canonical_event(native)
    assert len(canonical.affected_entity_iris) == 2
    assert canonical.occurred_at.year == 2024
    back = iso20022_to_internal.to_native_event(canonical)
    assert back["BizMsgEnvlp"]["Hdr"]["MsgDefIdr"].startswith("pacs.008")
    assert back["BizMsgEnvlp"]["Body"] == native["BizMsgEnvlp"]["Body"]


# ── FpML ────────────────────────────────────────────────────────────────────

def test_fpml_interest_rate_swap_round_trip():
    native = {
        "trade": {
            "tradeHeader": {
                "partyTradeIdentifier": {
                    "tradeId": "https://example.com/trade/irs-001",
                    "partyReference": "https://example.com/jpm",
                },
                "tradeDate": "2025-06-15T00:00:00",
            },
            "product": {
                "productType": "interestRateSwap",
                "notional": {"amount": 50_000_000, "currency": "USD"},
            },
        }
    }
    canonical = fpml_to_internal.to_canonical_instrument(native)
    assert canonical.notional == 50_000_000
    assert canonical.currency == "USD"
    assert str(canonical.instrument_type_iri).endswith("InterestRateSwap")
    back = fpml_to_internal.to_native_instrument(canonical)
    assert back == native


def test_fpml_credit_default_swap_round_trip():
    native = {
        "trade": {
            "tradeHeader": {
                "partyTradeIdentifier": {
                    "tradeId": "https://example.com/trade/cds-001",
                    "partyReference": "https://example.com/gs",
                },
                "tradeDate": "2025-09-01T00:00:00",
            },
            "product": {
                "productType": "creditDefaultSwap",
                "notional": {"amount": 25_000_000, "currency": "EUR"},
            },
        }
    }
    canonical = fpml_to_internal.to_canonical_instrument(native)
    assert str(canonical.instrument_type_iri).endswith("CreditDefaultSwap")
    back = fpml_to_internal.to_native_instrument(canonical)
    assert back == native
