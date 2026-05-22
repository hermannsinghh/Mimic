"""Scenario artifact pack/unpack — Plan §3.1 F-02.

A scenario artifact is a tarball + manifest where every file is content-addressed
by sha256. The manifest itself is canonical-JSON serialised so two identical
scenarios always pack to the same bytes.

    pack(scenario_dir, out_path) -> ArtifactManifest
    unpack(artifact_path, dest_dir, expected_digest=None) -> ArtifactManifest

Backends:
    LocalFSStore   — dev/test; files live in cache_dir/<digest>.tar
    OCIStore       — prod via oras-py (interface only; raises if oras missing)

The artifact digest is the sha256 of the canonical-JSON manifest. That digest
is what gets signed (F-03) and what Mimic Hub stores in its database (H-01).
"""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..determinism.hashing import canonical_json


@dataclass(frozen=True)
class FileEntry:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class ArtifactManifest:
    name: str
    version: str
    files: tuple[FileEntry, ...]
    artifact_sha256: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "files": [{"path": f.path, "sha256": f.sha256, "size": f.size} for f in self.files],
            "metadata": self.metadata,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_dict())


class ArtifactVerificationError(RuntimeError):
    """Raised when unpacked content doesn't match the manifest."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _iter_files(scenario_dir: Path) -> list[Path]:
    """Stable iteration: sorted by relative path, excluding cache + dotfiles."""
    excluded = {".pytest_cache", "__pycache__", ".git", "dist", "build", "node_modules"}
    out: list[Path] = []
    for p in sorted(scenario_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(scenario_dir)
        if any(part.startswith(".") or part in excluded for part in rel.parts):
            continue
        out.append(p)
    return out


def pack(scenario_dir: str | Path, out_path: str | Path) -> ArtifactManifest:
    """Pack `scenario_dir` into a content-addressed tarball at `out_path`."""
    scenario_dir = Path(scenario_dir).resolve()
    out_path = Path(out_path)
    if not scenario_dir.is_dir():
        raise FileNotFoundError(f"not a directory: {scenario_dir}")

    spec_path = scenario_dir / "scenario.yaml"
    if not spec_path.exists():
        raise FileNotFoundError(f"missing scenario.yaml in {scenario_dir}")

    # parse just enough to fill manifest name/version
    import yaml
    spec = yaml.safe_load(spec_path.read_text())
    meta = spec.get("metadata") or {}
    name = meta.get("name") or scenario_dir.name
    version = meta.get("version") or "0.0.0"

    files: list[FileEntry] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out_path, "w") as tar:
        for f in _iter_files(scenario_dir):
            data = f.read_bytes()
            rel = str(f.relative_to(scenario_dir))
            files.append(FileEntry(path=rel, sha256=_sha256_bytes(data), size=len(data)))
            info = tarfile.TarInfo(name=rel)
            info.size = len(data)
            info.mtime = 0  # reproducible — no timestamps
            tar.addfile(info, io.BytesIO(data))

    # artifact digest = sha256(canonical_json(manifest_without_artifact_digest))
    manifest_body = {
        "name": name,
        "version": version,
        "files": [{"path": f.path, "sha256": f.sha256, "size": f.size} for f in files],
        "metadata": {"file_count": len(files)},
    }
    artifact_digest = _sha256_bytes(canonical_json(manifest_body))
    return ArtifactManifest(
        name=name,
        version=version,
        files=tuple(files),
        artifact_sha256=artifact_digest,
        metadata=manifest_body["metadata"],
    )


def unpack(
    artifact_path: str | Path,
    dest_dir: str | Path,
    *,
    expected_digest: str | None = None,
) -> ArtifactManifest:
    """Unpack a scenario tarball into `dest_dir`, verifying every file digest.

    If `expected_digest` is given, the resulting artifact_sha256 must match —
    otherwise raises ArtifactVerificationError.
    """
    artifact_path = Path(artifact_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    files: list[FileEntry] = []
    with tarfile.open(artifact_path, "r") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            data = tar.extractfile(member).read()
            digest = _sha256_bytes(data)
            files.append(FileEntry(path=member.name, sha256=digest, size=len(data)))
            target = dest_dir / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    files.sort(key=lambda f: f.path)
    import yaml
    spec_text = (dest_dir / "scenario.yaml").read_text()
    spec = yaml.safe_load(spec_text)
    meta = spec.get("metadata") or {}
    name = meta.get("name", "")
    version = meta.get("version", "")
    manifest_body = {
        "name": name,
        "version": version,
        "files": [{"path": f.path, "sha256": f.sha256, "size": f.size} for f in files],
        "metadata": {"file_count": len(files)},
    }
    artifact_digest = _sha256_bytes(canonical_json(manifest_body))

    if expected_digest is not None and artifact_digest != expected_digest:
        raise ArtifactVerificationError(
            f"artifact digest mismatch: expected {expected_digest}, got {artifact_digest}"
        )

    return ArtifactManifest(
        name=name,
        version=version,
        files=tuple(files),
        artifact_sha256=artifact_digest,
        metadata=manifest_body["metadata"],
    )


# ── backends ────────────────────────────────────────────────────────────────

class LocalFSStore:
    """Dev/test backend — artifacts live under cache_dir/<digest>.tar."""

    def __init__(self, cache_dir: str | Path) -> None:
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def push(self, scenario_dir: str | Path) -> ArtifactManifest:
        # pack to a temp path keyed by digest after we know it
        scenario_dir = Path(scenario_dir)
        tmp = self.dir / "_pack.tmp"
        manifest = pack(scenario_dir, tmp)
        final = self.dir / f"{manifest.artifact_sha256}.tar"
        tmp.rename(final)
        (self.dir / f"{manifest.artifact_sha256}.json").write_text(
            json.dumps(manifest.to_dict(), sort_keys=True, indent=2)
        )
        return manifest

    def pull(self, digest: str, dest_dir: str | Path) -> ArtifactManifest:
        artifact = self.dir / f"{digest}.tar"
        if not artifact.exists():
            raise FileNotFoundError(f"no artifact for digest {digest!r} in {self.dir}")
        return unpack(artifact, dest_dir, expected_digest=digest)


class OCIStore:
    """Production backend via oras-py — stub until F-02 wires up the registry."""

    def __init__(self, registry_url: str) -> None:
        self.registry_url = registry_url
        try:
            import oras  # noqa: F401  (type: ignore[import-not-found])
        except ImportError as e:
            raise RuntimeError(
                "oras-py is not installed. Install with `pip install oras` or use LocalFSStore."
            ) from e

    def push(self, scenario_dir: str | Path) -> ArtifactManifest:
        raise NotImplementedError("OCIStore.push wiring lands with F-02 against a real registry")

    def pull(self, digest: str, dest_dir: str | Path) -> ArtifactManifest:
        raise NotImplementedError("OCIStore.pull wiring lands with F-02 against a real registry")
