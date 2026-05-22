"""Descriptive narrative layer over EN + DebtRank primitives — Plan §3.3 W-03.

`CascadeEngine` and its supporting types live here. They consume the provably-
correct contagion math in `mimic_world.contagion` (Eisenberg-Noe clearing
vector, DebtRank) and overlay a narrative — sector affinities, persona action
descriptions, qualitative impact bands — useful for human-facing reports and
prose summaries.

Anything in this module is *descriptive*, not load-bearing for audit. The
canonical contagion answers come from `mimic_world.contagion`.
"""
from ..cascade import CascadeEngine  # noqa: F401  re-export

__all__ = ["CascadeEngine"]
