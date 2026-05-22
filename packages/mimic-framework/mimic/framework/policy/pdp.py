"""Policy Decision Point — Plan §12.

A PolicyBundle is a directory containing:
    bundle.yaml         # metadata + rules (the executable spec)
    *.rego              # canonical Rego sources (for external OPA users)

Bundle digest = sha256(canonical_json(bundle.yaml) || sha256-of-each-rego-file
sorted by filename). That digest is recorded on every Decision as
`policy_version`.

Rules are declarative predicates expressed as a small DSL:
    rule:
      id: max_position
      description: quantity * price must not exceed entity.position_limit
      when: "action_type in allowed_actions"
      then: "quantity * price <= position_limit"

The evaluator parses these into Python lambdas — no external OPA binary needed.
"""
from __future__ import annotations

import hashlib
import operator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..determinism.hashing import canonical_json


class PolicyViolation(RuntimeError):
    """Raised when a Decision fails policy evaluation."""


@dataclass(frozen=True)
class PolicyRule:
    id: str
    description: str
    allowed_action_types: frozenset[str]
    invariant: str  # human-readable; evaluated programmatically by _check_invariant

    def applies_to(self, action_type: str) -> bool:
        return action_type in self.allowed_action_types


@dataclass(frozen=True)
class PolicyBundle:
    name: str
    version: str
    digest: str
    rules: tuple[PolicyRule, ...]
    rego_files: tuple[str, ...] = field(default_factory=tuple)


def _bundle_digest(meta: dict, rego_paths: list[Path]) -> str:
    h = hashlib.sha256()
    h.update(canonical_json(meta))
    for p in sorted(rego_paths, key=lambda p: p.name):
        h.update(p.name.encode("utf-8"))
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def load_bundle(bundle_dir: str | Path) -> PolicyBundle:
    """Load and digest a policy bundle from a directory."""
    bundle_dir = Path(bundle_dir)
    meta_path = bundle_dir / "bundle.yaml"
    if not meta_path.exists():
        raise FileNotFoundError(f"missing bundle.yaml in {bundle_dir}")
    meta = yaml.safe_load(meta_path.read_text())

    rego_paths = sorted(bundle_dir.glob("*.rego"))
    digest = _bundle_digest(meta, rego_paths)

    rules = tuple(
        PolicyRule(
            id=r["id"],
            description=r.get("description", ""),
            allowed_action_types=frozenset(r["allowed_action_types"]),
            invariant=r["invariant"],
        )
        for r in meta.get("rules", [])
    )
    return PolicyBundle(
        name=meta["name"],
        version=meta["version"],
        digest=digest,
        rules=rules,
        rego_files=tuple(p.name for p in rego_paths),
    )


_SUPPORTED_INVARIANTS = {
    "quantity * price <= position_limit": lambda d, e: (
        d["quantity"] * e.get("price", 0) <= e.get("position_limit", 0)
    ),
    "quantity >= 0": lambda d, e: d["quantity"] >= 0,
    "confidence >= 0.5": lambda d, e: d.get("confidence", 0) >= 0.5,
}


class PolicyDecisionPoint:
    def __init__(self, bundle: PolicyBundle) -> None:
        self.bundle = bundle

    @property
    def policy_version(self) -> str:
        """The digest to record on every Decision evaluated by this PDP."""
        return self.bundle.digest

    def check(self, decision: dict, entity: dict) -> None:
        """Raise PolicyViolation if any applicable rule fails."""
        action = decision.get("action_type")
        applied = 0
        for rule in self.bundle.rules:
            if not rule.applies_to(action):
                continue
            applied += 1
            check_fn = _SUPPORTED_INVARIANTS.get(rule.invariant)
            if check_fn is None:
                raise PolicyViolation(
                    f"unsupported invariant in rule {rule.id!r}: {rule.invariant!r}. "
                    f"Either add a check_fn or evaluate via external OPA binary."
                )
            if not check_fn(decision, entity):
                raise PolicyViolation(
                    f"rule {rule.id!r} failed: {rule.description} "
                    f"(invariant: {rule.invariant})"
                )
        if applied == 0:
            raise PolicyViolation(
                f"no rule covers action_type={action!r}. Decisions must always be "
                f"governed by at least one bundle rule."
            )

    def allows(self, decision: dict, entity: dict) -> bool:
        try:
            self.check(decision, entity)
        except PolicyViolation:
            return False
        return True
