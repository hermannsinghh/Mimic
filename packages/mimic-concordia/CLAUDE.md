# mimic-concordia — Agent Instructions

This package is the **import-stability wrapper** around DeepMind Concordia
(`gdm-concordia` on PyPI). It is the *only* place in Mimic that touches
`concordia.*` symbols directly. Everything else imports through
`mimic_concordia.*`.

Plan reference: §9.1. ADR: [2026-05-22-concordia-vendoring-strategy](../../decision-record/2026-05-22-concordia-vendoring-strategy.md).

## Hard rules

- **Never bump `gdm-concordia` without an ADR.** The version pin in
  `pyproject.toml` AND `mimic_concordia/_provenance.py` AND the test in
  `tests/test_import_stability.py::test_pin_is_v2_0_1` MUST agree on the
  exact version. The test is the gate; failing it without changing the pin
  in code is the audit signal.
- **Never add Mimic-side glue logic here.** Persona builders, prefab
  adapters, callback patches, BAML schemas — all belong in
  `packages/mimic-framework/mimic/framework/agents/concordia_runtime/`.
  This package only ferries the upstream surface across the wrapper boundary.
- **Never strip the upstream `concordia` import name.** Downstream Mimic
  code may do `from mimic_concordia import concordia` and expect the upstream
  module object. Adding our own `concordia` shadow would silently break
  upstream type identity.

## When to materialize the source fork

The wrapper is pinned-dep today. Source materialization (copying upstream
into `mimic_concordia/_vendor/concordia/`) is triggered by any of:

1. Upstream PyPI release stops or `google-deepmind/concordia` repo is archived.
2. A required change to Concordia internals that we cannot patch at the
   wrapper boundary or upstream into a release.
3. A regulator or buyer requires source-level provenance beyond PyPI hashes.

Protocol for materialization is documented in the ADR. Do not preemptively
materialize — that adds maintenance burden without benefit, and the lazy
path was the explicit ADR choice.

## Bumping `gdm-concordia`

When (and only when) the ADR has signed off on a bump:

1. Update the version in `pyproject.toml` (`dependencies`).
2. Update `UPSTREAM_VERSION` in `mimic_concordia/_provenance.py`.
3. Update `test_pin_is_v2_0_1` in `tests/test_import_stability.py` to the new
   version (rename the test if appropriate).
4. **Re-record every cassette** under `tests/fixtures/frozen-run/` against the
   new Concordia. A version bump can change LLM prompts emitted by Concordia
   components, which changes `model_fingerprint`, which changes cache keys.
5. Bump `mimic-concordia` minor.
6. Open a fresh ADR linking back to the vendoring-strategy one.
