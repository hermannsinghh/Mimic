"""Frozen-run cache for LLM responses — Plan §7.3 (F-08).

When MIMIC_FROZEN_RUN=1, every LLM call is keyed by
    cache_key = sha256(model_fingerprint + canonical_json(messages))
and looked up in a content-addressable store. Cache miss raises
FrozenRunCacheMiss — the run is never allowed to silently re-call the API.

This is the only audit-grade reproducibility path for closed-provider LLMs.

Backends:
- LocalFSBackend: dev/test, file under cache_dir/<key>.json
- S3Backend: prod (stub; wire to s3fs/boto3 later)

Wrap any LLMProvider with FrozenRunProvider to opt in:

    cached = FrozenRunProvider(real_provider, LocalFSBackend('/tmp/cache'))
    cached.complete(messages=..., ...)
"""
from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ..routing.provider import FrozenRunCacheMiss, LLMProvider, StructuredResponse
from .hashing import canonical_json


def is_frozen_run() -> bool:
    return os.environ.get("MIMIC_FROZEN_RUN", "0") == "1"


def compute_cache_key(model_fingerprint: str, messages: list[dict]) -> str:
    """sha256(model_fingerprint || canonical_json(messages))."""
    h = hashlib.sha256()
    h.update(model_fingerprint.encode("utf-8"))
    h.update(canonical_json(messages))
    return h.hexdigest()


class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> dict | None: ...
    @abstractmethod
    def put(self, key: str, value: dict) -> None: ...


class LocalFSBackend(CacheBackend):
    def __init__(self, cache_dir: str | Path) -> None:
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> dict | None:
        p = self._path(key)
        if not p.exists():
            return None
        return json.loads(p.read_text())

    def put(self, key: str, value: dict) -> None:
        self._path(key).write_text(json.dumps(value, sort_keys=True))


@dataclass(frozen=True)
class SSEConfig:
    """Server-side encryption configuration for S3Backend.

    Defaults: AES256 (S3-managed keys). For enterprise / lighthouse deployments
    that require customer-managed keys, use ``algorithm="aws:kms"`` and pass
    ``kms_key_id`` — that's a CISO ask we want satisfiable without changing
    the constructor surface later.
    """
    algorithm: Literal["AES256", "aws:kms"] = "AES256"
    kms_key_id: str | None = None
    bucket_key_enabled: bool = False

    def to_put_kwargs(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ServerSideEncryption": self.algorithm}
        if self.algorithm == "aws:kms":
            if not self.kms_key_id:
                raise ValueError("kms_key_id is required when algorithm='aws:kms'")
            out["SSEKMSKeyId"] = self.kms_key_id
            out["BucketKeyEnabled"] = self.bucket_key_enabled
        return out


_DEFAULT_SSE = SSEConfig(algorithm="AES256")


class S3Backend(CacheBackend):
    """Production frozen-run backend — Plan §7.3 / F-08.

    Stores LLM responses as JSON objects under ``<prefix>/<key>.json`` in an
    S3 bucket. ``boto3`` is an optional dependency: when boto3 is missing AND
    no explicit client is injected, the constructor raises a clear ImportError
    pointing at the install path.

    Reads return None on NoSuchKey (cache miss); other errors propagate.
    Writes use ``ContentType=application/json`` and the SSE config from
    ``sse_config`` (default = SSE-AES256). For enterprise CMK setups, pass
    ``sse_config=SSEConfig(algorithm="aws:kms", kms_key_id=...)``. Bucket
    policy + Object Lock are the deployer's responsibility.
    """

    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "mimic-frozen/",
        client: Any = None,
        sse_config: SSEConfig | None = None,
        # Back-compat: the v0 string-only kwarg. Prefer sse_config.
        server_side_encryption: str | None = None,
    ) -> None:
        if client is None:
            try:
                import boto3  # type: ignore[import-not-found]
            except ImportError as e:
                raise ImportError(
                    "S3Backend requires boto3 unless you inject a client. "
                    "Install with: pip install boto3"
                ) from e
            client = boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix if prefix.endswith("/") else prefix + "/"
        self._s3 = client
        # resolve SSE: explicit sse_config wins; else back-compat string; else default
        if sse_config is not None:
            self._sse = sse_config
        elif server_side_encryption == "AES256":
            self._sse = SSEConfig(algorithm="AES256")
        elif server_side_encryption is None:
            self._sse = _DEFAULT_SSE
        else:
            # caller passed an unknown SSE string — surface clearly
            raise ValueError(
                f"server_side_encryption={server_side_encryption!r} not supported. "
                f"Use sse_config=SSEConfig(...) for non-default SSE."
            )

    @property
    def sse_config(self) -> SSEConfig:
        return self._sse

    def _key(self, cache_key: str) -> str:
        return f"{self.prefix}{cache_key}.json"

    def get(self, key: str) -> dict | None:
        try:
            r = self._s3.get_object(Bucket=self.bucket, Key=self._key(key))
        except Exception as e:
            err_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if err_code in ("NoSuchKey", "NotFound", "404"):
                return None
            raise
        body = r["Body"].read()
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        return json.loads(body)

    def put(self, key: str, value: dict) -> None:
        body = json.dumps(value, sort_keys=True).encode("utf-8")
        kwargs: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": self._key(key),
            "Body": body,
            "ContentType": "application/json",
        }
        kwargs.update(self._sse.to_put_kwargs())
        self._s3.put_object(**kwargs)


class FrozenRunProvider:
    """Decorator over an LLMProvider that enforces frozen-run semantics."""

    def __init__(
        self,
        inner: LLMProvider,
        backend: CacheBackend,
        *,
        force_frozen: bool | None = None,
    ) -> None:
        self.inner = inner
        self.backend = backend
        self._force_frozen = force_frozen
        # delegated attributes
        self.provider_name = inner.provider_name
        self.model_name = inner.model_name
        self.model_version = inner.model_version

    def _frozen(self) -> bool:
        return self._force_frozen if self._force_frozen is not None else is_frozen_run()

    def estimate_cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return self.inner.estimate_cost_usd(input_tokens, output_tokens)

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
        # Probe the underlying provider just enough to compute the fingerprint —
        # we need it to key the cache. Real adapters know their fingerprint
        # without making a remote call.
        from ..routing.provider import compute_model_fingerprint

        fingerprint = compute_model_fingerprint(
            provider=self.inner.provider_name,
            model=self.inner.model_name,
            version=self.inner.model_version,
            system_prompt=system_prompt,
            temperature=temperature,
            tool_schema=tools[0] if tools else None,
        )
        key = compute_cache_key(fingerprint, messages)
        cached = self.backend.get(key)
        if cached is not None:
            # Strip debugging sidecar before validation (see RecordingProvider).
            cached.pop(_RECORDING_METADATA_KEY, None)
            return StructuredResponse.model_validate(cached)
        if self._frozen():
            raise FrozenRunCacheMiss(
                f"frozen-run cache miss for key={key[:16]}... "
                f"(provider={self.inner.provider_name}, model={self.inner.model_name})"
            )
        # warm-run path: call through and record
        resp = self.inner.complete(
            messages=messages, schema=schema, tools=tools,
            temperature=temperature, seed=seed, system_prompt=system_prompt,
        )
        record = resp.model_dump()
        record[_RECORDING_METADATA_KEY] = _build_recording_metadata(
            self.inner, system_prompt=system_prompt, temperature=temperature,
            tool_schema=tools[0] if tools else None,
        )
        self.backend.put(key, record)
        return resp


class RecordingProvider:
    """LLMProvider wrapper that records every response to a CacheBackend.

    Use this in a recording session (e.g. ``mimic scenario record-fixtures``)
    to populate a fixture directory with real LLM responses. The committed
    fixtures then back the CI's frozen-run mode — CI never hits a live API,
    and the recordings are re-generated only on explicit human action.

    Unlike FrozenRunProvider, RecordingProvider does NOT replay from cache —
    it always calls through. The point is to capture a fresh, intentional
    set of responses.

        # one-time recording session
        recorder = RecordingProvider(real_opus_45, LocalFSBackend('tests/fixtures/frozen-run/svb'))
        run_scenario_e2e(scenario_dir, ..., persona_builder=ConcordiaPersonaBuilder(provider=recorder, ...))
        # the fixture dir now contains every cache entry the run produced.
        # commit it; CI uses FrozenRunProvider against the same dir.

    Pairs with the convention in tests/fixtures/frozen-run/<scenario>/.
    """

    def __init__(self, inner: LLMProvider, backend: CacheBackend) -> None:
        self.inner = inner
        self.backend = backend
        self.provider_name = inner.provider_name
        self.model_name = inner.model_name
        self.model_version = inner.model_version
        self.recorded_count = 0

    def estimate_cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return self.inner.estimate_cost_usd(input_tokens, output_tokens)

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
        from ..routing.provider import compute_model_fingerprint

        resp = self.inner.complete(
            messages=messages, schema=schema, tools=tools,
            temperature=temperature, seed=seed, system_prompt=system_prompt,
        )
        fingerprint = compute_model_fingerprint(
            provider=self.inner.provider_name,
            model=self.inner.model_name,
            version=self.inner.model_version,
            system_prompt=system_prompt,
            temperature=temperature,
            tool_schema=tools[0] if tools else None,
        )
        key = compute_cache_key(fingerprint, messages)
        record = resp.model_dump()
        record[_RECORDING_METADATA_KEY] = _build_recording_metadata(
            self.inner, system_prompt=system_prompt, temperature=temperature,
            tool_schema=tools[0] if tools else None,
        )
        self.backend.put(key, record)
        self.recorded_count += 1
        return resp


# ── debugging sidecar metadata ──────────────────────────────────────────────

_RECORDING_METADATA_KEY = "_recording_metadata"


def _build_recording_metadata(
    inner: LLMProvider,
    *,
    system_prompt: str,
    temperature: float,
    tool_schema: dict | None,
) -> dict:
    """Sidecar fields embedded in cassette JSON. NOT part of the cache key —
    purely for human-readable debugging when someone opens `a7f3...json` in
    six months and wants to know what model recorded it. Stripped by
    FrozenRunProvider before StructuredResponse validation.
    """
    from datetime import datetime, timezone

    return {
        "provider": inner.provider_name,
        "model": inner.model_name,
        "version": inner.model_version,
        "temperature": float(temperature),
        "system_prompt_sha256": hashlib.sha256(
            system_prompt.encode("utf-8")
        ).hexdigest()[:16],
        "tool_schema_present": tool_schema is not None,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "schema": "mimic.framework.determinism.recording/v1",
    }
