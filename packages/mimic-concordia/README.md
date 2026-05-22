# mimic-concordia

The Mimic 2.0 wrapper around DeepMind Concordia v2.0.1.

This package is the **import-stability layer** for Concordia inside the Mimic
codebase. Everything that touches Concordia in Mimic should go through
`mimic_concordia.*`, not `concordia.*` directly. That gives us a single swap
point if upstream deprecates, changes shape, or has to be patched.

Plan reference: §9.1. ADR: [2026-05-22-concordia-vendoring-strategy](../../decision-record/2026-05-22-concordia-vendoring-strategy.md).

## What this package is

A pinned-dep wrapper:

- `gdm-concordia==2.0.1` is a hard dependency (declared in `pyproject.toml`).
- `mimic_concordia/__init__.py` re-exports the upstream `concordia` package
  and exposes a version check.
- `mimic_concordia._provenance` records upstream attribution and the version
  pin, both for humans and for the NOTICE bot.

## What it is not

- Not (yet) a source fork. Concordia upstream's source tree is *not* in this
  repo. We control upgrade timing via the pin in `pyproject.toml`; that is
  the governance equivalent of vendoring for everything below the "we need to
  patch internal code" line.
- Not a place to put Mimic-side glue logic. `ConcordiaPersonaBuilder` and the
  prefab adapters live in `mimic.framework.agents.concordia_runtime`, not
  here. This package only ferries the upstream surface across the wrapper
  boundary.

## Lazy source materialization

If any of the following happen, copy upstream `concordia/` into
`mimic_concordia/_vendor/concordia/` and switch the re-exports to that copy:

1. `gdm-concordia` is removed from PyPI or the GitHub repo is archived.
2. A required change cannot be expressed at the wrapper boundary (must edit
   Concordia internals).
3. A regulator or buyer requires source-level provenance beyond a PyPI hash.

When triggered, the protocol is described in the ADR. The downstream
`mimic_concordia.*` import paths are unaffected.

## Usage

```python
import mimic_concordia
print(mimic_concordia.__concordia_version__)  # "2.0.1"

# Submodules pass through cleanly:
from mimic_concordia import concordia
from mimic_concordia.concordia import agents, language_model, prefabs
```

The wrapper raises `ImportError` if `gdm-concordia` is missing or its
installed version disagrees with the pin. That mismatch is *the* contract for
F-12 step 1.
