"""Scenario spec parser, OCI artifact pack/unpack, signing.

Implements Plan §3.1 F-01, F-02, F-03 and §10 (Scenario Spec).
"""
from .artifact import (  # noqa: F401
    ArtifactManifest,
    ArtifactVerificationError,
    FileEntry,
    LocalFSStore,
    OCIStore,
    pack,
    unpack,
)
from .runner import (  # noqa: F401
    FrozenRunRequired,
    ScenarioRunner,
    ScenarioRunManifest,
    deterministic_stub_personas,
    run_scenario_e2e,
)
from .signing import (  # noqa: F401
    LocalDevSigner,
    Signature,
    SignatureVerificationError,
    SigstoreSigner,
    Signer,
    verify_with_public_key,
)
from .spec import ScenarioSpec, load_spec  # noqa: F401

__all__ = [
    "ScenarioSpec", "load_spec",
    "ArtifactManifest", "FileEntry", "pack", "unpack",
    "LocalFSStore", "OCIStore", "ArtifactVerificationError",
    "Signer", "Signature", "LocalDevSigner", "SigstoreSigner",
    "SignatureVerificationError", "verify_with_public_key",
    "ScenarioRunner", "ScenarioRunManifest", "FrozenRunRequired",
    "deterministic_stub_personas", "run_scenario_e2e",
]
