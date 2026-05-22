"""Policy engine — Plan §12.

Every agent action is wrapped by a Policy Decision Point (PDP) that:
  1. Loads a signed bundle (a directory containing rules + manifest).
  2. Computes the bundle digest — that digest IS the policy_version recorded
     on every Decision.
  3. Evaluates each Decision against the bundle's rules.

A run is NOT audit-grade unless every Decision has a verified policy_version
that matches a digest the PDP has loaded.

The reference Rego rules live in `policy/opa/` at the package root. They are
the canonical spec; the Python evaluator in this module is the in-process
shadow used during workflow execution.
"""
from .pdp import (  # noqa: F401
    PolicyBundle,
    PolicyDecisionPoint,
    PolicyRule,
    PolicyViolation,
    load_bundle,
)

__all__ = [
    "PolicyBundle",
    "PolicyDecisionPoint",
    "PolicyRule",
    "PolicyViolation",
    "load_bundle",
]
