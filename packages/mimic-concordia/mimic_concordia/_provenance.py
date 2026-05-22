"""Upstream-attribution constants for mimic-concordia.

These are recorded in code (not just NOTICE) so any consumer can introspect
the wrapper's pinned upstream version programmatically — useful for the
manifest emitted by `ScenarioRunner` and for the SBOM job in CI.
"""
from __future__ import annotations

from typing import Final

UPSTREAM_PYPI: Final[str] = "gdm-concordia"
UPSTREAM_VERSION: Final[str] = "2.0.1"
UPSTREAM_LICENSE: Final[str] = "Apache-2.0"
UPSTREAM_LICENSE_SPDX: Final[str] = "Apache-2.0"
UPSTREAM_HOME: Final[str] = "https://github.com/google-deepmind/concordia"
UPSTREAM_COPYRIGHT: Final[str] = "Copyright 2023 DeepMind Technologies Limited."

VENDORING_STRATEGY: Final[str] = "pinned-dep"
VENDORING_ADR: Final[str] = "decision-record/2026-05-22-concordia-vendoring-strategy.md"
