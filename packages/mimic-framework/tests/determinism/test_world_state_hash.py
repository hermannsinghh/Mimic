"""Golden vector tests for world_state_hash and SeedManifest.

Vectors live at <repo-root>/tests/determinism/golden/. Any failure here means
either a determinism contract change (requires schema major bump + ADR) OR a
bug. Default assumption: it's a bug. Don't auto-update the goldens.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mimic.framework.determinism import SeedManifest, world_state_hash

_REPO_ROOT = Path(__file__).resolve().parents[4]
_GOLDEN = _REPO_ROOT / "tests" / "determinism" / "golden"


def _load(name: str) -> dict:
    return json.loads((_GOLDEN / name).read_text())


def test_world_state_hash_golden_vectors():
    data = _load("world_state_hash_v1.json")
    for vec in data["vectors"]:
        actual = world_state_hash(**vec["input"])
        assert actual == vec["expected_hash"], (
            f"world_state_hash drift on '{vec['name']}'. "
            f"Expected {vec['expected_hash']}, got {actual}. "
            f"If this is intentional, bump schema major + write ADR."
        )


def test_world_state_hash_is_deterministic_across_calls():
    a = world_state_hash(
        entity_graph_state={"x": 1}, agent_memory_state={}, market_state={}, time_step=0
    )
    b = world_state_hash(
        entity_graph_state={"x": 1}, agent_memory_state={}, market_state={}, time_step=0
    )
    assert a == b


def test_world_state_hash_changes_when_any_component_changes():
    base = world_state_hash(
        entity_graph_state={"x": 1}, agent_memory_state={}, market_state={}, time_step=0
    )
    perturbations = [
        {"entity_graph_state": {"x": 2}, "agent_memory_state": {}, "market_state": {}, "time_step": 0},
        {"entity_graph_state": {"x": 1}, "agent_memory_state": {"m": "v"}, "market_state": {}, "time_step": 0},
        {"entity_graph_state": {"x": 1}, "agent_memory_state": {}, "market_state": {"spx": 1.0}, "time_step": 0},
        {"entity_graph_state": {"x": 1}, "agent_memory_state": {}, "market_state": {}, "time_step": 1},
    ]
    for p in perturbations:
        assert world_state_hash(**p) != base, f"hash failed to change for perturbation {p}"


def test_seed_manifest_golden_vectors():
    data = _load("seed_manifest_v1.json")
    for vec in data["vectors"]:
        m = SeedManifest(global_seed=vec["global_seed"])
        for shard_idx_str, expected_hex in vec["per_shard"].items():
            assert hex(m.per_shard_seed(int(shard_idx_str))) == expected_hex
        for agent_did, expected_hex in vec["per_agent"].items():
            assert hex(m.per_agent_seed(agent_did)) == expected_hex


def test_seed_manifest_rejects_invalid_inputs():
    m = SeedManifest(global_seed=42)
    with pytest.raises(ValueError):
        m.per_shard_seed(-1)
    with pytest.raises(ValueError):
        m.per_agent_seed("")


def test_seed_manifest_different_shards_give_different_seeds():
    m = SeedManifest(global_seed=42)
    seeds = {m.per_shard_seed(i) for i in range(100)}
    assert len(seeds) == 100, "HKDF derivation collided across 100 shards"
