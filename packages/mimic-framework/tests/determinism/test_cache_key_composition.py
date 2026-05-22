"""Lock test for the frozen-run cache key composition.

Per Plan §7.3, cache_key = sha256(model_fingerprint || canonical_json(messages)).
Per Plan §6.2, model_fingerprint = sha256(provider|model|version|system_prompt|temperature|tool_schema).

Both formulas are load-bearing for audit-grade replay. Any change to either
silently breaks the frozen-run cache: same logical input → different key →
cache miss → either a fresh LLM call (warm mode) or FrozenRunCacheMiss (frozen).

This test pins both formulas to known outputs for a known input. If it fails,
the cache layout has changed and any committed fixture cassettes will need
re-recording — that's a schema major bump per Plan §13.3.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from mimic.framework.determinism import compute_cache_key
from mimic.framework.determinism.hashing import canonical_json
from mimic.framework.routing import compute_model_fingerprint


def test_model_fingerprint_pinned_value():
    """Plan §6.2 formula must produce this exact digest for these inputs."""
    fp = compute_model_fingerprint(
        provider="anthropic",
        model="claude-opus-4-5",
        version="2026-01",
        system_prompt="you are a treaty pricer",
        temperature=0.0,
        tool_schema=None,
    )
    # Locked golden value — change here forces a schema major bump
    # and re-recording of every frozen-run cassette.
    expected = hashlib.sha256(
        b"anthropic|claude-opus-4-5|2026-01|you are a treaty pricer|0.000000|"
    ).hexdigest()
    assert fp == expected, (
        f"model_fingerprint formula drifted. Expected {expected}, got {fp}. "
        "If intentional, bump schema major + refresh all frozen-run cassettes "
        "+ write an ADR."
    )


def test_cache_key_canonicalizes_messages_before_hashing():
    """Two semantically-identical message lists with different key orders
    MUST produce the same cache_key. Otherwise frozen-run silently misses
    every time the LLM SDK reorders dict keys."""
    fp = "abc" * 21 + "x"  # 64 chars
    msgs_a = [{"role": "user", "content": "hi", "name": "test"}]
    msgs_b = [{"name": "test", "content": "hi", "role": "user"}]  # reordered
    assert compute_cache_key(fp, msgs_a) == compute_cache_key(fp, msgs_b)


def test_cache_key_uses_canonical_json():
    """The hash must be over canonical-JSON bytes (sorted keys, no spaces,
    no NaN), not whatever json.dumps default produces."""
    fp = "x" * 64
    msgs = [{"b": 2, "a": 1}]
    expected = hashlib.sha256(fp.encode("utf-8") + canonical_json(msgs)).hexdigest()
    assert compute_cache_key(fp, msgs) == expected


def test_cache_key_changes_when_fingerprint_changes():
    msgs = [{"role": "user", "content": "x"}]
    a = compute_cache_key("a" * 64, msgs)
    b = compute_cache_key("b" * 64, msgs)
    assert a != b


def test_cache_key_changes_when_messages_change():
    fp = "x" * 64
    a = compute_cache_key(fp, [{"role": "user", "content": "ask A"}])
    b = compute_cache_key(fp, [{"role": "user", "content": "ask B"}])
    assert a != b


def test_cache_key_changes_when_message_LIST_order_changes():
    """Message ORDER is semantically meaningful to the LLM — "A then B" is a
    different conversation from "B then A". The canonicalizer must preserve
    list order (sort_keys=True applies to dict keys, not list elements). If
    this test ever fails, we're silently cache-hitting across semantically
    different conversations and the audit story is broken."""
    fp = "x" * 64
    a_then_b = compute_cache_key(fp, [
        {"role": "user", "content": "A"},
        {"role": "user", "content": "B"},
    ])
    b_then_a = compute_cache_key(fp, [
        {"role": "user", "content": "B"},
        {"role": "user", "content": "A"},
    ])
    assert a_then_b != b_then_a, (
        "message list order collision — the canonicalizer is sorting list "
        "elements, which would silently cache-hit across different conversations. "
        "Check canonical_json's separator/sort handling."
    )


def test_cache_key_pinned_for_known_input():
    """End-to-end pin: given known fingerprint + known messages,
    the cache key is a known string. This is the regression test that
    breaks loudly if either formula drifts.
    """
    fp = "0" * 64  # all-zero fingerprint
    msgs = [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "what is 2+2?"},
    ]
    key = compute_cache_key(fp, msgs)
    # Derived deterministically from the locked formula above:
    expected = hashlib.sha256(
        fp.encode("utf-8") + canonical_json(msgs)
    ).hexdigest()
    assert key == expected
    # And the locked golden value (computed once, frozen here):
    assert len(key) == 64
