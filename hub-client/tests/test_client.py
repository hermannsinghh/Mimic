"""Tests for HubClient using httpx.MockTransport — no live network."""
from __future__ import annotations

import json

import httpx
import pytest

from hub_client import HubClient, HubError, ScenarioManifest


_MANIFEST = {
    "id": "svb-replay-2023:0.1.0",
    "name": "svb-replay-2023",
    "version": "0.1.0",
    "author_did": "did:web:mimic.ai",
    "artifact_digest": "a" * 64,
    "license": "MIT",
    "tier_scope": ["T1", "T2"],
    "sigstore_log_id": "rekor-1",
}


def _mock(handler):
    return httpx.MockTransport(handler)


def test_search_returns_manifests():
    def handler(request):
        assert request.url.path == "/search"
        assert request.url.params["q"] == "svb"
        return httpx.Response(200, json=[_MANIFEST])
    with HubClient(transport=_mock(handler)) as c:
        out = c.search("svb")
    assert len(out) == 1
    assert isinstance(out[0], ScenarioManifest)
    assert out[0].name == "svb-replay-2023"


def test_search_with_tier_param():
    def handler(request):
        assert request.url.params.get("tier") == "T1"
        return httpx.Response(200, json=[])
    with HubClient(transport=_mock(handler)) as c:
        out = c.search("anything", tier="T1")
    assert out == []


def test_get_scenario_returns_manifest():
    def handler(request):
        assert request.url.path == "/scenarios/svb-replay-2023:0.1.0"
        return httpx.Response(200, json=_MANIFEST)
    with HubClient(transport=_mock(handler)) as c:
        m = c.get_scenario("svb-replay-2023:0.1.0")
    assert m.tier_scope == ("T1", "T2")


def test_get_badge_returns_dict():
    badge = {"scenario_id": "svb-replay-2023:0.1.0", "directional_accuracy": 0.82}
    def handler(request):
        assert request.url.path == "/badges/svb-replay-2023:0.1.0"
        return httpx.Response(200, json=badge)
    with HubClient(transport=_mock(handler)) as c:
        out = c.get_badge("svb-replay-2023:0.1.0")
    assert out["directional_accuracy"] == 0.82


def test_pull_downloads_blob(tmp_path):
    body = b"fake tar bytes" * 10

    def handler(request):
        assert request.url.path == f"/blobs/{'a' * 64}"
        return httpx.Response(200, content=body)

    with HubClient(transport=_mock(handler)) as c:
        manifest = ScenarioManifest.from_dict(_MANIFEST)
        out = c.pull(manifest, dest_dir=tmp_path)
    assert out.read_bytes() == body


def test_4xx_surfaces_as_hub_error():
    def handler(request):
        return httpx.Response(404, text="not found")
    with HubClient(transport=_mock(handler)) as c:
        with pytest.raises(HubError, match="404"):
            c.get_scenario("missing")


def test_5xx_surfaces_as_hub_error():
    def handler(request):
        return httpx.Response(500, text="boom")
    with HubClient(transport=_mock(handler)) as c:
        with pytest.raises(HubError, match="500"):
            c.search("x")


def test_publish_requires_mimic_framework(tmp_path, monkeypatch):
    # Force `from mimic.framework.scenario import pack` to raise ImportError
    # regardless of how mimic-framework happens to be installed (PEP 660
    # editable finder, easy-install.pth, plain site-packages, …). Setting
    # the module entry to None in sys.modules makes `import` raise — that
    # is the documented way to mask an installed module for the duration of
    # a single test.
    import sys
    monkeypatch.setitem(sys.modules, "mimic.framework.scenario", None)
    with HubClient(transport=_mock(lambda r: httpx.Response(200, json=_MANIFEST))) as c:
        scen = tmp_path / "s"
        scen.mkdir()
        (scen / "x.txt").write_text("hi")
        with pytest.raises(HubError, match="mimic-framework"):
            c.publish(scen, api_key="x", skip_signing=True)


def test_publish_without_signer_or_skip_signing_raises():
    # Default behaviour now requires explicit signing decision.
    with HubClient(transport=_mock(lambda r: httpx.Response(200, json=_MANIFEST))) as c:
        scen = "/tmp/non-existent-scenario-dir-mimic-test"
        # The directory check fires before the signer check, but if we point at
        # an existing dir we'd hit the signer check. Use a real dir.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            from pathlib import Path as _P
            (_P(td) / "scenario.yaml").write_text(
                "apiVersion: mimic.scenario/v1\nkind: Scenario\n"
                "metadata:\n  name: x\n  version: 0.0.1\n  license: MIT\n"
                "  author_did: did:web:test\n  mimic_version: '>=0.2.0,<0.4.0'\n"
                "spec:\n  event:\n    iri: https://x.test/e\n    duration_days: 1\n"
                "  scope:\n    tiers: [T3]\n  mc:\n    paths: 1\n    horizon_days: 1\n    seed_global: 1\n"
            )
            with pytest.raises(HubError, match="signer"):
                c.publish(td, api_key="k")


def test_publish_with_signer_sends_signature_field(tmp_path):
    """Verify the signature payload is included in the multipart upload."""
    received = {}

    def handler(request):
        received["body"] = request.content
        received["url"] = str(request.url)
        return httpx.Response(200, json=_MANIFEST)

    # write a minimal scenario
    (tmp_path / "scenario.yaml").write_text(
        "apiVersion: mimic.scenario/v1\nkind: Scenario\n"
        "metadata:\n  name: x\n  version: 0.0.1\n  license: MIT\n"
        "  author_did: did:web:test\n  mimic_version: '>=0.2.0,<0.4.0'\n"
        "spec:\n  event:\n    iri: https://x.test/e\n    duration_days: 1\n"
        "  scope:\n    tiers: [T3]\n  mc:\n    paths: 1\n    horizon_days: 1\n    seed_global: 1\n"
    )

    from mimic.framework.scenario import LocalDevSigner

    signer = LocalDevSigner.generate()
    with HubClient(transport=_mock(handler)) as c:
        c.publish(tmp_path, api_key="k", signer=signer, signer_did="did:web:test")

    # The multipart body should contain a `signature` form field
    assert b'name="signature"' in received["body"]
    assert b"local-dev" in received["body"]


def test_publish_skip_signing_warns():
    """skip_signing=True must emit a UserWarning."""
    import tempfile
    from pathlib import Path as _P
    with tempfile.TemporaryDirectory() as td:
        (_P(td) / "scenario.yaml").write_text(
            "apiVersion: mimic.scenario/v1\nkind: Scenario\n"
            "metadata:\n  name: x\n  version: 0.0.1\n  license: MIT\n"
            "  author_did: did:web:test\n  mimic_version: '>=0.2.0,<0.4.0'\n"
            "spec:\n  event:\n    iri: https://x.test/e\n    duration_days: 1\n"
            "  scope:\n    tiers: [T3]\n  mc:\n    paths: 1\n    horizon_days: 1\n    seed_global: 1\n"
        )
        with HubClient(transport=_mock(lambda r: httpx.Response(200, json=_MANIFEST))) as c:
            with pytest.warns(UserWarning, match="skip_signing"):
                c.publish(td, api_key="k", skip_signing=True)
