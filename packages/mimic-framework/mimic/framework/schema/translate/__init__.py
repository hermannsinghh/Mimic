"""Schema translators: native vendor formats <-> canonical Mimic models.

Each translator exposes:
    to_canonical(record) -> Entity | Instrument | Event
    to_native(canonical) -> dict

Round-trip tests in tests/schema/translate/ must be bit-equivalent
on the round-trip-stable subset.
"""
from . import (  # noqa: F401
    acord_to_internal,
    fibo_to_internal,
    fpml_to_internal,
    iso20022_to_internal,
)

__all__ = [
    "fibo_to_internal",
    "acord_to_internal",
    "iso20022_to_internal",
    "fpml_to_internal",
]
