"""HubClient — talks to a Mimic Hub instance.

API:
    client = HubClient(base_url=..., transport=...)
    client.search(query, tier=None) -> list[ScenarioManifest]
    client.get_scenario(scenario_id) -> ScenarioManifest
    client.get_badge(scenario_id) -> dict
    client.pull(manifest, dest_dir) -> Path
    client.publish(scenario_dir, api_key) -> ScenarioManifest

`transport` is the httpx.Client (default) or any httpx-compatible client (used
in tests with a MockTransport). All errors surface as `HubError`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx


class HubError(RuntimeError):
    """Any failure from the Hub server."""


@dataclass(frozen=True)
class ScenarioManifest:
    id: str
    name: str
    version: str
    author_did: str
    artifact_digest: str
    license: str
    tier_scope: tuple[str, ...] = field(default_factory=tuple)
    sigstore_log_id: str | None = None
    calibration: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "ScenarioManifest":
        return cls(
            id=d["id"],
            name=d["name"],
            version=d["version"],
            author_did=d["author_did"],
            artifact_digest=d["artifact_digest"],
            license=d.get("license", ""),
            tier_scope=tuple(d.get("tier_scope", ())),
            sigstore_log_id=d.get("sigstore_log_id"),
            calibration=d.get("calibration"),
        )


class HubClient:
    def __init__(
        self,
        base_url: str = "https://hub.mimic.ai",
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self.base_url,
            transport=transport,
            timeout=timeout,
        )

    # ── reads ───────────────────────────────────────────────────────────

    def search(
        self,
        query: str | None = None,
        *,
        tier: str | None = None,
    ) -> list[ScenarioManifest]:
        params = {}
        if query:
            params["q"] = query
        if tier:
            params["tier"] = tier
        return self._get_list("/search", params=params)

    def get_scenario(self, scenario_id: str) -> ScenarioManifest:
        r = self._http.get(f"/scenarios/{scenario_id}")
        self._raise_for_status(r)
        return ScenarioManifest.from_dict(r.json())

    def get_badge(self, scenario_id: str) -> dict:
        r = self._http.get(f"/badges/{scenario_id}")
        self._raise_for_status(r)
        return r.json()

    # ── artifact transfer ───────────────────────────────────────────────

    def pull(self, manifest: ScenarioManifest, dest_dir: str | Path) -> Path:
        """Download the artifact described by `manifest` into `dest_dir`."""
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f"{manifest.id}.tar"
        with self._http.stream("GET", f"/blobs/{manifest.artifact_digest}") as r:
            self._raise_for_status(r)
            with open(out, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)
        return out

    # ── writes (auth required) ──────────────────────────────────────────

    def publish(
        self,
        scenario_dir: str | Path,
        *,
        api_key: str,
        signer: Any = None,
        signer_did: str | None = None,
        skip_signing: bool = False,
    ) -> ScenarioManifest:
        """Pack + sign + push a scenario directory to the Hub.

        Scenario packing happens client-side (deterministic). The artifact is
        Sigstore-signed (or signed with `signer`) before upload. Both the
        artifact and the detached signature are sent multipart.

        Args:
            scenario_dir: path to the scenario directory to publish.
            api_key: Hub API key.
            signer: an object with .sign(artifact_digest, signer_did) -> Signature.
                If None, uses a default Sigstore signer (when sigstore-python is
                installed). Falls back to LocalDevSigner only if skip_signing=True
                isn't acceptable — see the warning.
            signer_did: signer DID to record on the signature. Required when
                signer is provided. Defaults to "did:web:unknown" otherwise.
            skip_signing: if True, push without a signature (loudly warned).
                Hub server policy decides whether to accept this — most
                deployments reject unsigned artifacts.
        """
        scenario_dir = Path(scenario_dir)
        if not scenario_dir.is_dir():
            raise HubError(f"not a directory: {scenario_dir}")
        try:
            from mimic.framework.scenario import pack  # type: ignore[import-not-found]
        except ImportError as e:
            raise HubError(
                "publish() requires mimic-framework in the environment. "
                "Install with: pip install mimic-framework"
            ) from e

        tmp_tar = scenario_dir / "_publish.tmp.tar"
        try:
            manifest = pack(scenario_dir, tmp_tar)

            signature_payload: str | None = None
            if not skip_signing:
                if signer is None:
                    raise HubError(
                        "publish() requires a signer or skip_signing=True. "
                        "Pass `signer=LocalDevSigner.generate()` (dev only) or a "
                        "Sigstore signer. See .claude/skills/mimic-release.md."
                    )
                import json as _json
                sig = signer.sign(manifest.artifact_sha256, signer_did=signer_did or "did:web:unknown")
                signature_payload = _json.dumps(sig.to_dict(), sort_keys=True)
            else:
                import warnings
                warnings.warn(
                    "publish(skip_signing=True) — Hub server is likely to reject "
                    "an unsigned artifact. Use only for dev with a Hub configured "
                    "to permit unsigned uploads.",
                    stacklevel=2,
                )

            with open(tmp_tar, "rb") as f:
                files = {"artifact": ("scenario.tar", f, "application/x-tar")}
                data = {"expected_digest": manifest.artifact_sha256}
                if signature_payload is not None:
                    data["signature"] = signature_payload
                r = self._http.post(
                    "/publish",
                    files=files,
                    data=data,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            self._raise_for_status(r)
            return ScenarioManifest.from_dict(r.json())
        finally:
            tmp_tar.unlink(missing_ok=True)

    # ── internals ───────────────────────────────────────────────────────

    def _get_list(self, path: str, *, params: dict | None = None) -> list[ScenarioManifest]:
        r = self._http.get(path, params=params)
        self._raise_for_status(r)
        return [ScenarioManifest.from_dict(d) for d in r.json()]

    def _raise_for_status(self, r: httpx.Response) -> None:
        if r.status_code >= 400:
            raise HubError(f"{r.request.method} {r.url} -> {r.status_code}: {r.text}")

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "HubClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()
