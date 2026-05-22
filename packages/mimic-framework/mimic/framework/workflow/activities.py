"""Temporal activities — Plan §8.

Each activity is a pure async function. The `@activity.defn` decoration is
applied if temporalio is installed; otherwise the bare function is exported
for offline testing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from temporalio import activity  # type: ignore[import-not-found]
    _DEFN = activity.defn
except ImportError:  # pragma: no cover - exercised when temporalio missing
    def _DEFN(fn=None, *, name: str | None = None):
        if fn is None:
            return lambda f: f
        return fn


@dataclass(frozen=True)
class DataRef:
    """A reference to fetched data — content-addressed, signed."""
    source: str
    digest: str
    record_count: int


@_DEFN
async def pull_signed_scenario(scenario_uri: str) -> dict[str, Any]:
    """Pull a scenario artifact from Mimic Hub and verify its Sigstore signature.

    TODO (F-02, F-03): replace with oras-py pull + cosign verify.
    """
    raise NotImplementedError("F-02/F-03 not yet implemented")


@_DEFN
async def fetch_source(source: str, as_of: str) -> DataRef:
    """Fetch data from a connector and return a content-addressed reference."""
    raise NotImplementedError("requires connector wiring in mimic.framework.signal.sources")


@_DEFN
async def propagate_contagion(outcomes: list[dict]) -> dict[str, Any]:
    """Run EN + DebtRank propagation over the outcome set.

    Delegates to `mimic_world.contagion.eisenberg_noe_clearing` + DebtRank.
    """
    raise NotImplementedError("requires liability matrix wiring (W-04)")


@_DEFN
async def sign_run_manifest(cascade_result: dict) -> dict[str, Any]:
    """Sign the final run manifest with cosign — emits Rekor entry."""
    raise NotImplementedError("F-03 not yet implemented")
