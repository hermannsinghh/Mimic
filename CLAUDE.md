# Mimic 2.0 — Agent Operating Instructions

This repository is the **Mimic 2.0** monorepo. Before any architecture-affecting work, read
[PLAN.md](PLAN.md) top-to-bottom. The plan is the single source of truth — when it conflicts
with anything else, the plan wins.

## Non-negotiable invariants (Plan §0)

Every commit must respect:

1. **Auditability** — every simulation run produces a `world_state_hash` and a signed event log
   replayable from inputs.
2. **Composability** — every capability is a Python module callable from a Temporal workflow.
   No monolithic CLI assumptions.
3. **Schema-canonical** — entities, instruments, events, decisions, outcomes are
   FIBO / ACORD / ISO 20022 / FpML IRI-addressable before they touch any solver.

## Anti-goals (do not build, do not accept PRs for)

- A web UI no-code workflow builder. We are SDK-first.
- A new ontology. Use FIBO; write translators only.
- Crypto tokens, on-chain marketplaces, blockchain replay.
- Reproductions of Aladdin / RMS / Verisk integrations (avoid Aladdin-land for 18 months).

## Where things live

```
packages/
  mimic-framework/   BSL — scenario, schema, workflow, agents, routing, determinism, sim, signal, bench, policy
  mimic-forecast/    BSL — frontier time-series adapters (Toto 2.0, Timer-S1, TiRex, Chronos, …)
  mimic-world/       BSL — provably-correct contagion math (Eisenberg-Noe, DebtRank)
  mimic-sim/         legacy — being absorbed into mimic-framework.sim during 0.2.x
  mimic-signal/      legacy — being absorbed into mimic-framework.signal during 0.2.x
  mimic-bench/       legacy — being absorbed into mimic-framework.bench during 0.2.x
hub/                 AGPL — Mimic Hub scenario registry (FastAPI + Postgres + OCI + Sigstore)
scenarios/           MIT  — first-party reference scenarios
eval/                MIT  — historical-episode calibration harness
infra/               MIT  — Terraform/Pulumi for Temporal Cloud, Modal, OCI registry
docs/                MIT  — Docusaurus / MkDocs site
decision-record/     architectural decision records (ADRs)
tests/determinism/   golden hash vectors — touch only with a schema major bump
```

## Skills

Before doing one of the tasks below, read the matching skill in `.claude/skills/`:

- Authoring a new scenario → `mimic-scenario-author.md`
- Adding a data connector → `mimic-connector-author.md`
- Adding a Concordia prefab → `mimic-prefab-author.md`
- Reviewing a PR for determinism → `mimic-determinism-check.md`
- Cutting a release → `mimic-release.md`
- Bumping FIBO/ACORD/ISO 20022/FpML versions → `mimic-schema-bump.md`

## Contracts that require special care

These four contracts are versioned independently of the rest of the code. Touching any of them
forces a schema major bump and a refresh of `tests/determinism/golden/`:

1. **Canonical schema** — `mimic.framework.schema.Decision` / `Outcome` (Plan §5.1).
2. **Determinism** — `world_state_hash` Merkle-DAG, SeedManifest HKDF derivation (Plan §7).
3. **Scenario spec** — `apiVersion: mimic.scenario/v1` (Plan §10).
4. **Routing systemic-score formula** — `routing/systemic.py` (Plan §6.1) — semver minor bump.

## Required CI workflows (Plan §13.1)

`test.yml`, `bench.yml`, `license.yml`, `determinism.yml`, `release.yml`, `fibo-bump.yml`, `sbom.yml`.
Never disable a required workflow. Coverage threshold ≥80% on framework/forecast/world.

## Milestones (Plan §16)

At day 30 / 90 / 180 from the project kickoff (2026-05-21), run the checklist in Plan §16 and
write a status report to `docs/status/<date>.md`.

## When in doubt

Open a `decision-record/` ADR with the options, decision, and consequences. Never silently
deviate from the plan.
