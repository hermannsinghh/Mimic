---
name: mimic-release
description: Run the Mimic release dance — bench, sign, SBOM, GitHub release, Hub push, changelog
---

# Cutting a Mimic release

Read this before tagging a release on `mimic-framework`, `mimic-forecast`, or `mimic-world`.
Contract: Plan §13.

## Release cadence

- Framework / forecast / world: **minor every 6 weeks**, patch on demand.
- Hub: continuous deploy.
- Scenarios: independent — release any time.

## SemVer policy

- **Major** — canonical schema change, `world_state_hash` change, scenario spec change.
- **Minor** — new adapters, new prefabs, new connectors, routing-tier threshold changes.
- **Patch** — bugfixes, perf, docs.

## Pre-release checklist

- [ ] `pytest -q` green in every changed package; coverage ≥80% on framework/forecast/world.
- [ ] `bench.yml` green nightly: forecast bench, agent bench, calibration replay.
- [ ] `license.yml` green: LICENSE, NOTICE, LICENSE-BSL, LICENSE-CHANGE-DATE present;
      no GPL deps in BSL packages.
- [ ] `determinism.yml` green: golden hash vectors match.
- [ ] CHANGELOG entry under `## [<version>] - YYYY-MM-DD`.
- [ ] If a contract changed (schema / hash / spec / routing formula), there is a matching
      `decision-record/` ADR.

## Release commands

```bash
# 1. Tag (annotated, signed)
git tag -s v0.2.0 -m "mimic-framework 0.2.0"

# 2. Push tag — release.yml fires automatically
git push origin v0.2.0

# release.yml builds wheel + OCI runtime image, signs with cosign,
# uploads SBOM (CycloneDX) to release assets, publishes SLSA Level 3 provenance.
```

## Post-release

- [ ] Verify the release on Mimic Hub: every published scenario referencing the old version
      has a CI job opened to test against the new one.
- [ ] Update `docs/migration/` if there were breaking changes.
- [ ] If this is a schema major bump, post the migration guide in the release notes AND
      announce on the Hub deprecation channel.

## Red flags that block a release

- A red `bench.yml` — calibration regressions are never shipped.
- Missing SBOM — every release asset must include a CycloneDX SBOM.
- Cosign signature failure — never release unsigned wheels or images.
- An unmerged ADR for a contract change.
