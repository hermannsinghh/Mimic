"""Concordia runtime — Plan §9.1, F-12.

Glue between the locked ``PersonaBuilder`` contract (ADR
``decision-record/2026-05-21-audit-grade-refusal.md``) and the existing
``Prefab`` cascade (Plan §9.2). The runtime wraps DeepMind Concordia agents
(via ``mimic-concordia``) so a scenario can produce ``Decision``s that:

  * carry the Concordia agent's reasoning trace through the Mimic ``Prefab``;
  * still pass through the ``RoutingCascade`` → ``PolicyDecisionPoint`` →
    ``Decision`` emission contract;
  * declare ``is_deterministic = False`` so ``ScenarioRunner`` either insists
    on frozen-run mode or refuses to emit a hash.

All Concordia imports go through ``mimic_concordia.*``, never ``concordia.*``.
That keeps the single swap point promised by ADR
``decision-record/2026-05-22-concordia-vendoring-strategy.md`` honest.

Public surface:

    ConcordiaPersonaBuilder      — the PersonaBuilder
    MimicProviderAsConcordiaLM   — adapter wrapping LLMProvider as Concordia LM
    SHA256UnitEmbedder           — deterministic stub embedder for tests
    DEFAULT_SYSTEM_PROMPT        — the stable string the LM adapter uses
"""
from __future__ import annotations

from .builder import ConcordiaPersonaBuilder, ConcordiaRuntimeImportError
from .embedder import SHA256UnitEmbedder
from .language_model import DEFAULT_SYSTEM_PROMPT, MimicProviderAsConcordiaLM

__all__ = [
    "ConcordiaPersonaBuilder",
    "ConcordiaRuntimeImportError",
    "MimicProviderAsConcordiaLM",
    "SHA256UnitEmbedder",
    "DEFAULT_SYSTEM_PROMPT",
]
