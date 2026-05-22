"""Tests for the `mimic scenario` CLI subgroup."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from mimic.cli import cli

_SVB = Path(__file__).resolve().parents[3] / "scenarios" / "svb-replay-2023"


@pytest.fixture
def runner():
    return CliRunner()


def test_scenario_inspect(runner):
    result = runner.invoke(cli, ["scenario", "inspect", str(_SVB)])
    assert result.exit_code == 0, result.output
    assert "svb-replay-2023" in result.output
    assert "0x57ab1107" in result.output


def test_scenario_pack_and_verify_round_trip(runner, tmp_path):
    tarball = tmp_path / "svb.tar"
    result = runner.invoke(cli, ["scenario", "pack", str(_SVB), "-o", str(tarball)])
    assert result.exit_code == 0, result.output
    assert tarball.exists()
    assert "digest:" in result.output

    # rich may wrap "sha256:<hex>" to a new line — match anywhere in output
    import re
    match = re.search(r"sha256:([0-9a-f]{64})", result.output)
    assert match, f"no sha256 digest found in:\n{result.output}"
    digest = match.group(1)

    dest = tmp_path / "unpacked"
    result = runner.invoke(cli, [
        "scenario", "verify", str(tarball),
        "-d", digest, "-u", str(dest),
    ])
    assert result.exit_code == 0, result.output
    assert "verified" in result.output
    assert (dest / "scenario.yaml").exists()


def test_scenario_verify_rejects_wrong_digest(runner, tmp_path):
    tarball = tmp_path / "svb.tar"
    runner.invoke(cli, ["scenario", "pack", str(_SVB), "-o", str(tarball)])
    result = runner.invoke(cli, [
        "scenario", "verify", str(tarball),
        "-d", "0" * 64, "-u", str(tmp_path / "u"),
    ])
    assert result.exit_code == 2


def test_scenario_sign_writes_signature_file(runner, tmp_path):
    tarball = tmp_path / "svb.tar"
    runner.invoke(cli, ["scenario", "pack", str(_SVB), "-o", str(tarball)])

    result = runner.invoke(cli, [
        "scenario", "sign", str(tarball),
        "--signer-did", "did:web:test.example",
    ])
    assert result.exit_code == 0, result.output
    sig_path = tarball.with_suffix(tarball.suffix + ".sig")
    assert sig_path.exists()
    sig = json.loads(sig_path.read_text())
    assert sig["signer_did"] == "did:web:test.example"
    assert sig["backend"] == "local-dev"
    assert len(sig["signature_hex"]) == 128
