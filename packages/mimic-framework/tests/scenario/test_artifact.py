"""Tests for scenario artifact pack/unpack — Plan §3.1 F-02."""
from __future__ import annotations

from pathlib import Path

import pytest

from mimic.framework.scenario import (
    ArtifactVerificationError,
    LocalFSStore,
    pack,
    unpack,
)

_SVB = Path(__file__).resolve().parents[4] / "scenarios" / "svb-replay-2023"


def test_pack_svb_scenario(tmp_path):
    out = tmp_path / "svb.tar"
    manifest = pack(_SVB, out)
    assert out.exists()
    assert manifest.name == "svb-replay-2023"
    assert manifest.version == "0.1.0"
    assert len(manifest.files) >= 2  # scenario.yaml + README.md
    assert all(len(f.sha256) == 64 for f in manifest.files)
    assert len(manifest.artifact_sha256) == 64


def test_pack_is_deterministic(tmp_path):
    a = pack(_SVB, tmp_path / "a.tar")
    b = pack(_SVB, tmp_path / "b.tar")
    assert a.artifact_sha256 == b.artifact_sha256
    assert a.to_canonical_json() == b.to_canonical_json()


def test_unpack_round_trip(tmp_path):
    artifact_path = tmp_path / "svb.tar"
    pack_manifest = pack(_SVB, artifact_path)
    dest = tmp_path / "unpacked"
    unpack_manifest = unpack(artifact_path, dest, expected_digest=pack_manifest.artifact_sha256)
    assert unpack_manifest.artifact_sha256 == pack_manifest.artifact_sha256
    # every original file is present and byte-identical
    for f in pack_manifest.files:
        assert (dest / f.path).exists()
        assert (dest / f.path).stat().st_size == f.size


def test_unpack_rejects_wrong_expected_digest(tmp_path):
    artifact_path = tmp_path / "svb.tar"
    pack(_SVB, artifact_path)
    with pytest.raises(ArtifactVerificationError):
        unpack(artifact_path, tmp_path / "dest", expected_digest="0" * 64)


def test_local_fs_store_push_pull(tmp_path):
    store = LocalFSStore(tmp_path / "store")
    m1 = store.push(_SVB)
    m2 = store.pull(m1.artifact_sha256, tmp_path / "fetched")
    assert m1.artifact_sha256 == m2.artifact_sha256


def test_local_fs_store_pull_missing_digest(tmp_path):
    store = LocalFSStore(tmp_path / "store")
    with pytest.raises(FileNotFoundError):
        store.pull("0" * 64, tmp_path / "dest")


def test_pack_excludes_cache_and_dotfiles(tmp_path):
    # build a fake scenario with cache + dotfile noise
    scen = tmp_path / "mini"
    scen.mkdir()
    (scen / "scenario.yaml").write_text(
        "apiVersion: mimic.scenario/v1\nkind: Scenario\n"
        "metadata:\n  name: mini\n  version: 0.0.1\n  license: MIT\n"
        "  author_did: did:web:test\n  mimic_version: '>=0.2.0,<0.4.0'\n"
        "spec:\n  event:\n    iri: https://x.test/e\n    duration_days: 1\n"
        "  scope:\n    tiers: [T3]\n  mc:\n    paths: 1\n    horizon_days: 1\n    seed_global: 1\n"
    )
    (scen / "README.md").write_text("# mini")
    (scen / ".pytest_cache").mkdir()
    (scen / ".pytest_cache" / "junk").write_text("noise")
    (scen / "__pycache__").mkdir()
    (scen / "__pycache__" / "x.pyc").write_text("bytecode")
    (scen / ".env").write_text("SECRET=nope")

    m = pack(scen, tmp_path / "mini.tar")
    paths = {f.path for f in m.files}
    assert "scenario.yaml" in paths
    assert "README.md" in paths
    for noise in paths:
        assert ".pytest_cache" not in noise
        assert "__pycache__" not in noise
        assert not noise.startswith(".")
