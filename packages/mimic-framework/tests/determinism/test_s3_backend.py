"""Tests for the S3 frozen-run backend — Plan §7.3 F-08 close.

No real S3 access — we inject a stub client that implements the subset of the
boto3 S3 surface we use (get_object, put_object).
"""
from __future__ import annotations

import io
import json

import pytest

from mimic.framework.determinism import (
    FrozenRunProvider,
    S3Backend,
)
from mimic.framework.routing import (
    FrozenRunCacheMiss,
    StructuredResponse,
    compute_model_fingerprint,
)


class _StubS3:
    """Minimal in-memory S3 stub. Captures put_object kwargs for assertions."""

    class _NoSuchKey(Exception):
        def __init__(self):
            super().__init__("NoSuchKey")
            self.response = {"Error": {"Code": "NoSuchKey"}}

    def __init__(self):
        self.store: dict[tuple[str, str], dict] = {}
        self.put_kwargs: list[dict] = []

    def get_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.store:
            raise self._NoSuchKey()
        body = self.store[(Bucket, Key)]["Body"]
        return {"Body": io.BytesIO(body)}

    def put_object(self, **kwargs):
        self.put_kwargs.append(kwargs)
        self.store[(kwargs["Bucket"], kwargs["Key"])] = {"Body": kwargs["Body"]}


def test_put_and_get_round_trip():
    s3 = _StubS3()
    backend = S3Backend("mimic-cache", client=s3)
    backend.put("abc123", {"hello": "world", "n": 1})
    out = backend.get("abc123")
    assert out == {"hello": "world", "n": 1}


def test_get_returns_none_on_no_such_key():
    s3 = _StubS3()
    backend = S3Backend("mimic-cache", client=s3)
    assert backend.get("missing") is None


def test_put_uses_canonical_prefix_and_sse():
    s3 = _StubS3()
    backend = S3Backend("mimic-cache", prefix="frozen", client=s3)  # no trailing /
    backend.put("k", {"v": 1})
    kwargs = s3.put_kwargs[0]
    assert kwargs["Bucket"] == "mimic-cache"
    assert kwargs["Key"] == "frozen/k.json"
    assert kwargs["ContentType"] == "application/json"
    assert kwargs["ServerSideEncryption"] == "AES256"


def test_constructor_raises_when_boto3_missing(monkeypatch):
    # Simulate boto3 not installed by injecting a SystemModule that raises on import.
    import sys
    monkeypatch.setitem(sys.modules, "boto3", None)
    with pytest.raises(ImportError, match="boto3"):
        S3Backend("any-bucket")


def test_frozen_run_provider_with_s3_backend():
    class _Inner:
        provider_name = "stub"
        model_name = "stub-v1"
        model_version = "2026-01"
        call_count = 0

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

    s3 = _StubS3()
    backend = S3Backend("mimic-cache", client=s3)
    inner = _Inner()

    # warm-run: writes to S3
    warm = FrozenRunProvider(inner, backend, force_frozen=False)
    msgs = [{"role": "user", "content": "warm"}]
    warm.complete(messages=msgs, schema=None, tools=None,
                  temperature=0.0, seed=None, system_prompt="sys")
    assert inner.call_count == 1
    assert len(s3.store) == 1

    # frozen-run: replays from S3
    frozen = FrozenRunProvider(inner, backend, force_frozen=True)
    frozen.complete(messages=msgs, schema=None, tools=None,
                    temperature=0.0, seed=None, system_prompt="sys")
    assert inner.call_count == 1  # no second call


def test_frozen_run_miss_raises_with_s3_backend():
    s3 = _StubS3()  # empty bucket
    backend = S3Backend("mimic-cache", client=s3)
    class _Inner:
        provider_name = "stub"
        model_name = "stub-v1"
        model_version = "2026-01"
        def estimate_cost_usd(self, i, o): return 0.01
        def complete(self, **kw): raise AssertionError("must not call")
    provider = FrozenRunProvider(_Inner(), backend, force_frozen=True)
    with pytest.raises(FrozenRunCacheMiss):
        provider.complete(messages=[{"role": "user", "content": "cold"}],
                          schema=None, tools=None,
                          temperature=0.0, seed=None, system_prompt="sys")
