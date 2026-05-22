# Mimic 2.0

Audit-grade stress-testing SDK for any financial institution — with reinsurance treaty pricing
as the lighthouse vertical.

**This repo is a monorepo (uv workspace).** The build plan is in [PLAN.md](PLAN.md); agent
operating instructions are in [CLAUDE.md](CLAUDE.md).

## Layout

```
packages/
  mimic-framework/   BSL — scenario, schema, workflow, agents, routing, determinism, sim, signal, bench, policy
  mimic-forecast/    BSL — frontier time-series adapters
  mimic-world/       BSL — contagion math (Eisenberg-Noe, DebtRank)
  mimic-sim/         legacy (being absorbed)
  mimic-signal/      legacy (being absorbed)
  mimic-bench/       legacy (being absorbed)
hub/                 AGPL — Mimic Hub scenario registry
scenarios/           MIT  — first-party reference scenarios (7 stubs)
eval/                MIT  — calibration harness
infra/               MIT  — Terraform + Modal
docs/                MIT  — site
decision-record/     ADRs
tests/determinism/   golden hash vectors
```

## Invariants

1. Auditability — every run produces a `world_state_hash` and signed event log.
2. Composability — every capability callable from a Temporal workflow.
3. Schema-canonical — bind to FIBO / ACORD / ISO 20022 / FpML, do not invent types.

## Quickstart (coming, day-30 target)

```bash
uv sync
mimic scenario run scenarios/svb-replay-2023
```

## License

- `packages/mimic-framework`, `packages/mimic-forecast`, `packages/mimic-world` core: BSL 1.1, converts to Apache-2.0 on 2029-05-21.
- `hub/`: AGPL-3.0.
- `scenarios/`, `docs/`, examples: MIT.
- Hub-client SDK (separate package): Apache-2.0.

See each package's LICENSE for full terms.
