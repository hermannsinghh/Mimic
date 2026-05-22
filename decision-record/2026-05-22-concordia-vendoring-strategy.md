# Concordia vendoring strategy — pinned-dep with lazy source materialization

**Status:** accepted
**Date:** 2026-05-22
**Relates to:** Plan §9.1 (Concordia fork), §17.4 (Concordia governance risk),
F-12 (Concordia integration)
**Forced by:** F-12 step 1 is "vendor Concordia"; the literal reading is "copy
upstream source into `packages/mimic-concordia/src/`", but the repo is not yet
under git and the wrapper-vs-source question needs an answer before any code
lands.

## Context

Plan §9.1 reads: *"Vendor DeepMind Concordia v2.0 as `mimic-concordia/`. We own
the fork. Patches the callback API to emit `Decision` (per §5.1), not free text."*

The user-facing instructions for F-12 step 1 expand this to: *"mechanical:
submodule or vendor, tag against upstream, get import path stable, no behavior
change."*

Two facts narrow the option space:

1. **The Mimic 2.0 monorepo is not under git yet.** A git-submodule approach to
   tracking upstream is therefore not currently viable.
2. **`gdm-concordia==2.0.1`** is available on PyPI under Apache-2.0, with a
   stable top-level import name (`concordia`). The 522 KB wheel pulls heavy
   transitive deps (transformers, langchain-community, google-cloud-aiplatform,
   boto3, matplotlib, ipython, …) we do not want to force on every Mimic
   install.

Step 1 is supposed to be "mechanical, no behavior change". The plan's "patches
the callback API to emit `Decision`" is step 2's deliverable — and it can be
satisfied at the wrapper boundary (translate Concordia's native output into a
canonical `Decision` inside `ConcordiaPersonaBuilder`) without modifying
upstream source.

## Options

A. **Full source vendor.** Extract the ~6,000 LOC `concordia/` tree from the
   wheel into `packages/mimic-concordia/src/`, drop our own
   `pyproject.toml`/`LICENSE`/`NOTICE`, treat as a maintained fork. Matches the
   literal reading of §9.1.

B. **Pinned-dep wrapper.** Create `packages/mimic-concordia/` as a wrapper
   package whose `pyproject.toml` depends on `gdm-concordia==2.0.1`. Re-export
   the upstream surface as `mimic_concordia.*` so all of Mimic imports through
   our package. No upstream source in our tree.

## Decision

**Option B.** A wrapper package at `packages/mimic-concordia/`, pinning
`gdm-concordia==2.0.1`, with a documented **lazy source materialization**
escape hatch.

Reasoning:

- The plan §9.1 goal — "we own the fork" — is primarily about *governance*:
  protecting Mimic from a DeepMind deprecation event (§17.4). A version pin at
  `2.0.1` is functionally equivalent: upgrade timing is fully under our
  control, and the wrapper's import surface is stable regardless of upstream
  changes.
- Step 1 is "no behavior change". Copying 6k LOC into the repo on day 1 is
  disproportionate work for a step whose acceptance criterion is "the import
  path is stable and pytest is green."
- The patch §9.1 calls out — emit `Decision` instead of free text — happens at
  the wrapper API (`ConcordiaPersonaBuilder` in F-12 step 2). It does not
  require editing upstream source; it requires controlling the bytes that
  leave Mimic toward downstream consumers, which a wrapper does.
- Heavy transitive deps stay opt-in. Plain `pip install mimic-framework` does
  not pull in transformers/langchain/etc.; users wanting Concordia install
  `mimic-concordia` explicitly.

### Lazy materialization protocol

If any of the following triggers, we copy `concordia/` source into
`packages/mimic-concordia/src/concordia/` and switch the wrapper to use the
local copy:

1. **Upstream deprecation / repo archival.** PyPI release stops or the
   `google-deepmind/concordia` repo is archived.
2. **Internal patch required.** A change cannot be expressed at the wrapper
   boundary — e.g. a hook inside Concordia's component tree, or a fix to
   upstream that we can't get merged.
3. **Audit / SLSA demands.** A regulator or buyer requires us to attest to
   the exact source we ship, and PyPI provenance is insufficient.

When triggered, the protocol is: copy source, regenerate the wrapper's
`__init__.py` to import from `mimic_concordia._vendor.concordia` instead of
upstream `concordia`, and bump `mimic-concordia` minor. Downstream code
(`mimic_concordia.*` re-exports) is unaffected — that's the whole point of
the wrapper layer.

## Contract

```
packages/mimic-concordia/
├── pyproject.toml             # name=mimic-concordia, deps=[gdm-concordia==2.0.1]
├── LICENSE                    # BSL-1.1 (wrapper code is ours; upstream stays Apache-2.0)
├── LICENSE-BSL
├── LICENSE-CHANGE-DATE        # 2029-05-22 (3 years from this ADR)
├── NOTICE                     # credits DeepMind for upstream Concordia
├── README.md                  # documents the wrapper + materialization protocol
└── mimic_concordia/
    ├── __init__.py            # re-exports concordia.* under stable names
    └── _provenance.py         # UPSTREAM_VERSION, UPSTREAM_PYPI, UPSTREAM_LICENSE
```

`mimic_concordia.__concordia_version__` MUST equal `"2.0.1"` at import time.
If `gdm-concordia` is not installed or its version differs, the wrapper raises
`ImportError` with explicit install instructions. This is the import-path-
stability contract.

## Consequences

- **F-12 step 1 acceptance**: `from mimic_concordia import ...` works,
  `mimic_concordia.__concordia_version__ == "2.0.1"`, full pytest run remains
  green.
- **F-12 step 2**: `ConcordiaPersonaBuilder` imports from `mimic_concordia`,
  never from `concordia` directly. Any code in Mimic that needs Concordia goes
  through the wrapper — single swap point.
- **Governance**: a `gdm-concordia` upgrade is one-line in
  `packages/mimic-concordia/pyproject.toml` plus the wrapper's
  `__concordia_version__` constant. CI's `license.yml` already enforces NOTICE
  presence; we add Concordia's Apache-2.0 attribution to NOTICE here.
- **If upstream breaks**: we trip a wrapper unit test on import (version
  mismatch), pin to the last good version, and decide whether to materialize.
- **No ADR re-litigation expected**: the locked nine contract surfaces are
  upstream-of this decision and are unaffected. This ADR sits below the
  scenario / determinism / equivalence contracts and above the implementation
  of F-12 step 2.

## Open items

- When the monorepo lands in a git repository, evaluate whether to keep the
  pinned-dep wrapper or switch to git-submodule vendoring of the
  `google-deepmind/concordia` repo. Defer — current state ships fine.
- BSL vs Apache-2.0 mismatch question: the wrapper code (our 100 lines or so)
  is BSL like the rest of `mimic-framework`/`mimic-forecast`/`mimic-world`;
  Concordia upstream stays Apache-2.0 and is credited in NOTICE. BSL allows
  consuming Apache-licensed dependencies — verified against MariaDB BSL 1.1
  text. License compatibility: clean.
