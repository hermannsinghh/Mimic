---
name: mimic-schema-bump
description: Handle FIBO/ACORD/ISO 20022/FpML version bumps — update translators, run round-trip tests
---

# Bumping a Mimic schema dependency

Read this before merging a FIBO/ACORD/ISO 20022/FpML version bump. Triggered by `fibo-bump.yml`
(quarterly cron) or a manual ACORD/ISO bump PR.

## Scope of a schema bump

A schema bump is any of:
- FIBO release change (e.g. `2025-Q3` → `2025-Q4`).
- ACORD message version change.
- ISO 20022 message version change.
- FpML release change.

A schema bump is **always** a schema-layer change. It may or may not be a Mimic schema major
bump — depends on whether canonical Decision/Outcome are affected.

## Required steps

1. **Diff the schema.** Use the vendor's published diff (FIBO release notes, ACORD changelog,
   ISO 20022 catalogue). Capture in `decision-record/<date>-<schema>-bump.md`.
2. **Update the pin.**
   - FIBO: `[tool.mimic] fibo-version` in `packages/mimic-framework/pyproject.toml`.
   - ACORD/ISO/FpML: in the relevant translator's `pyproject.toml`.
3. **Update the translators.** Every change in vendor schema needs a matching change in
   `mimic/framework/schema/translate/<vendor>_to_internal.py`.
4. **Run round-trip tests.** `pytest packages/mimic-framework/tests/schema/translate/ -q`.
   The native → canonical → native round-trip must be bit-equivalent on the stable subset.
   Document any newly unstable fields in the ADR.
5. **Update golden vectors only if necessary.** If a hash component changed, this becomes a
   Mimic schema major bump — refresh `tests/determinism/golden/` and follow
   `mimic-determinism-check.md`.
6. **Update docs.** `docs/schema/<vendor>-<version>.md`.

## Never auto-merge a schema bump.

`fibo-bump.yml` opens the PR. A human reviews:
- Translator coverage.
- Round-trip stability.
- Whether the bump propagates to a Mimic schema major version.

## Things to refuse

- A FIBO bump PR that auto-merges via Dependabot — block it; FIBO bumps require schema review.
- A translator update that silently drops a field. Either keep the field with a translation
  rule, or document the drop in the ADR and the canonical schema major bump.
- Skipping round-trip tests "because the diff is small." Always run the full suite.
