"""FIBO-shaped network builder — Plan §3.3 W-04.

Consumes FIBO-style entity + bilateral-exposure dicts and produces a
LiabilityNetwork ready for Eisenberg-Noe / DebtRank.

Minimal FIBO-shaped document::

    {
      "schema": "mimic.world.liability/v1",
      "currency": "USD",
      "entities": [
        {
          "iri": "https://example.com/svb",
          "name": "SVB",
          "type": "fibo-fbc-fct-fse:FinancialInstitution",
          "equity": 16e9,
          "total_assets": 209e9
        }
      ],
      "exposures": [
        {
          "debtor_iri": "https://example.com/svb",
          "creditor_iri": "https://example.com/fhlb",
          "amount": 14e9,
          "instrument_iri": "fibo-fbc-dae-dbt:DebtInstrument"
        }
      ]
    }

Loose validation only — strict canonical schema validation lives in
`mimic.framework.schema.translate.fibo_to_internal`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .network import LiabilityNetwork

REQUIRED_ENTITY_FIELDS = ("iri", "equity", "total_assets")
REQUIRED_EXPOSURE_FIELDS = ("debtor_iri", "creditor_iri", "amount")
SUPPORTED_SCHEMA = "mimic.world.liability/v1"


class FIBOValidationError(ValueError):
    """Raised when the input document is not a valid FIBO-shaped liability doc."""


def from_fibo_dict(doc: dict) -> LiabilityNetwork:
    """Build a LiabilityNetwork from a FIBO-shaped dict.

    Entities are keyed by IRI (canonical identifier in FIBO). The `name`
    field is optional — if present, it's preserved as metadata; node
    lookup always goes through the IRI.
    """
    if doc.get("schema") != SUPPORTED_SCHEMA:
        raise FIBOValidationError(
            f"unsupported schema {doc.get('schema')!r}, expected {SUPPORTED_SCHEMA!r}"
        )
    if "entities" not in doc:
        raise FIBOValidationError("missing 'entities'")
    if "exposures" not in doc:
        raise FIBOValidationError("missing 'exposures' (use [] for an empty network)")

    net = LiabilityNetwork()
    seen: set[str] = set()
    for ent in doc["entities"]:
        for field in REQUIRED_ENTITY_FIELDS:
            if field not in ent:
                raise FIBOValidationError(f"entity missing required field {field!r}: {ent}")
        if ent["iri"] in seen:
            raise FIBOValidationError(f"duplicate entity IRI: {ent['iri']!r}")
        seen.add(ent["iri"])
        net.add_node(
            name=ent["iri"],
            equity=float(ent["equity"]),
            total_assets=float(ent["total_assets"]),
            fibo_iri=ent["iri"],
            display_name=ent.get("name"),
            entity_type=ent.get("type"),
        )

    for exp in doc["exposures"]:
        for field in REQUIRED_EXPOSURE_FIELDS:
            if field not in exp:
                raise FIBOValidationError(f"exposure missing required field {field!r}: {exp}")
        if exp["debtor_iri"] not in seen:
            raise FIBOValidationError(
                f"exposure references unknown debtor IRI {exp['debtor_iri']!r}"
            )
        if exp["creditor_iri"] not in seen:
            raise FIBOValidationError(
                f"exposure references unknown creditor IRI {exp['creditor_iri']!r}"
            )
        net.add_bilateral_exposure(
            debtor=exp["debtor_iri"],
            creditor=exp["creditor_iri"],
            amount=float(exp["amount"]),
        )
    return net


def from_fibo_json(path: str | Path) -> LiabilityNetwork:
    """Load + parse a FIBO-shaped liability document from disk."""
    return from_fibo_dict(json.loads(Path(path).read_text()))
