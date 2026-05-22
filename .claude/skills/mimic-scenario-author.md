---
name: mimic-scenario-author
description: Walks Claude Code through authoring a new Mimic scenario — layout, FIBO validation, signing, publishing
---

# Authoring a new Mimic scenario

Read this before creating or substantially editing any scenario in `scenarios/`. The contract
comes from Plan §10.

## Required artifact layout

```
scenarios/<scenario-name>/
├── scenario.yaml           # apiVersion mimic.scenario/v1
├── inputs.schema.json      # JSON Schema; entity types use FIBO IRIs
├── workflow.py             # Temporal workflow OR declarative YAML
├── agents/                 # optional: custom prefabs
├── seeds/manifest.yaml     # SeedManifest
├── data_refs.lock          # OCI/IPFS CIDs of input datasets
├── eval/historical/        # historical-episode replay sets
├── badges/calibration.json # written by Hub on publish — never author-supplied
└── SIGNATURES              # cosign signatures + SLSA in-toto attestations
```

## scenario.yaml canonical fields

```yaml
apiVersion: mimic.scenario/v1
kind: Scenario
metadata:
  name: <kebab-case-name>
  version: <semver>
  license: MIT
  author_did: did:web:<your-domain>
  mimic_version: ">=0.2.0,<0.4.0"
spec:
  event:
    iri: https://mimic.ai/events/<category>/<event-slug>
    duration_days: <int>
  scope:
    tiers: [T1, T2, T3]
    entity_filter: "<SQL-ish filter on FIBO entity attrs>"
  mc:
    paths: <int, ≥1>
    horizon_days: <int, ≥1>
    seed_global: <int>
  reloop: false
  budget_usd: <float>
```

## Authoring checklist

- [ ] `scenario.yaml` validates against `mimic.framework.scenario.load_spec`.
- [ ] Every entity/instrument/event in `inputs.schema.json` resolves to a FIBO 2025-Q3 IRI.
- [ ] `seeds/manifest.yaml` includes a `global_seed` AND specifies HKDF-SHA256 derivation.
- [ ] `data_refs.lock` pins every input dataset by OCI digest or IPFS CID — no `latest` tags.
- [ ] `eval/historical/` has at least one episode with known outcomes for calibration.
- [ ] The scenario passes `mimic.framework.scenario.load_spec` AND a dry-run on
      `tests/scenarios/dry_run.py`.
- [ ] Signed with cosign — the `SIGNATURES` directory contains a Rekor transparency log entry.

## Publishing

1. Bench the scenario locally: `mimic scenario bench <name>` — produces a draft calibration
   badge. **Do not commit the draft** — the Hub writes the final badge.
2. `mimic scenario push <name>` uploads to Hub. Hub re-runs calibration and writes
   `badges/calibration.json` server-side.
3. Hub posts a Sigstore + SLSA attestation; the published artifact URI is OCI-addressed.

## Things to refuse

- A scenario without `eval/historical/` — cannot be calibrated, cannot ship.
- A scenario that pins `mimic_version: ">=0.1"` — must be `>=0.2.0`.
- Author-supplied `badges/calibration.json` — Hub writes this; client supply is rejected.
- Inputs using non-FIBO entity types — write a translator instead.
