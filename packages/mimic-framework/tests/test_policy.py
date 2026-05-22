"""Tests for the policy decision point — Plan §12."""
from __future__ import annotations

from pathlib import Path

import pytest

from mimic.framework.policy import (
    PolicyDecisionPoint,
    PolicyViolation,
    load_bundle,
)

_BUNDLE_DIR = Path(__file__).resolve().parents[1] / "policy" / "opa"


def test_bundle_loads_and_digests():
    b = load_bundle(_BUNDLE_DIR)
    assert b.name == "mimic-agent-actions"
    assert b.version == "0.1.0"
    assert len(b.digest) == 64
    assert "agent_actions.rego" in b.rego_files
    assert len(b.rules) == 3


def test_bundle_digest_is_stable():
    a = load_bundle(_BUNDLE_DIR)
    b = load_bundle(_BUNDLE_DIR)
    assert a.digest == b.digest


def test_pdp_allows_within_position_limit():
    pdp = PolicyDecisionPoint(load_bundle(_BUNDLE_DIR))
    decision = {"action_type": "buy", "quantity": 10, "confidence": 0.9}
    entity = {"price": 5.0, "position_limit": 100.0}
    pdp.check(decision, entity)  # no raise
    assert pdp.allows(decision, entity)


def test_pdp_blocks_over_position_limit():
    pdp = PolicyDecisionPoint(load_bundle(_BUNDLE_DIR))
    decision = {"action_type": "buy", "quantity": 100, "confidence": 0.9}
    entity = {"price": 5.0, "position_limit": 100.0}
    with pytest.raises(PolicyViolation, match="position_limit"):
        pdp.check(decision, entity)


def test_pdp_blocks_negative_quantity():
    pdp = PolicyDecisionPoint(load_bundle(_BUNDLE_DIR))
    decision = {"action_type": "buy", "quantity": -1, "confidence": 0.9}
    entity = {"price": 1.0, "position_limit": 100.0}
    with pytest.raises(PolicyViolation, match="non_negative_quantity"):
        pdp.check(decision, entity)


def test_pdp_blocks_low_confidence_for_capital_action():
    pdp = PolicyDecisionPoint(load_bundle(_BUNDLE_DIR))
    decision = {"action_type": "raise_capital", "quantity": 0, "confidence": 0.3}
    entity = {"price": 0.0, "position_limit": 1e9}
    with pytest.raises(PolicyViolation, match="minimum_confidence"):
        pdp.check(decision, entity)


def test_pdp_rejects_uncovered_action_type():
    pdp = PolicyDecisionPoint(load_bundle(_BUNDLE_DIR))
    decision = {"action_type": "teleport", "quantity": 1, "confidence": 0.9}
    entity = {"price": 1.0, "position_limit": 100.0}
    with pytest.raises(PolicyViolation, match="no rule covers"):
        pdp.check(decision, entity)


def test_policy_version_is_the_digest():
    pdp = PolicyDecisionPoint(load_bundle(_BUNDLE_DIR))
    assert pdp.policy_version == pdp.bundle.digest


def test_bundle_digest_changes_when_rules_change(tmp_path):
    """Modifying the bundle.yaml changes the digest — proves audit linkage."""
    import shutil
    src = _BUNDLE_DIR
    dst = tmp_path / "bundle"
    shutil.copytree(src, dst)
    a = load_bundle(dst)
    # mutate
    (dst / "bundle.yaml").write_text(
        (dst / "bundle.yaml").read_text() + "\nextra_field: stuff\n"
    )
    b = load_bundle(dst)
    assert a.digest != b.digest
