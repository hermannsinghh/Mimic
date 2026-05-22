"""Canonical Decision and Outcome models — Plan §5.1.

NEVER change this file without bumping the schema major version
and updating the golden test vectors in tests/determinism/golden/.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AnyUrl, BaseModel


ActionType = Literal[
    "hedge",
    "raise_capital",
    "cut_exposure",
    "lobby",
    "hold",
    "sell",
    "buy",
    "reinsure",
    "cede",
    "retain",
]


class RationaleStep(BaseModel):
    claim: str
    evidence_iri: AnyUrl
    confidence: float


class Decision(BaseModel):
    decision_id: str
    agent_did: str
    instrument_iri: AnyUrl
    action_type: ActionType
    quantity: float
    unit: str
    rationale_chain: list[RationaleStep]
    timestamp: datetime
    model_fingerprint: str
    confidence: float
    policy_version: str


class Outcome(BaseModel):
    world_state_hash_prev: str
    event_iri: AnyUrl
    world_state_hash_next: str
    probability_weight: float
    seed: int
    timestamp: datetime
