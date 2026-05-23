"""Tests for ``mimic.framework.routing.deepseek.DeepSeekProvider``.

Mirror of ``test_anthropic_provider.py`` against the OpenAI-compatible
DeepSeek API. No live HTTP — a fake ``client.chat.completions`` mimics
just enough of the SDK to exercise JSON parsing, model_fingerprint
composition, cost math (Plan §4.2 T3 prices), and seed forwarding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from mimic.framework.routing import (
    DeepSeekJSONParseError,
    DeepSeekProvider,
    StructuredResponse,
    compute_model_fingerprint,
)


# ── fake OpenAI-style client ───────────────────────────────────────────────


@dataclass
class _FakeUsage:
    prompt_tokens: int = 12
    completion_tokens: int = 8


@dataclass
class _FakeChatMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeChatMessage


@dataclass
class _FakeCompletion:
    choices: list[_FakeChoice]
    usage: _FakeUsage = field(default_factory=_FakeUsage)


class _FakeChatCompletions:
    def __init__(self, response_text: str = '{"text": "ok"}',
                 prompt_tokens: int = 12, completion_tokens: int = 8) -> None:
        self._response_text = response_text
        self._usage = _FakeUsage(prompt_tokens=prompt_tokens,
                                  completion_tokens=completion_tokens)
        self.calls: list[dict] = []

    def create(self, **kwargs: Any) -> _FakeCompletion:
        self.calls.append(kwargs)
        return _FakeCompletion(
            choices=[_FakeChoice(message=_FakeChatMessage(content=self._response_text))],
            usage=self._usage,
        )


class _FakeChat:
    def __init__(self, completions: _FakeChatCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, response_text: str = '{"text": "ok"}',
                 prompt_tokens: int = 12, completion_tokens: int = 8) -> None:
        self.chat = _FakeChat(_FakeChatCompletions(
            response_text=response_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ))


# ── happy path ─────────────────────────────────────────────────────────────


def test_complete_returns_structured_response_with_parsed_content():
    client = _FakeClient(response_text='{"text": "hello"}')
    p = DeepSeekProvider(client=client)
    r = p.complete(messages=[{"role": "user", "content": "hi"}],
                   schema=None, tools=None, temperature=0.0, seed=None)
    assert isinstance(r, StructuredResponse)
    assert r.content == {"text": "hello"}


def test_cost_matches_plan_4_2_t3_rates():
    """Plan §4.2: DeepSeek V3.2 = $0.28 / M input, $0.42 / M output."""
    client = _FakeClient(prompt_tokens=1_000_000, completion_tokens=500_000)
    p = DeepSeekProvider(client=client)  # default cost_in/out
    r = p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)
    # 1.0 * 0.28 + 0.5 * 0.42 = 0.49
    assert r.cost_usd == pytest.approx(0.49)


def test_system_prompt_passed_as_first_chat_message():
    """OpenAI-compat convention: system prompt becomes a role=system message."""
    client = _FakeClient()
    p = DeepSeekProvider(client=client)
    p.complete(messages=[{"role": "user", "content": "u"}],
               schema=None, tools=None, temperature=0.0, seed=None,
               system_prompt="be careful")
    sent = client.chat.completions.calls[-1]
    assert sent["messages"][0] == {"role": "system", "content": "be careful"}
    assert sent["messages"][1] == {"role": "user", "content": "u"}


def test_no_system_message_when_system_prompt_empty():
    client = _FakeClient()
    p = DeepSeekProvider(client=client)
    p.complete(messages=[{"role": "user", "content": "u"}],
               schema=None, tools=None, temperature=0.0, seed=None)
    sent = client.chat.completions.calls[-1]
    assert sent["messages"] == [{"role": "user", "content": "u"}]


def test_seed_forwarded_when_provided():
    """Unlike Anthropic, DeepSeek (OpenAI-compat) honors seed — pass it
    through so audit-grade replays can attempt bit-stability when the
    provider supports it."""
    client = _FakeClient()
    p = DeepSeekProvider(client=client)
    p.complete(messages=[{"role": "user", "content": "x"}],
               schema=None, tools=None, temperature=0.0, seed=12345)
    assert client.chat.completions.calls[-1]["seed"] == 12345


def test_seed_omitted_when_none():
    client = _FakeClient()
    p = DeepSeekProvider(client=client)
    p.complete(messages=[{"role": "user", "content": "x"}],
               schema=None, tools=None, temperature=0.0, seed=None)
    assert "seed" not in client.chat.completions.calls[-1]


def test_tools_forwarded():
    client = _FakeClient()
    p = DeepSeekProvider(client=client)
    tools = [{"type": "function", "function": {"name": "f"}}]
    p.complete(messages=[{"role": "user", "content": "x"}],
               schema=None, tools=tools, temperature=0.0, seed=None)
    assert client.chat.completions.calls[-1]["tools"] == tools


def test_model_fingerprint_matches_compute_helper():
    client = _FakeClient()
    p = DeepSeekProvider(client=client, model="deepseek-chat", model_version="v3.2")
    r = p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.3, seed=None,
                   system_prompt="be terse")
    expected = compute_model_fingerprint(
        provider="deepseek", model="deepseek-chat", version="v3.2",
        system_prompt="be terse", temperature=0.3, tool_schema=None,
    )
    assert r.model_fingerprint == expected


def test_confidence_from_content_when_present():
    client = _FakeClient(response_text='{"text": "yes", "confidence": 0.55}')
    p = DeepSeekProvider(client=client)
    r = p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)
    assert r.confidence == pytest.approx(0.55)


def test_confidence_default_when_absent():
    client = _FakeClient(response_text='{"text": "yes"}')
    p = DeepSeekProvider(client=client)
    r = p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)
    # Default prior for DeepSeek is 0.8 (less than Anthropic's 0.85)
    assert r.confidence == pytest.approx(0.8)


# ── JSON parsing edge cases ────────────────────────────────────────────────


def test_parses_json_in_code_fences():
    client = _FakeClient(response_text='```json\n{"action": "hold"}\n```')
    p = DeepSeekProvider(client=client)
    r = p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)
    assert r.content == {"action": "hold"}


def test_raises_on_empty_text():
    client = _FakeClient(response_text="")
    p = DeepSeekProvider(client=client)
    with pytest.raises(DeepSeekJSONParseError, match="empty"):
        p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)


def test_raises_on_non_dict_json():
    client = _FakeClient(response_text="[1, 2, 3]")
    p = DeepSeekProvider(client=client)
    with pytest.raises(DeepSeekJSONParseError, match="not dict"):
        p.complete(messages=[{"role": "user", "content": "x"}],
                   schema=None, tools=None, temperature=0.0, seed=None)


# ── Protocol identity ──────────────────────────────────────────────────────


def test_provider_satisfies_llmprovider_protocol():
    from mimic.framework.routing import LLMProvider
    p = DeepSeekProvider(client=_FakeClient())
    assert isinstance(p, LLMProvider)


def test_provider_attributes_exposed():
    p = DeepSeekProvider(client=_FakeClient(),
                         model="deepseek-chat", model_version="v3.2")
    assert p.provider_name == "deepseek"
    assert p.model_name == "deepseek-chat"
    assert p.model_version == "v3.2"


def test_constructor_requires_api_key_when_no_client():
    """Without a client AND without DEEPSEEK_API_KEY → raises."""
    import os
    saved = os.environ.pop("DEEPSEEK_API_KEY", None)
    try:
        with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
            DeepSeekProvider()
    finally:
        if saved:
            os.environ["DEEPSEEK_API_KEY"] = saved
