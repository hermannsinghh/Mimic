"""Deterministic stub embedder for Concordia ``AssociativeMemoryBank``.

Concordia's memory bank refuses to accept text unless an embedder is set
(``ValueError: Embedder must be set before calling 'add' method.``). For
unit tests and noise-floor measurement we need a stable, reproducible
embedder that does NOT require downloading sentence-transformer weights.

``SHA256UnitEmbedder`` derives a unit vector from ``sha256(text)`` —

* Deterministic: same text → same vector across runs and machines.
* Identity-distinguishing: different texts almost always produce different
  vectors (sha256 collisions are not a real concern).
* Cheap: 64 floats per call, no model load.

It is NOT semantically meaningful — two semantically identical sentences
get different vectors if the byte string differs. That matters for any
"retrieve similar memories" component; for the minimal-prefab path that
only calls ``LastNObservations`` (no retrieval) the embedder's similarity
behavior is irrelevant.

Production callers should pass a real sentence-transformer or a hosted
embedding model. The adapter is fully overridable via
``ConcordiaPersonaBuilder(embedder=…)``.
"""
from __future__ import annotations

import hashlib

import numpy as np


class SHA256UnitEmbedder:
    """Hash-based deterministic embedder. Returns a 64-dim unit vector."""

    dim: int = 64

    def __call__(self, text: str) -> np.ndarray:
        # Each sha256 digest gives 32 bytes; expand to 64 floats by reading
        # the digest twice with different salts, then normalize.
        raw_a = hashlib.sha256(("a:" + text).encode("utf-8")).digest()
        raw_b = hashlib.sha256(("b:" + text).encode("utf-8")).digest()
        arr = np.frombuffer(raw_a + raw_b, dtype=np.uint8).astype(np.float64)
        # Center to [-1, 1] then normalize.
        centered = (arr - 127.5) / 127.5
        norm = float(np.linalg.norm(centered))
        if norm == 0.0:
            # Vanishingly improbable — fall back to a fixed unit vector so
            # the caller never sees a NaN.
            unit = np.zeros(self.dim, dtype=np.float64)
            unit[0] = 1.0
            return unit
        return centered / norm
