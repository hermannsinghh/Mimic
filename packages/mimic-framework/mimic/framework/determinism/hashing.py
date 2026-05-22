"""world_state_hash Merkle-DAG — Plan §7.2.

    root = sha256(
        hash(entity_graph_state) ||
        hash(agent_memory_state) ||
        hash(market_state) ||
        hash(time_step)
    )

Each component is a sorted, canonical-JSON-serialized Merkle tree.

NEVER change this file without:
  1. A schema major version bump.
  2. Refreshing tests/determinism/golden/.
  3. An ADR in decision-record/.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

_COMPONENTS = ("entity_graph_state", "agent_memory_state", "market_state", "time_step")


def canonical_json(obj: Any) -> bytes:
    """Sorted keys, no whitespace, UTF-8 — the only on-wire JSON form for hashing."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _merkle_hash(value: Any) -> bytes:
    """Recursive Merkle hashing over dicts/lists; primitives hashed as canonical JSON."""
    if isinstance(value, dict):
        # sort keys, hash each (key, child_hash) pair, then hash the concatenation
        parts = b""
        for k in sorted(value.keys()):
            child = _merkle_hash(value[k])
            parts += _sha256(canonical_json(k) + child)
        return _sha256(b"D" + parts)
    if isinstance(value, list):
        parts = b""
        for item in value:
            parts += _merkle_hash(item)
        return _sha256(b"L" + parts)
    # primitive (str, int, float, bool, None)
    return _sha256(b"P" + canonical_json(value))


def world_state_hash(
    *,
    entity_graph_state: Any,
    agent_memory_state: Any,
    market_state: Any,
    time_step: Any,
) -> str:
    """Return the hex-encoded world_state_hash root.

    All four components are required (keyword-only) to make accidental
    omission impossible — drop a key and you get a different hash.
    """
    component_hashes = [
        _merkle_hash(entity_graph_state),
        _merkle_hash(agent_memory_state),
        _merkle_hash(market_state),
        _merkle_hash(time_step),
    ]
    root = _sha256(b"".join(component_hashes))
    return root.hex()
