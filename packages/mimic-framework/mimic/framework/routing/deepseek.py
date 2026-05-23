"""DeepSeek ``LLMProvider`` adapter — Plan §4.2 row 6 (V3.2, T3).

DeepSeek's chat-completion API is OpenAI-compatible: same endpoint shape,
just point the ``openai`` SDK at ``https://api.deepseek.com``. This adapter
satisfies the same ``LLMProvider`` Protocol as ``AnthropicProvider`` so
either can sit behind the cascade, ``RecordingProvider``, ``FrozenRunProvider``,
or the ``ConcordiaPersonaBuilder`` LM bridge.

Use cases inside Mimic:

* **Plan §4.2 T3**: the cheapest cascade tier. T3 → T2 → T1 escalation
  decisions are checked here when confidence drops.
* **Development-grade cassettes for F-12 step 3.** Until an Anthropic key
  is available, the lighthouse cassettes can be recorded against DeepSeek
  for forward progress; they live in a clearly-marked separate fixture
  directory (``svb-replay-2023-deepseek/``) and are NOT the audit baseline.
  Re-record against ``claude-opus-4-7`` to land the canonical fixtures —
  see ``decision-record/2026-05-22-anthropic-model-choice.md`` for the
  canonical model and ADR ``2026-05-21-runner-equivalence-criterion.md``
  for why the baseline matters.
* **Noise-floor measurement**. Running ``measure_noise_floor`` against
  ``DeepSeekProvider`` produces a real (DeepSeek-shaped) noise floor that
  can pre-screen the ADR's threshold table before the canonical Anthropic
  measurement lands.

Cost table baked in matches Plan §4.2:

    DeepSeek V3.2  →  $0.28 / M input, $0.42 / M output

Same JSON-parsing convention as ``AnthropicProvider``: model returns JSON
in the text response, the provider parses it; ``DeepSeekJSONParseError``
raises rather than poisons cassettes.
"""
from __future__ import annotations

import re
from typing import Any

from .anthropic import _JSON_OBJECT_RE  # share the parse regex
from .provider import StructuredResponse, compute_model_fingerprint

# Default model identifier per the existing deepseek.env convention in
# ``mimic/llm.py`` (DEEPSEEK_MODEL=deepseek-chat). The chat alias maps to
# DeepSeek V3.2 today. Pin via ``model_version`` for cassette stability.
DEFAULT_MODEL: str = "deepseek-chat"
DEFAULT_MODEL_VERSION: str = "v3.2"
DEFAULT_BASE_URL: str = "https://api.deepseek.com"


class DeepSeekJSONParseError(RuntimeError):
    """Raised when DeepSeek's response can't be parsed into a JSON object.

    Symmetric with ``AnthropicJSONParseError``: a recording session that
    hit a malformed response should fail loudly rather than silently
    cassette a broken fixture.
    """


class DeepSeekProvider:
    """Talk to DeepSeek via the OpenAI-compatible chat-completions endpoint.

    Args:
        model: DeepSeek model alias (``deepseek-chat``, ``deepseek-reasoner``,
            etc.). Defaults to ``deepseek-chat`` matching the existing
            ``mimic/llm.py`` convention.
        model_version: stable string folded into ``model_fingerprint``.
            Bumping it invalidates cassettes by design.
        api_key: DeepSeek API key. If ``None``, resolves ``DEEPSEEK_API_KEY``.
        base_url: DeepSeek API base URL. If ``None``, uses
            ``DEEPSEEK_BASE_URL`` env var or the documented default.
        max_tokens: per-call cap on output tokens. Defaults to 4096.
        client: pre-constructed ``openai.OpenAI`` (used in tests). When
            provided, ``api_key`` and ``base_url`` are ignored.
        cost_in_per_m / cost_out_per_m: $ per million tokens (Plan §4.2).
    """

    provider_name: str = "deepseek"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        model_version: str = DEFAULT_MODEL_VERSION,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        client: Any | None = None,
        cost_in_per_m: float = 0.28,
        cost_out_per_m: float = 0.42,
    ) -> None:
        self.model_name = model
        self.model_version = model_version
        self._max_tokens = max_tokens
        self._cost_in_per_m = cost_in_per_m
        self._cost_out_per_m = cost_out_per_m
        if client is not None:
            self._client = client
            return
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "DeepSeekProvider requires the 'openai' SDK. "
                "Install with: pip install openai"
            ) from exc
        import os
        resolved_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "DeepSeekProvider needs DEEPSEEK_API_KEY (env var) or an "
                "explicit api_key= argument."
            )
        resolved_base = base_url or os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
        self._client = OpenAI(api_key=resolved_key, base_url=resolved_base)

    # ── LLMProvider Protocol ──────────────────────────────────────────────

    def estimate_cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self._cost_in_per_m
            + output_tokens * self._cost_out_per_m
        ) / 1_000_000.0

    def complete(
        self,
        *,
        messages: list[dict],
        schema: dict | None,
        tools: list[dict] | None,
        temperature: float,
        seed: int | None,
        system_prompt: str = "",
    ) -> StructuredResponse:
        # OpenAI-compatible API conventionally encodes the system prompt
        # as the first message with role="system".
        chat_messages: list[dict] = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        chat_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": self._max_tokens,
        }
        # DeepSeek (and OpenAI) DO honor the seed parameter — pass it
        # through when provided. This is one of the few places where
        # seed flows end-to-end (Anthropic doesn't).
        if seed is not None:
            kwargs["seed"] = seed
        if tools:
            kwargs["tools"] = tools
        completion = self._client.chat.completions.create(**kwargs)

        text = _extract_chat_text(completion)
        content = _parse_json_content(text)
        usage_in = int(getattr(completion.usage, "prompt_tokens", 0))
        usage_out = int(getattr(completion.usage, "completion_tokens", 0))
        cost = self.estimate_cost_usd(usage_in, usage_out)

        fingerprint = compute_model_fingerprint(
            provider=self.provider_name,
            model=self.model_name,
            version=self.model_version,
            system_prompt=system_prompt,
            temperature=temperature,
            tool_schema=tools[0] if tools else None,
        )
        confidence_value: Any = content.get("confidence") if isinstance(content, dict) else None
        confidence = (
            float(confidence_value) if isinstance(confidence_value, (int, float)) else 0.8
        )
        return StructuredResponse(
            content=content,
            input_tokens=usage_in,
            output_tokens=usage_out,
            cost_usd=cost,
            confidence=confidence,
            model_fingerprint=fingerprint,
        )


# ── helpers ────────────────────────────────────────────────────────────────


def _extract_chat_text(completion: Any) -> str:
    """Pull text from the first choice of an OpenAI-style chat completion."""
    choices = getattr(completion, "choices", []) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    content = getattr(message, "content", None)
    return content if isinstance(content, str) else ""


def _parse_json_content(text: str) -> dict[str, Any]:
    r"""Parse DeepSeek's response text into a JSON object dict.

    Same convention as ``AnthropicProvider._parse_json_content``: try a
    strict ``json.loads``, fall back to extracting the first ``{…}`` span.
    """
    import json
    if not text.strip():
        raise DeepSeekJSONParseError("DeepSeek returned empty text content")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_OBJECT_RE.search(text)
        if not m:
            raise DeepSeekJSONParseError(
                f"no JSON object found in DeepSeek response: {text[:200]!r}"
            )
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            raise DeepSeekJSONParseError(
                f"JSON parse failed inside extracted block: {exc}; "
                f"text head: {text[:200]!r}"
            ) from exc
    if not isinstance(parsed, dict):
        raise DeepSeekJSONParseError(
            f"DeepSeek response parsed to {type(parsed).__name__}, not dict"
        )
    return parsed
