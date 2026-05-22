"""Scenario spec models — see Plan §10.2."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import AnyUrl, BaseModel, Field


class ScenarioEvent(BaseModel):
    iri: AnyUrl
    duration_days: int


class ScenarioScope(BaseModel):
    tiers: list[Literal["T1", "T2", "T3"]]
    entity_filter: str | None = None


class MonteCarloConfig(BaseModel):
    paths: int = Field(ge=1)
    horizon_days: int = Field(ge=1)
    seed_global: int


class ScenarioMetadata(BaseModel):
    name: str
    version: str
    license: str
    author_did: str
    mimic_version: str


class ScenarioSpecBody(BaseModel):
    event: ScenarioEvent
    scope: ScenarioScope
    mc: MonteCarloConfig
    reloop: bool = False
    budget_usd: float | None = None


class ScenarioSpec(BaseModel):
    apiVersion: Literal["mimic.scenario/v1"]
    kind: Literal["Scenario"]
    metadata: ScenarioMetadata
    spec: ScenarioSpecBody


def load_spec(path: str | Path) -> ScenarioSpec:
    """Load and validate a scenario.yaml from disk."""
    raw = yaml.safe_load(Path(path).read_text())
    return ScenarioSpec.model_validate(raw)
