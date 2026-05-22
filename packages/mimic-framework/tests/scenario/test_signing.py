"""Tests for artifact signing — Plan §3.1 F-03."""
from __future__ import annotations

import pytest

from mimic.framework.scenario import (
    LocalDevSigner,
    SignatureVerificationError,
    verify_with_public_key,
)


def test_sign_and_self_verify():
    signer = LocalDevSigner.generate()
    sig = signer.sign("a" * 64, signer_did="did:web:test")
    signer.verify(sig)  # no raise


def test_signature_carries_required_fields():
    signer = LocalDevSigner.generate()
    sig = signer.sign("b" * 64, signer_did="did:web:munichre")
    assert sig.artifact_digest == "b" * 64
    assert sig.signer_did == "did:web:munichre"
    assert sig.backend == "local-dev"
    assert len(sig.signature_hex) == 128  # Ed25519 sig = 64 bytes = 128 hex
    assert "public_key_hex" in sig.metadata


def test_verify_with_public_key_round_trip():
    signer = LocalDevSigner.generate()
    sig = signer.sign("c" * 64, signer_did="did:web:test")
    pk_hex = sig.metadata["public_key_hex"]
    verify_with_public_key(sig, pk_hex)  # no raise


def test_verify_fails_on_tampered_digest():
    signer = LocalDevSigner.generate()
    sig = signer.sign("d" * 64, signer_did="did:web:test")
    tampered = type(sig)(
        artifact_digest="e" * 64,
        signer_did=sig.signer_did,
        signature_hex=sig.signature_hex,
        backend=sig.backend,
        metadata=sig.metadata,
    )
    with pytest.raises(SignatureVerificationError):
        signer.verify(tampered)


def test_verify_fails_with_wrong_public_key():
    signer_a = LocalDevSigner.generate()
    signer_b = LocalDevSigner.generate()
    sig = signer_a.sign("f" * 64, signer_did="did:web:a")
    with pytest.raises(SignatureVerificationError):
        signer_b.verify(sig)


def test_local_signer_pem_round_trip(tmp_path):
    signer = LocalDevSigner.generate()
    pem = signer.export_private_pem()
    pem_path = tmp_path / "key.pem"
    pem_path.write_bytes(pem)
    restored = LocalDevSigner.from_pem(pem_path)
    sig = restored.sign("aa" * 32, signer_did="did:web:test")
    restored.verify(sig)
    signer.verify(sig)  # same key, both signers should agree
