"""mimic-concordia — Mimic 2.0 wrapper around DeepMind Concordia v2.0.1.

This module is the **single import boundary** between Mimic and Concordia.
Everything in the Mimic codebase that needs Concordia should import from
`mimic_concordia.*`. That gives us one place to swap the implementation if
upstream deprecates, breaks, or has to be patched (see ADR
``decision-record/2026-05-22-concordia-vendoring-strategy.md``).

Plan reference: §9.1 (Concordia fork), F-12 step 1.
"""
from __future__ import annotations

from importlib import metadata as _metadata
from typing import Final

from . import _provenance


class ConcordiaVersionMismatch(ImportError):
    """Raised at import time when the installed gdm-concordia disagrees with the pin.

    F-12's audit story depends on a known, signed upstream version. A floating
    install means we cannot attest to what Concordia bytes were executed during
    a scenario run, which breaks the §0 auditability invariant.

    Fix: ``pip install 'gdm-concordia==2.0.1'`` (the version declared in
    ``packages/mimic-concordia/pyproject.toml`` and in ``_provenance.py``).
    """


EXPECTED_CONCORDIA_VERSION: Final[str] = _provenance.UPSTREAM_VERSION


def _resolve_concordia_version() -> str:
    """Return the installed gdm-concordia version, or raise ImportError if missing.

    Uses ``importlib.metadata`` so we don't have to import ``concordia`` (and
    pull in its heavy transitive deps: transformers, langchain-community, …)
    just to read the version string.
    """
    try:
        return _metadata.version(_provenance.UPSTREAM_PYPI)
    except _metadata.PackageNotFoundError as exc:
        raise ImportError(
            f"mimic-concordia requires '{_provenance.UPSTREAM_PYPI}'"
            f"=={EXPECTED_CONCORDIA_VERSION}, but it is not installed. "
            f"Install with: pip install '{_provenance.UPSTREAM_PYPI}=={EXPECTED_CONCORDIA_VERSION}'"
        ) from exc


__concordia_version__: Final[str] = _resolve_concordia_version()

if __concordia_version__ != EXPECTED_CONCORDIA_VERSION:
    raise ConcordiaVersionMismatch(
        f"Installed gdm-concordia=={__concordia_version__!r} does not match "
        f"the mimic-concordia pin (expected {EXPECTED_CONCORDIA_VERSION!r}). "
        f"This pin is the audit-grade contract surface — bumping it requires "
        f"reviewing {_provenance.VENDORING_ADR} and bumping mimic-concordia."
    )

# Eager import so `from mimic_concordia import concordia` is the documented
# stable surface. Concordia's own __init__.py is empty (a license header), so
# this import is cheap; transitive heavy deps are only pulled in when the
# caller touches concrete submodules like ``concordia.language_model.openai``.
import concordia  # noqa: E402  (intentional post-version-check import)

# Eagerly re-export the concordia submodules used inside
# ``mimic.framework.agents.concordia_runtime``. This is the import-stability
# surface: downstream code does
#
#     from mimic_concordia import language_model, entity_typing,
#                                 entity_minimal, basic_associative_memory
#
# so the grep ``from concordia`` / ``import concordia`` boundary stays
# inside this package only.
#
# A previous draft used sys.modules aliasing (``sys.modules[
# 'mimic_concordia.concordia'] = concordia``) to enable the deep
# ``from mimic_concordia.concordia.X.Y import Z`` form. That caused Python
# to load each touched submodule a second time under the mimic_concordia
# namespace, which made enum identity fail across the two paths
# (``mimic_concordia.concordia.typing.entity.OutputType.FREE`` was a
# different class from ``concordia.typing.entity.OutputType.FREE``, breaking
# every component that does ``output_type == entity_lib.OutputType.FREE``).
# Eager named re-exports avoid that pitfall.
from concordia.language_model import language_model as language_model  # noqa: E402
from concordia.typing import entity as entity_typing  # noqa: E402
from concordia.prefabs.entity import minimal as entity_minimal  # noqa: E402
from concordia.associative_memory import basic_associative_memory  # noqa: E402

__all__ = [
    "__concordia_version__",
    "EXPECTED_CONCORDIA_VERSION",
    "ConcordiaVersionMismatch",
    "concordia",
    "_provenance",
    "language_model",
    "entity_typing",
    "entity_minimal",
    "basic_associative_memory",
]
