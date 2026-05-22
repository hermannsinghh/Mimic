# scenarios/ — Agent Instructions

First-party reference scenarios. **MIT-licensed** — anyone can fork, modify, republish.

Before authoring a scenario, read `.claude/skills/mimic-scenario-author.md`.

## Required layout per scenario (Plan §10.1)

```
my-scenario/
  scenario.yaml           # name, version (semver), license, author DID, mimic-version range
  inputs.schema.json      # JSON Schema; entity types use FIBO IRIs
  workflow.py             # Temporal workflow OR declarative YAML
  agents/                 # optional: custom prefabs
  seeds/manifest.yaml     # SeedManifest
  data_refs.lock          # OCI/IPFS CIDs of input datasets
  eval/historical/        # historical-episode replay sets
  badges/calibration.json # written by Hub on publish, NOT author-supplied
  SIGNATURES              # cosign signatures + SLSA in-toto attestations
```

## First-party scenarios (Plan §10.3)

- `taiwan-strait-30d-closure` — Marine + global trade cascade (lighthouse: reinsurer)
- `svb-replay-2023` — Calibration benchmark (lighthouse: mid-banks)
- `uk-gilt-ldi-2022` — UK pension/LDI cascade (lighthouse: UK pension / BoE)
- `covid-dash-for-cash-2020` — Liquidity stress benchmark (lighthouse: central bank)
- `2008-gfc-bank-cascade` — Bank contagion benchmark (lighthouse: G-SIB / regulator)
- `cyber-cat-2026` — Cyber insurance correlation (lighthouse: reinsurer / cyber syndicate)
- `eu-ai-act-model-risk-2026` — AI model risk overlay (lighthouse: EU life/health insurer)
