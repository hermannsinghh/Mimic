"""Frozen-run cache tests — Plan §7.3."""
from __future__ import annotations

import pytest

from mimic.framework.determinism import (
    FrozenRunProvider,
    LocalFSBackend,
    compute_cache_key,
)
from mimic.framework.routing import (
    FrozenRunCacheMiss,
    StructuredResponse,
    compute_model_fingerprint,
)


class _StubProvider:
    def __init__(self):
        self.provider_name = "stub"
        self.model_name = "stub-v1"
        self.model_version = "2026-01"
        self.call_count = 0

    def estimate_cost_usd(self, i, o):
        return 0.01

    def complete(self, *, messages, schema, tools, temperature, seed, system_prompt=""):
        self.call_count += 1
        return StructuredResponse(
            content={"x": 1}, input_tokens=10, output_tokens=5,
            cost_usd=0.01, confidence=0.9,
            model_fingerprint=compute_model_fingerprint(
                provider=self.provider_name, model=self.model_name,
                version=self.model_version, system_prompt=system_prompt,
                temperature=temperature, tool_schema=None,
            ),
        )


def test_cache_key_changes_with_fingerprint_or_messages():
    a = compute_cache_key("fp1", [{"role": "user", "content": "hi"}])
    b = compute_cache_key("fp2", [{"role": "user", "content": "hi"}])
    c = compute_cache_key("fp1", [{"role": "user", "content": "bye"}])
    assert a != b != c
    assert len(a) == 64


def test_warm_run_caches_and_replays(tmp_path):
    inner = _StubProvider()
    cached = FrozenRunProvider(inner, LocalFSBackend(tmp_path), force_frozen=False)
    messages = [{"role": "user", "content": "hi"}]
    r1 = cached.complete(
        messages=messages, schema=None, tools=None,
        temperature=0.0, seed=None, system_prompt="sys",
    )
    r2 = cached.complete(
        messages=messages, schema=None, tools=None,
        temperature=0.0, seed=None, system_prompt="sys",
    )
    assert inner.call_count == 1, "second call should hit cache, not provider"
    assert r1 == r2


def test_frozen_run_cache_miss_raises(tmp_path):
    inner = _StubProvider()
    cached = FrozenRunProvider(inner, LocalFSBackend(tmp_path), force_frozen=True)
    with pytest.raises(FrozenRunCacheMiss):
        cached.complete(
            messages=[{"role": "user", "content": "cold"}], schema=None, tools=None,
            temperature=0.0, seed=None, system_prompt="sys",
        )
    assert inner.call_count == 0, "frozen-run must NEVER silently call the provider"


def test_frozen_run_replays_from_warm_cache(tmp_path):
    inner = _StubProvider()
    warm = FrozenRunProvider(inner, LocalFSBackend(tmp_path), force_frozen=False)
    msgs = [{"role": "user", "content": "warm me"}]
    warm.complete(messages=msgs, schema=None, tools=None,
                  temperature=0.0, seed=None, system_prompt="sys")
    assert inner.call_count == 1
    # Now flip to frozen — should replay, not raise
    frozen = FrozenRunProvider(inner, LocalFSBackend(tmp_path), force_frozen=True)
    frozen.complete(messages=msgs, schema=None, tools=None,
                    temperature=0.0, seed=None, system_prompt="sys")
    assert inner.call_count == 1, "frozen mode must not re-call after a hit"
