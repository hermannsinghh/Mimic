"""Artifact signing — Plan §3.1 F-03.

A signed artifact carries:
  - the artifact_sha256 (from F-02)
  - a signature over that digest
  - the signer identity (DID or Sigstore certificate)
  - a Rekor transparency log entry (production only)

Backends:
  - LocalDevSigner: Ed25519 with a local keypair under ~/.mimic/keys/.
    Use for dev/test only — produces a Signature without a transparency log.
  - SigstoreSigner: Sigstore Fulcio + Rekor (stub; raises if sigstore not installed).

Verifying a signature is symmetric: the verifier needs the signer's public key
(local backend) or trusts the Sigstore root (production backend).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)


class SignatureVerificationError(RuntimeError):
    """Raised when a signature fails to verify."""


@dataclass(frozen=True)
class Signature:
    artifact_digest: str
    signer_did: str
    signature_hex: str
    backend: str  # "local-dev" or "sigstore"
    rekor_log_id: str | None = None  # populated by Sigstore backend
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "artifact_digest": self.artifact_digest,
            "signer_did": self.signer_did,
            "signature_hex": self.signature_hex,
            "backend": self.backend,
            "rekor_log_id": self.rekor_log_id,
            "metadata": self.metadata,
        }


class Signer(ABC):
    @abstractmethod
    def sign(self, artifact_digest: str, signer_did: str) -> Signature: ...

    @abstractmethod
    def verify(self, signature: Signature) -> None:
        """Raise SignatureVerificationError on bad signature."""


class LocalDevSigner(Signer):
    """Ed25519 signer using a local keypair. Dev/test only — NOT audit-grade."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._sk = private_key
        self._pk = private_key.public_key()

    @classmethod
    def generate(cls) -> "LocalDevSigner":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_pem(cls, pem_path: str | Path, password: bytes | None = None) -> "LocalDevSigner":
        data = Path(pem_path).read_bytes()
        key = load_pem_private_key(data, password=password)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("PEM does not contain an Ed25519 private key")
        return cls(key)

    def export_private_pem(self) -> bytes:
        return self._sk.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )

    def export_public_raw(self) -> bytes:
        return self._pk.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)

    def public_key(self) -> Ed25519PublicKey:
        return self._pk

    def sign(self, artifact_digest: str, signer_did: str) -> Signature:
        sig = self._sk.sign(artifact_digest.encode("utf-8"))
        return Signature(
            artifact_digest=artifact_digest,
            signer_did=signer_did,
            signature_hex=sig.hex(),
            backend="local-dev",
            metadata={"public_key_hex": self.export_public_raw().hex()},
        )

    def verify(self, signature: Signature) -> None:
        if signature.backend != "local-dev":
            raise SignatureVerificationError(
                f"LocalDevSigner cannot verify backend={signature.backend!r}"
            )
        try:
            self._pk.verify(
                bytes.fromhex(signature.signature_hex),
                signature.artifact_digest.encode("utf-8"),
            )
        except InvalidSignature as e:
            raise SignatureVerificationError(
                f"signature failed verification for digest {signature.artifact_digest}"
            ) from e


def verify_with_public_key(signature: Signature, public_key_raw_hex: str) -> None:
    """Verify a Signature against a known public-key hex string (raw 32 bytes)."""
    pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_raw_hex))
    try:
        pk.verify(
            bytes.fromhex(signature.signature_hex),
            signature.artifact_digest.encode("utf-8"),
        )
    except InvalidSignature as e:
        raise SignatureVerificationError("signature did not verify") from e


class SigstoreSigner(Signer):
    """Production: Sigstore Fulcio + Rekor. Stub until F-03 lands the wiring."""

    def __init__(self) -> None:
        try:
            import sigstore  # type: ignore[import-not-found] # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "sigstore-python is not installed. Use LocalDevSigner for dev."
            ) from e

    def sign(self, artifact_digest: str, signer_did: str) -> Signature:
        raise NotImplementedError("SigstoreSigner.sign lands with F-03 H-03")

    def verify(self, signature: Signature) -> None:
        raise NotImplementedError("SigstoreSigner.verify lands with F-03 H-03")
