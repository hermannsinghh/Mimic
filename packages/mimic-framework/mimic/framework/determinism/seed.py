"""SeedManifest — Plan §7.1.

HKDF-SHA256 derivation of per-shard and per-agent seeds from a single global_seed.

NEVER change derivation without a schema major version bump
and updating the golden vectors in tests/determinism/golden/.
"""
from __future__ import annotations

from typing import Literal

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import BaseModel

_KDF_LEN = 8  # 64 bits per derived seed


class SeedManifest(BaseModel):
    global_seed: int
    derivation: Literal["HKDF-SHA256"] = "HKDF-SHA256"
    per_shard_label: str = "shard"
    per_agent_label: str = "agent"

    def _derive(self, info: bytes) -> int:
        salt = b"mimic.framework.determinism.SeedManifest/v1"
        ikm = self.global_seed.to_bytes(32, "big", signed=False)
        kdf = HKDF(algorithm=hashes.SHA256(), length=_KDF_LEN, salt=salt, info=info)
        return int.from_bytes(kdf.derive(ikm), "big", signed=False)

    def per_shard_seed(self, shard_idx: int) -> int:
        if shard_idx < 0:
            raise ValueError("shard_idx must be non-negative")
        return self._derive(f"{self.per_shard_label}/{shard_idx}".encode())

    def per_agent_seed(self, agent_did: str) -> int:
        if not agent_did:
            raise ValueError("agent_did must be non-empty")
        return self._derive(f"{self.per_agent_label}/{agent_did}".encode())
