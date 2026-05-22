# Runner ↔ Concordia equivalence criterion

**Status:** accepted
**Date:** 2026-05-21
**Relates to:** F-12 (Concordia integration), §9 (agent reasoning), §11 (calibration)
**Forced by:** F-12 about to land; we need the contract for "same scenario, both
runners produce equivalent decisions" *before* the integration starts —
otherwise we'll relitigate it under pressure during the actual swap.

## Context

The in-process `ScenarioRunner` (day-30 closer) uses the
`deterministic_stub_personas` builder for its forcing test: two consecutive
runs produce identical `world_state_hash_final`.

When `ConcordiaPersonaBuilder` lands (F-12), the persona-builder slot is
filled by a Concordia-driven prefab cascade that calls real LLMs. Even with
frozen-run mode priming the cache, the Concordia builder will produce
**different** Decisions than the stub on the same scenario — that's the point.

A naive equivalence test would compare the two runners' `world_state_hash_final`
on the same scenario and demand they match. That would be **wrong**:

- Same hash from both runners would mean Concordia produced bit-identical
  Decisions to a deterministic stub — which would only happen if Concordia
  weren't actually reasoning.
- The right equivalence is *distributional*: under reasonable Monte Carlo or
  scenario perturbations, the two runners' decision-action distributions
  should be close.

## Options

A. **Strict same-hash.** Reject the in-process runner as a useful comparison
   tool; only Concordia-vs-Concordia runs count.

B. **No equivalence test.** The two paths are decoupled by design.

C. **Distributional equivalence with a per-prefab threshold.** Compare the
   distribution of decision-action quantities and types from both runners over
   a scenario panel; require 1-Wasserstein distance below a calibrated
   threshold per (prefab, scenario) pair.

## Decision

**Option C.** Reasoning:

- A throws away the value of the in-process runner as a regression-detection
  tool. Without it, a regression in the Concordia integration only surfaces
  when calibration runs against historical episodes — a long cycle.
- B leaves a real gap. When a Concordia version bump silently changes how
  ReinsurerTreatyPricer behaves, we want a fast in-test signal.
- C uses the metrics already implemented in [eval/harness/metrics.py](../eval/harness/metrics.py)
  — `wasserstein1` is the natural distance for 1-D action quantities;
  for the categorical action_type field we use a TV-distance or a chi-square
  over the observed action-type histogram.

## Contract

For each `(prefab, scenario)` pair, the equivalence test asserts:

```python
W1(in_process_decisions[prefab][scenario].quantity,
   concordia_decisions[prefab][scenario].quantity)
    < THRESHOLD_QUANTITY[prefab]

TV(in_process_decisions[prefab][scenario].action_type_histogram,
   concordia_decisions[prefab][scenario].action_type_histogram)
    < THRESHOLD_ACTION_TYPE[prefab]
```

### Threshold provenance — the load-bearing rule

**Thresholds MUST be set ex ante and justified in writing.** Empirically
fitting a threshold to the gap observed between the two runners on day 1
makes the test pass by construction and provides zero diligence signal — a
regulator reading the test sees "same result", not "result within an
independently-defended tolerance."

Each threshold below must carry one of these provenance tags:

- `(domain)` — derived from a domain expert's "indistinguishable for our
  purposes" judgment, with the expert and date named.
- `(theory)` — derived from a published reference (cite paper / regulatory
  guidance / actuarial standard).
- `(prior-art)` — replicated from an existing equivalence regime (cite).

Tags `(empirical-day1)` or anything that means "set to whatever the gap
turned out to be" are NOT acceptable. If the empirically-observed gap
exceeds the ex ante threshold, the integration is not landable; tighten
the prefab, don't loosen the threshold.

Initial thresholds (drafted today as placeholders pending provenance work
during F-12 implementation):

| Prefab | W1 quantity threshold | TV action-type threshold | Provenance |
|---|---|---|---|
| ReinsurerTreatyPricer       | $50M  | 0.20 | TODO (domain) — needs reinsurance broker sign-off |
| BankTreasuryALM             | $100M | 0.25 | TODO (theory) — needs reference to bank-stress literature |
| HedgeFundRiskOfficer        | $25M  | 0.20 | TODO (domain) |
| CentralBankLiquidityProvider | $5B  | 0.15 | TODO (prior-art) — BoE LDI 2022 retrospective |
| RatingAgencyAnalyst         | 1 notch | 0.10 | TODO (prior-art) — agency methodology docs |
| BrokerCedentAdvisor         | $10M  | 0.20 | TODO (domain) |

**Every "TODO" must resolve to a real provenance entry before F-12 lands.**
Landing F-12 with TODO thresholds means we have a "passing" equivalence test
that proves nothing. This is a hard merge gate.

Any threshold change after F-12 is a minor version bump and requires a new
ADR linking back to this one — and the new ADR carries its own provenance
tag justifying the change.

## What stays the same

- Within one runner backend, the bit-reproducibility contract from
  ADR 2026-05-21-audit-grade-refusal still holds: same backend + same seed +
  same inputs → same hash.
- The equivalence test is a separate harness in `tests/equivalence/`, not
  part of the per-package test suite. It runs in `bench.yml` nightly.

## Consequences

- F-12 must ship with its first equivalence test green for at least one prefab
  on at least one scenario. Otherwise the integration is not landable.
- The in-process runner is now a permanent part of the test infrastructure,
  not a stopgap. Removing it requires deprecation + ADR.
- The thresholds in the table above are the contract surface. CR rules apply.
