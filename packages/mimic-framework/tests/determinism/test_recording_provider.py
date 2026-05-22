"""Tests for RecordingProvider — the cassette-recording side of frozen-run.

Together with FrozenRunProvider, this is the loop the user described in their
day-90 setup: record once with a real LLM provider, commit the fixtures, then
CI never hits a live API.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mimic.framework.determinism import (
    FrozenRunProvider,
    LocalFSBackend,
    RecordingProvider,
    compute_cache_key,
)
from mimic.framework.routing import (
    FrozenRunCacheMiss,
    StructuredResponse,
    compute_model_fingerprint,
)


class _LiveStub:
    """Stand-in for a live LLM provider — counts calls."""
    def __init__(self, response_content):
        self.provider_name = "anthropic"
        self.model_name = "claude-opus-4-5"
        self.model_version = "2026-01"
        self._content = response_content
        self.calls = 0

    def estimate_cost_usd(self, i, o):
        return 0.04

    def complete(self, *, messages, schema, tools, temperature, seed, system_prompt=""):
        self.calls += 1
        return StructuredResponse(
            content=self._content, input_tokens=120, output_tokens=80,
            cost_usd=0.04, confidence=0.92,
            model_fingerprint=compute_model_fingerprint(
                provider=self.provider_name, model=self.model_name,
                version=self.model_version, system_prompt=system_prompt,
                temperature=temperature, tool_schema=None,
            ),
        )


def test_recording_provider_always_calls_inner(tmp_path):
    inner = _LiveStub({"action": "reinsure", "premium_usd": 1e6})
    rec = RecordingProvider(inner, LocalFSBackend(tmp_path))
    msgs = [{"role": "user", "content": "price this treaty"}]

    # First call
    rec.complete(messages=msgs, schema=None, tools=None,
                 temperature=0.0, seed=None, system_prompt="sys")
    # Second call with identical args — still goes through (no replay)
    rec.complete(messages=msgs, schema=None, tools=None,
                 temperature=0.0, seed=None, system_prompt="sys")
    assert inner.calls == 2
    assert rec.recorded_count == 2


def test_recorded_fixtures_replay_via_frozen_run_provider(tmp_path):
    """The round-trip the user described: record once, then CI replays.

    Recording session uses RecordingProvider against a live (stubbed) API.
    CI mounts the same backend dir behind FrozenRunProvider with force_frozen=True;
    every cache hit replays without calling the inner provider.
    """
    # 1. Recording session
    inner = _LiveStub({"action": "reinsure", "premium_usd": 1e6, "confidence": 0.92})
    backend = LocalFSBackend(tmp_path)
    recorder = RecordingProvider(inner, backend)
    msgs = [{"role": "user", "content": "price this treaty"}]
    recorder.complete(messages=msgs, schema=None, tools=None,
                      temperature=0.0, seed=None, system_prompt="sys")
    assert inner.calls == 1
    fixture_files = list(tmp_path.glob("*.json"))
    assert len(fixture_files) == 1

    # 2. CI session — different process, frozen mode, same backend dir
    inner_ci = _LiveStub({"action": "DIFFERENT"})  # should never get called
    frozen = FrozenRunProvider(inner_ci, LocalFSBackend(tmp_path), force_frozen=True)
    resp = frozen.complete(messages=msgs, schema=None, tools=None,
                           temperature=0.0, seed=None, system_prompt="sys")
    assert inner_ci.calls == 0, "CI must not call the live API"
    assert resp.content == {"action": "reinsure", "premium_usd": 1e6, "confidence": 0.92}


def test_unrecorded_request_raises_in_frozen_mode(tmp_path):
    """Recording captures only what was actually requested. Anything else
    raises FrozenRunCacheMiss in CI — which is the loud failure we want."""
    inner = _LiveStub({"x": 1})
    recorder = RecordingProvider(inner, LocalFSBackend(tmp_path))
    recorder.complete(messages=[{"role": "user", "content": "A"}], schema=None,
                      tools=None, temperature=0.0, seed=None, system_prompt="sys")

    inner_ci = _LiveStub({"x": 2})
    frozen = FrozenRunProvider(inner_ci, LocalFSBackend(tmp_path), force_frozen=True)
    # Asking a different question — no cassette for it
    with pytest.raises(FrozenRunCacheMiss):
        frozen.complete(messages=[{"role": "user", "content": "B"}], schema=None,
                        tools=None, temperature=0.0, seed=None, system_prompt="sys")
    assert inner_ci.calls == 0


def test_recorded_cassette_carries_debugging_sidecar(tmp_path):
    """Opening a cassette file in six months must reveal the model context.
    The sidecar lives at key '_recording_metadata' inside the JSON value —
    NOT in the cache key (would defeat caching) but in the stored response."""
    import json
    inner = _LiveStub({"action": "reinsure", "premium_usd": 1e6})
    rec = RecordingProvider(inner, LocalFSBackend(tmp_path))
    rec.complete(messages=[{"role": "user", "content": "price"}],
                 schema=None, tools=None, temperature=0.7, seed=None,
                 system_prompt="you are a treaty pricer")

    cassette_path = next(tmp_path.glob("*.json"))
    stored = json.loads(cassette_path.read_text())
    assert "_recording_metadata" in stored
    md = stored["_recording_metadata"]
    assert md["provider"] == "anthropic"
    assert md["model"] == "claude-opus-4-5"
    assert md["version"] == "2026-01"
    assert md["temperature"] == 0.7
    assert len(md["system_prompt_sha256"]) == 16
    assert md["tool_schema_present"] is False
    assert "recorded_at" in md
    assert md["schema"] == "mimic.framework.determinism.recording/v1"


def test_sidecar_metadata_does_not_break_frozen_run_replay(tmp_path):
    """The metadata must be stripped before StructuredResponse validation —
    otherwise CI replays would fail with extra-field validation errors."""
    inner = _LiveStub({"action": "hold", "confidence": 0.9})
    rec = RecordingProvider(inner, LocalFSBackend(tmp_path))
    msgs = [{"role": "user", "content": "wait?"}]
    original = rec.complete(messages=msgs, schema=None, tools=None,
                            temperature=0.0, seed=None, system_prompt="sys")

    inner_ci = _LiveStub({"action": "MUST_NOT_BE_CALLED"})
    frozen = FrozenRunProvider(inner_ci, LocalFSBackend(tmp_path), force_frozen=True)
    replayed = frozen.complete(messages=msgs, schema=None, tools=None,
                               temperature=0.0, seed=None, system_prompt="sys")
    assert inner_ci.calls == 0
    assert replayed.content == original.content
    assert replayed.model_fingerprint == original.model_fingerprint


def test_sidecar_metadata_changes_with_system_prompt(tmp_path):
    """Two recordings with different system_prompts → different sidecars,
    so a debugger can spot system-prompt drift between cassettes."""
    import json
    inner = _LiveStub({"x": 1})
    rec = RecordingProvider(inner, LocalFSBackend(tmp_path))
    rec.complete(messages=[{"role": "user", "content": "q"}],
                 schema=None, tools=None, temperature=0.0, seed=None,
                 system_prompt="prompt A")
    rec.complete(messages=[{"role": "user", "content": "q"}],
                 schema=None, tools=None, temperature=0.0, seed=None,
                 system_prompt="prompt B")
    cassettes = sorted(tmp_path.glob("*.json"))
    assert len(cassettes) == 2  # different system_prompt → different fingerprint → different key
    md_a = json.loads(cassettes[0].read_text())["_recording_metadata"]
    md_b = json.loads(cassettes[1].read_text())["_recording_metadata"]
    assert md_a["system_prompt_sha256"] != md_b["system_prompt_sha256"]


def test_warm_run_via_frozen_run_provider_also_records_sidecar(tmp_path):
    """FrozenRunProvider in warm mode (cache miss + not frozen) records too.
    It should also embed the sidecar so warm-run cassettes are debuggable."""
    import json
    inner = _LiveStub({"action": "hedge"})
    warm = FrozenRunProvider(inner, LocalFSBackend(tmp_path), force_frozen=False)
    warm.complete(messages=[{"role": "user", "content": "x"}],
                  schema=None, tools=None, temperature=0.0, seed=None, system_prompt="sys")
    cassette = next(tmp_path.glob("*.json"))
    stored = json.loads(cassette.read_text())
    assert "_recording_metadata" in stored
    assert stored["_recording_metadata"]["provider"] == "anthropic"


def test_recording_uses_canonical_cache_key(tmp_path):
    """The filename under the backend dir is the cache_key. Two semantically
    identical message lists must collide to the same cassette."""
    inner = _LiveStub({"x": 1})
    rec = RecordingProvider(inner, LocalFSBackend(tmp_path))

    # Record with messages in one key order
    rec.complete(messages=[{"role": "user", "content": "q", "name": "test"}],
                 schema=None, tools=None, temperature=0.0, seed=None, system_prompt="sys")
    cassettes_after_first = sorted(tmp_path.glob("*.json"))

    # Record with messages reordered — should overwrite the same key, not add a new file
    rec.complete(messages=[{"name": "test", "content": "q", "role": "user"}],
                 schema=None, tools=None, temperature=0.0, seed=None, system_prompt="sys")
    cassettes_after_second = sorted(tmp_path.glob("*.json"))

    assert len(cassettes_after_first) == 1
    assert cassettes_after_second == cassettes_after_first, (
        "RecordingProvider must use canonical-JSON cache keys; otherwise "
        "two semantically-identical message lists would record to different "
        "cassettes and the frozen-run replay would silently miss in CI."
    )
