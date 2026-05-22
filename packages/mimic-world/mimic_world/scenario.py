"""Scenario — structured shock event with cascade rules and a 50-scenario library."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CascadeRule:
    """How one world-state variable propagates to another."""

    from_key: str
    to_key: str
    multiplier: float  # how much of from_key's value bleeds into to_key


@dataclass
class Scenario:
    """
    A structured economic/geopolitical shock with known propagation patterns.

    Use Scenario.from_library("taiwan_strait_closure_30d") to load a pre-built scenario,
    or construct one directly for custom simulations.
    """

    id: str
    title: str
    category: str                    # geopolitical|supply_chain|macro|climate|pandemic|cyber
    severity: float                  # 0–1 (1 = catastrophic)
    duration_days: int
    initial_shocks: dict[str, float] # world_state key → delta (fraction)
    affected_sectors: list[str] = field(default_factory=list)
    cascade_rules: list[CascadeRule] = field(default_factory=list)
    historical_analogue: Optional[str] = None
    source: str = "mimic-world team"
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Scenario:
        return cls(
            id=data["id"],
            title=data["title"],
            category=data["category"],
            severity=float(data["severity"]),
            duration_days=int(data["duration_days"]),
            initial_shocks={k: float(v) for k, v in data["initial_shocks"].items()},
            affected_sectors=data.get("affected_sectors", []),
            cascade_rules=[
                CascadeRule(
                    from_key=r["from"],
                    to_key=r["to"],
                    multiplier=float(r["multiplier"]),
                )
                for r in data.get("cascade_rules", [])
            ],
            historical_analogue=data.get("historical_analogue"),
            source=data.get("source", "mimic-world team"),
            description=data.get("description", ""),
        )

    @classmethod
    def from_library(cls, scenario_id: str) -> Scenario:
        """Load a pre-built scenario from the bundled library."""
        lib_path = Path(__file__).parent.parent / "scenarios" / "library"
        path = lib_path / f"{scenario_id}.json"

        if not path.exists():
            available = sorted(f.stem for f in lib_path.glob("*.json"))
            raise ValueError(
                f"Scenario {scenario_id!r} not found.\n"
                f"Available ({len(available)}): {', '.join(available)}"
            )

        with open(path) as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def list_library(cls) -> list[dict]:
        """Return metadata for all scenarios in the library."""
        lib_path = Path(__file__).parent.parent / "scenarios" / "library"
        scenarios = []
        for path in sorted(lib_path.glob("*.json")):
            with open(path) as f:
                data = json.load(f)
                scenarios.append(
                    {
                        "id": data["id"],
                        "title": data["title"],
                        "category": data["category"],
                        "severity": data["severity"],
                        "duration_days": data["duration_days"],
                    }
                )
        return scenarios

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "severity": self.severity,
            "duration_days": self.duration_days,
            "initial_shocks": self.initial_shocks,
            "affected_sectors": self.affected_sectors,
            "cascade_rules": [
                {"from": r.from_key, "to": r.to_key, "multiplier": r.multiplier}
                for r in self.cascade_rules
            ],
            "historical_analogue": self.historical_analogue,
            "source": self.source,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return (
            f"Scenario(id={self.id!r}, severity={self.severity:.0%}, "
            f"duration={self.duration_days}d)"
        )
