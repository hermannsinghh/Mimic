"""Anthropic ``LLMProvider`` adapter — Plan §4.2 row 1 (Claude Opus 4.5, T1).

Concrete implementation of ``mimic.framework.routing.provider.LLMProvider``
that talks to the Anthropic API via the ``anthropic`` Python SDK. The
adapter is intentionally thin: every contract from the LLMProvider
Protocol maps to one ``anthropic.Anthropic().messages.create`` call, and
the structured-output convention is "model returns JSON in a free-text
reply, the provider parses it." Tool use is not used for v0 — every Mimic
caller already gives the model a system prompt that names the expected
JSON shape (``ReinsurerTreatyPricer.system_prompt`` etc.), and Claude
Opus reliably emits compliant JSON when instructed.

Audit-grade reproducibility is *not* guaranteed by this provider alone —
Anthropic's API has no seed parameter. The only audit-grade path is
``FrozenRunProvider(AnthropicProvider(...), backend=…)`` with primed
cassettes. See ADR ``decision-record/2026-05-21-audit-grade-refusal.md``
and Plan §7.3.

Cost table baked in matches Plan §4.2:

    Claude Opus 4.5   →  $5 / M input, $25 / M output
    Claude Sonnet 4.5 →  $3 / M input, $15 / M output

Callers can override via ``cost_in_per_m`` / ``cost_out_per_m`` for any
other model.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .provider import StructuredResponse, compute_model_fingerprint

# Default model identifier. Plan §4.2 originally named "Claude Opus 4.5" as
# T1; that alias is deprecated by Anthropic as of 2026-05, so the live default
# is ``claude-opus-4-7``. Divergence recorded in
# ``decision-record/2026-05-22-anthropic-model-choice.md``. Callers can pin to
# a dated version (e.g. ``claude-opus-4-7-20260415``) if cassette stability
# across alias drift is a concern — recording pinned to a dated version is
# the recommended path because the cassette is keyed off ``model_version``
# (see ``provider.compute_model_fingerprint``).
DEFAULT_MODEL: str = "claude-opus-4-7"
DEFAULT_MODEL_VERSION: str = "2026-04"  # placeholder — see "On model_version" in the docstring


class AnthropicJSONParseError(RuntimeError):
    """Raised when the Anthropic response cannot be parsed into a JSON object.

    Recording cassettes that contain unparseable responses would poison the
    fixture set; the recording session must fail loudly rather than swallow.
    """


class AnthropicProvider:
    """Talk to Anthropic. Returns ``StructuredResponse`` with parsed JSON content.

    Args:
        model: Anthropic model alias or dated version (e.g. ``claude-opus-4-5``,
            ``claude-opus-4-5-20260301``).
        model_version: a stable string folded into ``model_fingerprint``. For
            dated model IDs this is usually a trailing date stamp; for the
            family alias it should be a release-tracking string the operator
            pins themselves. Bumping it invalidates every cassette by design.
        api_key: Anthropic API key. If ``None``, the SDK resolves
            ``ANTHROPIC_API_KEY`` from the environment.
        max_tokens: per-call max output tokens. Defaults to 4096 — Plan §4.2
            doesn't pin a value, so this is a sensible cap that keeps cost
            bounded during recording. Anthropic requires this parameter.
        client: pre-constructed ``anthropic.Anthropic`` instance for tests.
            When provided, ``api_key`` is ignored.
        cost_in_per_m / cost_out_per_m: $ per million tokens, used by
            ``estimate_cost_usd`` and ``cost_usd`` on the returned response.
    """

    provider_name: str = "anthropic"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        model_version: str = DEFAULT_MODEL_VERSION,
        api_key: str | None = None,
        max_tokens: int = 4096,
        client: Any | None = None,
        cost_in_per_m: float = 5.0,
        cost_out_per_m: float = 25.0,
    ) -> None:
        self.model_name = model
        self.model_version = model_version
        self._max_tokens = max_tokens
        self._cost_in_per_m = cost_in_per_m
        self._cost_out_per_m = cost_out_per_m
        if client is not None:
            self._client = client
        else:
            try:
                import anthropic  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover
                raise ImportError(
                    "AnthropicProvider requires the 'anthropic' SDK. "
                    "Install with: pip install anthropic"
                ) from exc
            self._client = anthropic.Anthropic(api_key=api_key)

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
        # ``seed`` is accepted to honor the Protocol but Anthropic's API has
        # no public seed parameter. Folded into model_fingerprint already via
        # the system_prompt+temperature+tool_schema triple (Plan §4.2 spec).
        del seed
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": self._max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools
        message = self._client.messages.create(**kwargs)

        text = _extract_text(message)
        content = _parse_json_content(text)
        usage_in = int(getattr(message.usage, "input_tokens", 0))
        usage_out = int(getattr(message.usage, "output_tokens", 0))
        cost = self.estimate_cost_usd(usage_in, usage_out)

        fingerprint = compute_model_fingerprint(
            provider=self.provider_name,
            model=self.model_name,
            version=self.model_version,
            system_prompt=system_prompt,
            temperature=temperature,
            tool_schema=tools[0] if tools else None,
        )
        # confidence is a soft signal — prefer model-asserted value if
        # present in the parsed content, else a fixed Opus prior of 0.85.
        confidence_value: Any = content.get("confidence") if isinstance(content, dict) else None
        confidence = (
            float(confidence_value) if isinstance(confidence_value, (int, float)) else 0.85
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


def _extract_text(message: Any) -> str:
    """Concat every text block in the Anthropic ``Message`` response.

    The SDK returns ``message.content`` as a list of blocks each with a
    ``type`` field. We only consume ``"text"`` blocks — tool_use, image,
    etc. are not supported in this v0 adapter.
    """
    blocks = getattr(message, "content", []) or []
    parts: list[str] = []
    for block in blocks:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_content(text: str) -> dict[str, Any]:
    r"""Parse Claude's response text into a JSON object dict.

    First attempts a strict ``json.loads`` on the whole string. If that
    fails (e.g. Claude wrapped the JSON in ```json … ``` fences), falls
    back to extracting the first ``{…}`` span via regex. Raises
    ``AnthropicJSONParseError`` if neither path produces a dict.
    """
    if not text.strip():
        raise AnthropicJSONParseError("Anthropic returned empty text content")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_OBJECT_RE.search(text)
        if not m:
            raise AnthropicJSONParseError(
                f"no JSON object found in Anthropic response: {text[:200]!r}"
            )
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            raise AnthropicJSONParseError(
                f"JSON parse failed inside extracted block: {exc}; "
                f"text head: {text[:200]!r}"
            ) from exc
    if not isinstance(parsed, dict):
        raise AnthropicJSONParseError(
            f"Anthropic response parsed to {type(parsed).__name__}, not dict"
        )
    return parsed
