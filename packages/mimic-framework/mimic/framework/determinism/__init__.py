"""Determinism, audit, replay — Plan §7.

- SeedManifest: HKDF-derived per-shard/per-agent seeds.
- world_state_hash: Merkle-DAG over entity_graph, agent_memory, market, time.
- Frozen-run mode: LLM responses keyed by content hash on S3.
- GPU determinism: pinned CUDA/PyTorch image, batch-invariant vLLM.
"""
from .frozen import (  # noqa: F401
    CacheBackend,
    FrozenRunProvider,
    LocalFSBackend,
    RecordingProvider,
    S3Backend,
    SSEConfig,
    compute_cache_key,
    is_frozen_run,
)
from .hashing import canonical_json, world_state_hash  # noqa: F401
from .seed import SeedManifest  # noqa: F401

__all__ = [
    "SeedManifest",
    "world_state_hash",
    "canonical_json",
    "is_frozen_run",
    "compute_cache_key",
    "CacheBackend",
    "LocalFSBackend",
    "S3Backend",
    "SSEConfig",
    "FrozenRunProvider",
    "RecordingProvider",
]
