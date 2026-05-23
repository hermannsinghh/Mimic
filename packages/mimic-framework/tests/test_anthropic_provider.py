"""Tests for ``mimic.framework.routing.anthropic.AnthropicProvider``.

No live HTTP. A fake client mimics the relevant slice of
``anthropic.Anthropic().messages.create`` so we exercise the adapter's
JSON parsing, model_fingerprint composition, cost math, and StructuredResponse
mapping without burning API credits in CI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from mimic.framework.routing import (
    AnthropicJSONParseError,
    AnthropicProvider,
    StructuredResponse,
    compute_model_fingerprint,
)


# ── fake anthropic client ──────────────────────────────────────────────────


@dataclass
class _FakeUsage:
    input_tokens: int = 12
    output_tokens: int = 8


@dataclass
class _FakeBlock:
    type: str
    text: str | None = None


@dataclass
class _FakeMessage:
    content: list[_FakeBlock]
    usage: _FakeUsage = field(default_factory=_FakeUsage)


class _FakeMessages:
    def __init__(self, response_text: str = '{"text": "ok"}',
                 input_tokens: int = 12, output_tokens: int = 8) -> None:
        self._response_text = response_text
        self._usage = _FakeUsage(input_tokens=input_tokens, output_tokens=output_tokens)
        self.calls: list[dict] = []

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.calls.append(kwargs)
        return _FakeMessage(
            content=[_FakeBlock(type="text", text=self._response_text)],
            usage=self._usage,
        )


class _FakeClient:
    def __init__(self, response_text: str = '{"text": "ok"}',
                 input_tokens: int = 12, output_tokens: int = 8) -> None:
        self.messages = _FakeMessages(
            response_text=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


# ── happy path ─────────────────────────────────────────────────────────────


def test_complete_returns_structured_response_with_parsed_content():
    client = _FakeClient(response_text='{"text": "hello"}')
    p = AnthropicProvider(client=client, model="claude-opus-4-5", model_version="2026-04")
    r = p.complete(
        messages=[{"role": "user", "content": "hi"}],
        schema=None, tools=None, temperature=0.0, seed=None,
        system_prompt="be helpful",
    )
    assert isinstance(r, StructuredResponse)
    assert r.content == {"text": "hello"}
    assert r.input_tokens == 12
    assert r.output_tokens == 8


def test_cost_matches_estimate_per_million_tokens():
    client = _FakeClient(input_tokens=1_000_000, output_tokens=500_000)
    p = AnthropicProvider(client=client, cost_in_per_m=5.0, cost_out_per_m=25.0)
    r = p.complete(
        messages=[{"role": "user", "content": "x"}],
        schema=None, tools=None, temperature=0.0, seed=None,
    )
    # 1.0 × 5 + 0.5 × 25 = 17.5
    assert r.cost_usd == pytest.approx(17.5)


def test_estimate_cost_usd_matches_cost_table():
    p = AnthropicProvider(client=_FakeClient(), cost_in_per_m=5.0, cost_out_per_m=25.0)
    # Plan §4.2: Claude Opus 4.5 = 5/25
    assert p.estimate_cost_usd(1_000_000, 0) == pytest.approx(5.0)
    assert p.estimate_cost_usd(0, 1_000_000) == pytest.approx(25.0)


def test_model_fingerprint_matches_compute_helper():
    client = _FakeClient()
    p = AnthropicProvider(client=client, model="claude-opus-4-5", model_version="2026-04")
    r = p.complete(
        messages=[{"role": "user", "content": "x"}],
        schema=None, tools=None, temperature=0.3, seed=None,
        system_prompt="be terse",
    )
    expected = compute_model_fingerprint(
        provider="anthropic", model="claude-opus-4-5", version="2026-04",
        system_prompt="be terse", temperature=0.3, tool_schema=None,
    )
    assert r.model_fingerprint == expected


def test_system_prompt_passed_to_client_when_nonempty():
    client = _FakeClient()
    p = AnthropicProvider(client=client)
    p.complete(messages=[{"role": "user", "content": "x"}],
               schema=None, tools=None, temperature=0.0, seed=None,
               system_prompt="be careful")
    assert client.messages.calls[-1]["system"] == "be careful"


def test_system_prompt_omitted_when_empty():
    client = _FakeClient()
    p = AnthropicProvider(client=client)
    p.complete(messages=[{"role": "user", "content": "x"}],
               schema=None, tools=None, temperature=0.0, seed=None)
    assert "system" not in client.messages.calls[-1]


def test_tools_forwarded_when_given():
    client = _FakeClient()
    p = AnthropicProvider(client=client)
    tools = [{"name": "x", "description": "y", "input_schema": {"type": "object"}}]
    p.complete(messages=[{"role": "user", "content": "x"}],
               schema=None, tools=tools, temperature=0.0, seed=None)
    assert client.messages.calls[-1]["tools"] == tools


def test_seed_ignored_silently():
    """Anthropic API has no public seed parameter; the adapter must
    accept ``seed`` to honor the Protocol but never forward it."""
    client = _FakeClient()
    p = AnthropicProvider(client=client)
    p.complete(messages=[{"role": "user", "content": "x"}],
               schema=None, tools=None, temperature=0.0, seed=42)
    assert "seed" not in client.messages.calls[-1]


def test_confidence_from_content_when_present():
    client = _FakeClient(response_text='{"text": "yes", "confidence": 0.42}')
    p = AnthropicProvider(client=client)
    r = p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)
    assert r.confidence == pytest.approx(0.42)


def test_confidence_default_when_absent():
    client = _FakeClient(response_text='{"text": "yes"}')
    p = AnthropicProvider(client=client)
    r = p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)
    assert r.confidence == pytest.approx(0.85)


# ── JSON parsing edge cases ────────────────────────────────────────────────


def test_parses_json_wrapped_in_code_fences():
    client = _FakeClient(response_text='```json\n{"action": "hold"}\n```')
    p = AnthropicProvider(client=client)
    r = p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)
    assert r.content == {"action": "hold"}


def test_raises_on_empty_text():
    client = _FakeClient(response_text="")
    p = AnthropicProvider(client=client)
    with pytest.raises(AnthropicJSONParseError, match="empty"):
        p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)


def test_raises_on_no_json():
    client = _FakeClient(response_text="just prose, no JSON here")
    p = AnthropicProvider(client=client)
    with pytest.raises(AnthropicJSONParseError, match="no JSON object"):
        p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)


def test_raises_on_non_object_json():
    client = _FakeClient(response_text="[1, 2, 3]")
    p = AnthropicProvider(client=client)
    with pytest.raises(AnthropicJSONParseError, match="not dict"):
        p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)


# ── Protocol identity ──────────────────────────────────────────────────────


def test_provider_satisfies_llmprovider_protocol():
    """``runtime_checkable`` Protocol check — confirms the adapter shape."""
    from mimic.framework.routing import LLMProvider
    p = AnthropicProvider(client=_FakeClient())
    assert isinstance(p, LLMProvider)


def test_provider_attributes_exposed():
    p = AnthropicProvider(client=_FakeClient(),
                          model="claude-opus-4-5", model_version="2026-04")
    assert p.provider_name == "anthropic"
    assert p.model_name == "claude-opus-4-5"
    assert p.model_version == "2026-04"
