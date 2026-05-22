# mimic-framework — Agent Instructions

This package is the top-level SDK: scenario spec, schema, runtime glue. It also absorbs
`mimic-sim`, `mimic-signal`, `mimic-bench` as internal modules under `mimic.framework.*`.

## Hard rules

- **Never change `mimic.framework.schema.Decision` or `Outcome`** (see [decision.py](mimic/framework/schema/decision.py))
  without bumping the schema major version AND updating golden vectors in `../../tests/determinism/golden/`.
- **Never change `world_state_hash` computation** without the same major bump + golden refresh.
- **No new entity/instrument/event types** — bind to a FIBO IRI or write a translator.
- LLM provider adapters MUST emit `model_fingerprint = sha256(provider|model|version|system_prompt|temperature|tool_schema)`
  on every call (Plan §4.2).
- Frozen-run mode (`MIMIC_FROZEN_RUN=1`) must raise `FrozenRunCacheMiss` on a cache miss —
  never silently re-call the LLM (Plan §7.3).

## Module map (Plan §1.2)

```
mimic/framework/
  scenario/      — Scenario spec parser, OCI artifact pack/unpack, signing
  schema/        — FIBO/ACORD/ISO 20022/FpML translators + canonical models
  workflow/      — Temporal workflow definitions + activities
  agents/        — Concordia fork glue + LangGraph reasoning nodes
  routing/       — RouteLLM-style tier cascade
  determinism/   — SeedManifest, world_state_hash, frozen-run cache
  sim/           — (legacy: mimic_sim re-export) Monte Carlo orchestration
  signal/        — (legacy: mimic_signal re-export) Event extraction
  bench/         — (legacy: mimic_bench re-export) Calibration harness
  policy/        — OPA/Cedar policy decision point
```

The legacy re-exports must continue to work until the 0.3.0 release. Do not delete them.

## Build queue (Plan §3.1)

Pick P0 tasks before P1 in ID order: F-01, F-02, F-03, F-04, F-05, F-06, F-07, F-12.
P1: F-08, F-09, F-10, F-11.

## FIBO release

Pinned in `pyproject.toml` under `[tool.mimic] fibo-version = "2025-Q3"`. Bumps are quarterly
via the `fibo-bump.yml` workflow. Never auto-merge a FIBO PR.
