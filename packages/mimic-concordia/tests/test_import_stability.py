"""F-12 step 1 contract: mimic_concordia provides a stable, version-pinned
import root for everything in Mimic that talks to DeepMind Concordia.

These tests pin the contract surface promised by ADR
``decision-record/2026-05-22-concordia-vendoring-strategy.md``. Breaking any
one of them means the wrapper no longer gives F-12 the import-stability it
needs to swap implementations later.
"""
from __future__ import annotations

import importlib

import pytest


def test_mimic_concordia_imports() -> None:
    mc = importlib.import_module("mimic_concordia")
    assert mc is not None


def test_pin_matches_provenance() -> None:
    import mimic_concordia
    from mimic_concordia import _provenance

    assert mimic_concordia.EXPECTED_CONCORDIA_VERSION == _provenance.UPSTREAM_VERSION
    assert mimic_concordia.__concordia_version__ == _provenance.UPSTREAM_VERSION


def test_pin_is_v2_0_1() -> None:
    """The exact version pin is the audit contract. Bumping it requires an ADR
    + a re-record of all cassettes (because the model_fingerprint inputs may
    shift). Tightening this string is the warning sign."""
    import mimic_concordia

    assert mimic_concordia.__concordia_version__ == "2.0.1"


def test_concordia_is_reexported() -> None:
    """`from mimic_concordia import concordia` is the documented stable path."""
    import mimic_concordia

    assert hasattr(mimic_concordia, "concordia")
    import concordia as upstream

    assert mimic_concordia.concordia is upstream


def test_provenance_constants_are_complete() -> None:
    from mimic_concordia import _provenance

    assert _provenance.UPSTREAM_PYPI == "gdm-concordia"
    assert _provenance.UPSTREAM_VERSION == "2.0.1"
    assert _provenance.UPSTREAM_LICENSE_SPDX == "Apache-2.0"
    assert _provenance.UPSTREAM_HOME.startswith("https://github.com/google-deepmind/concordia")
    assert _provenance.VENDORING_STRATEGY == "pinned-dep"
    assert "concordia-vendoring-strategy" in _provenance.VENDORING_ADR


def test_version_mismatch_class_is_importable() -> None:
    """Downstream code (and CI) should be able to catch this exception by name."""
    from mimic_concordia import ConcordiaVersionMismatch

    assert issubclass(ConcordiaVersionMismatch, ImportError)


def test_provenance_module_alone_does_not_import_concordia(monkeypatch: pytest.MonkeyPatch) -> None:
    """_provenance must be safe to import without gdm-concordia installed.

    The version check lives in ``mimic_concordia.__init__``; the provenance
    module is the metadata source it consults and is depended on by the
    NOTICE / SBOM tooling. It must not transitively import ``concordia``.
    """
    import sys

    mod = importlib.reload(importlib.import_module("mimic_concordia._provenance"))
    assert mod.UPSTREAM_PYPI == "gdm-concordia"
    # _provenance must not pull in the heavy concordia tree on its own.
    # (mimic_concordia.__init__ is allowed to; provenance is not.)
    # We can't fully assert "concordia not in sys.modules" because the test
    # suite may import mimic_concordia elsewhere, but we can assert that
    # reloading _provenance alone doesn't add it.
    before = "concordia" in sys.modules
    importlib.reload(mod)
    after = "concordia" in sys.modules
    assert after == before, "reloading _provenance must not import concordia"
