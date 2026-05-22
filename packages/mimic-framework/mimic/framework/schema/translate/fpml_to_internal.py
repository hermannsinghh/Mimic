"""FpML → canonical translator — Plan §5.2.

FpML describes OTC derivatives. Maps trade headers and product types to
canonical Instrument records.
"""
from __future__ import annotations

from datetime import datetime

from ..entities import Instrument

FPML_PRODUCT_TO_FIBO = {
    "interestRateSwap": "https://spec.edmcouncil.org/fibo/ontology/DER/RateDerivatives/IRSwaps/InterestRateSwap",
    "creditDefaultSwap": "https://spec.edmcouncil.org/fibo/ontology/DER/CreditDerivatives/CreditDefaultSwaps/CreditDefaultSwap",
    "fxForward": "https://spec.edmcouncil.org/fibo/ontology/DER/FXDerivatives/FXForwards/FXForward",
}


def to_canonical_instrument(record: dict) -> Instrument:
    """Map an FpML trade record to a canonical Instrument."""
    product_kind = record["trade"]["product"]["productType"]
    notional_block = record["trade"]["product"]["notional"]
    return Instrument(
        iri=record["trade"]["tradeHeader"]["partyTradeIdentifier"]["tradeId"],
        instrument_type_iri=FPML_PRODUCT_TO_FIBO.get(
            product_kind, "https://mimic.ai/instruments/fpml/unknown",
        ),
        issuer_iri=record["trade"]["tradeHeader"]["partyTradeIdentifier"]["partyReference"],
        notional=float(notional_block["amount"]),
        currency=notional_block["currency"],
        maturity=datetime.fromisoformat(record["trade"]["tradeHeader"]["tradeDate"]),
    )


def to_native_instrument(inst: Instrument) -> dict:
    """Reverse mapping — round-trip-stable subset only."""
    fibo_to_product = {v: k for k, v in FPML_PRODUCT_TO_FIBO.items()}
    return {
        "trade": {
            "tradeHeader": {
                "partyTradeIdentifier": {
                    "tradeId": str(inst.iri),
                    "partyReference": str(inst.issuer_iri),
                },
                "tradeDate": inst.maturity.isoformat() if inst.maturity else None,
            },
            "product": {
                "productType": fibo_to_product.get(
                    str(inst.instrument_type_iri), "unknown",
                ),
                "notional": {
                    "amount": inst.notional,
                    "currency": inst.currency,
                },
            },
        }
    }
