"""Adapter: Mimic ``LLMProvider`` → Concordia ``LanguageModel``.

Concordia's component pipeline calls ``LanguageModel.sample_text(prompt)`` and
``sample_choice(prompt, responses)``. Mimic providers expose
``complete(messages=…, schema=…, …)`` and always return a structured dict.

The adapter:

* Wraps the prompt into a single user message so the Mimic provider's contract
  is honored. Concordia bakes everything (instructions, observations,
  components) into the prompt itself — there is no separate "system" role
  in Concordia's API — so the adapter uses ``DEFAULT_SYSTEM_PROMPT`` as a
  stable, version-pinned constant. Changing that constant is a deliberate
  cache-invalidation event (all cassettes go stale), which matches Plan
  §7.3's design and the prefab-author skill's "expect cassette churn" note.

* For ``sample_text`` we ask for ``content={"text": "…"}`` by passing no
  schema; if the response dict has no "text" key we fall back to a stable
  ``json.dumps(content, sort_keys=True)`` so the contract is total. Live
  Mimic providers MUST honor the ``schema=None → {"text": str}`` convention
  for the adapter to be useful in production; the fallback is just a
  defensive belt-and-braces for test stubs.

* For ``sample_choice`` we ask the provider for an integer index via a tiny
  inline schema. This is the only place the adapter changes shape based on
  Concordia's call-style, so the cache-key invariant from
  ``test_cache_key_composition.py`` still holds — every distinct shape gets
  a distinct fingerprint, and re-runs with the same shape hit the same key.
"""
from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from typing import Any, Final

from ...routing.provider import LLMProvider

# Importing concordia is deferred until class body runtime so importing
# `mimic.framework.agents.concordia_runtime` without `mimic-concordia`
# installed gives a clean error message at the right layer (see builder.py).
# All concordia access routes through `mimic_concordia.*` so the wrapper
# boundary in ADR 2026-05-22-concordia-vendoring-strategy.md is preserved.
try:
    from mimic_concordia import language_model as _cc_lm
    _LanguageModel = _cc_lm.LanguageModel
    _DEFAULT_TEMPERATURE: float = _cc_lm.DEFAULT_TEMPERATURE
    _DEFAULT_MAX_TOKENS: int = _cc_lm.DEFAULT_MAX_TOKENS
    _DEFAULT_TIMEOUT_SECONDS: float = _cc_lm.DEFAULT_TIMEOUT_SECONDS
    _DEFAULT_TERMINATORS: tuple[str, ...] = tuple(_cc_lm.DEFAULT_TERMINATORS)
    _CONCORDIA_AVAILABLE = True
except ImportError:  # pragma: no cover — exercised only when mimic-concordia is absent
    _LanguageModel = object  # type: ignore[assignment, misc]
    _DEFAULT_TEMPERATURE = 0.5
    _DEFAULT_MAX_TOKENS = 256
    _DEFAULT_TIMEOUT_SECONDS = 60.0
    _DEFAULT_TERMINATORS = ()
    _CONCORDIA_AVAILABLE = False


# Stable, version-pinned system prompt used for every Concordia-routed call.
# Bumping this string invalidates every recorded cassette — that is intentional
# (see prefab-author skill, "Expect cassette churn"). Treat changes here the
# same as a Mimic schema change: they require a fresh cassette recording pass
# and a note in the F-12 release record.
DEFAULT_SYSTEM_PROMPT: Final[str] = (
    "You are reasoning as an entity inside an audit-grade multi-agent "
    "stress-test simulation. Answer ONLY with the structured content the "
    "tool schema requests. If no schema is given, reply with a JSON object "
    'of the form {"text": "<your reply>"}.'
)


class MimicProviderAsConcordiaLM(_LanguageModel):  # type: ignore[misc, valid-type]
    """Concordia ``LanguageModel`` backed by a Mimic ``LLMProvider``.

    The provider is expected to be wrapped in ``FrozenRunProvider`` whenever
    audit-grade reproducibility is required — the adapter itself doesn't
    enforce that, because the ``ScenarioRunner`` already does (see
    ADR ``decision-record/2026-05-21-audit-grade-refusal.md``).
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        if not _CONCORDIA_AVAILABLE:
            raise ImportError(
                "MimicProviderAsConcordiaLM requires mimic-concordia. "
                "Install with: pip install mimic-framework[concordia]"
            )
        # Concordia's LanguageModel ABC has no __init__ contract, so this
        # is effectively a fresh start.
        self._provider = provider
        self._system_prompt = system_prompt

    # ── Concordia LanguageModel API ──────────────────────────────────────

    def sample_text(
        self,
        prompt: str,
        *,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        terminators: Collection[str] = _DEFAULT_TERMINATORS,
        temperature: float = _DEFAULT_TEMPERATURE,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        seed: int | None = None,
    ) -> str:
        # max_tokens / terminators / timeout are not part of the Mimic
        # LLMProvider Protocol — providers honor them best-effort via their
        # native config. They're recorded here for completeness so the
        # adapter doesn't silently drop information passed by Concordia.
        del max_tokens, terminators, timeout
        response = self._provider.complete(
            messages=[{"role": "user", "content": prompt}],
            schema=None,
            tools=None,
            temperature=temperature,
            seed=seed,
            system_prompt=self._system_prompt,
        )
        content = response.content
        text = content.get("text") if isinstance(content, dict) else None
        if isinstance(text, str):
            return text
        # Belt-and-braces fallback. A live provider that honors the
        # `schema=None → {"text": str}` convention will never reach this.
        return json.dumps(content, sort_keys=True)

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ) -> tuple[int, str, Mapping[str, Any]]:
        if not responses:
            raise ValueError("sample_choice: responses must be non-empty")
        choice_schema = {
            "type": "object",
            "properties": {
                "index": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": len(responses) - 1,
                },
            },
            "required": ["index"],
        }
        framed = (
            prompt
            + "\n\nPick the best response by index from the following list, "
            "and reply with a JSON object {\"index\": <int>}:\n"
            + "\n".join(f"  [{i}] {r}" for i, r in enumerate(responses))
        )
        response = self._provider.complete(
            messages=[{"role": "user", "content": framed}],
            schema=choice_schema,
            tools=None,
            temperature=0.0,
            seed=seed,
            system_prompt=self._system_prompt,
        )
        idx_raw = response.content.get("index") if isinstance(response.content, dict) else None
        try:
            idx = int(idx_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"sample_choice: provider returned non-integer index {idx_raw!r}"
            ) from exc
        if not 0 <= idx < len(responses):
            raise ValueError(
                f"sample_choice: index {idx} outside [0, {len(responses)})"
            )
        info: dict[str, Any] = {
            "model_fingerprint": response.model_fingerprint,
            "confidence": response.confidence,
        }
        return idx, responses[idx], info
