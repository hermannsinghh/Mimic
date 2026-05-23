# 2026-05-22 — F-12 steps 3 & 4 against DeepSeek (forward-progress fallback)

## Summary

Live recording of svb-replay-2023 cassettes and noise-floor measurement ran
against DeepSeek V3.2 (T3 per Plan §4.2). Used as a forward-progress
substitute while the canonical Anthropic Opus key is being procured. The
DeepSeek cassettes are **not** the F-12 audit baseline — they live at
`tests/fixtures/frozen-run/svb-replay-2023-deepseek/` and a follow-up
recording against `claude-opus-4-7` is still required to land the
canonical fixtures at `tests/fixtures/frozen-run/svb-replay-2023/`.

## What ran

```
MIMIC_RECORD_PROVIDER=deepseek python scripts/record_svb_cassettes.py
MIMIC_NOISE_PROVIDER=deepseek python scripts/measure_concordia_noise_floor.py
```

### Recording (step 3)

| Metric | Value |
|---|---|
| Provider | `deepseek` (v3.2) |
| Model | `deepseek-chat` |
| Cassettes recorded | 4 |
| Decisions emitted | 2 (one per entity: SVB, FHLB) |
| Total API spend | ~$0.0003 |
| Decision shapes | both `action="hold"`, confidence 0.95 |

DeepSeek correctly identified that SVB and FHLB are banks, not reinsurance
cedents, and returned `"hold"` from the `ReinsurerTreatyPricer` prefab with
rationales explaining the domain mismatch. That's the right signal for
step 5: the prefab needs either domain-tailored prompts or different
prefabs per entity type (`BankTreasuryALM` for banks, etc.).

### Replay verification

Two consecutive `MIMIC_FROZEN_RUN=1` replays against the committed
DeepSeek cassettes produced **bit-identical `world_state_hash_final`**:
`7a42443338c7749d…`. The inner provider was never called (a
`_NeverCalled` sentinel would have raised). Audit-grade round-trip is
green.

### Noise floor (step 4)

| Group | max W1 | mean W1 | sample count |
|---|---|---|---|
| `hold` | 0.0 | 0.0 | 8 (2 entities × 4 seeds) |

Global action-type TV: 0.0. Per the equivalence-criterion ADR's threshold
table, all proposed thresholds ($50M W1 for reinsure/hold) strictly
exceed the measured floor — clean.

## The noise-floor harness has an unstated assumption

**The current `measure_noise_floor` mutates `spec.spec.mc.seed_global`
between runs, but that value is consumed by `SeedManifest` for downstream
contagion math; it does NOT propagate into the LLM provider's `seed`
parameter** (the `Prefab.run()` and `ConcordiaPersonaBuilder.__call__`
paths both pass `seed=None` to the cascade today).

The consequence:

* Different "seeds" pass identical messages to the LLM at identical
  temperatures, so any LLM that is approximately deterministic at
  temperature 0 (DeepSeek's `seed`-honoring path, or Anthropic's
  internal-stochasticity floor) returns ~identical content.
* The measured noise floor with the current harness is therefore
  **spec-seed sensitivity**, not **LLM stochasticity**.

For DeepSeek + temp=0 + identical prompts, that floor is exactly 0. For
Anthropic + temp=0 it would be ε > 0 (Anthropic's internal batching
non-determinism), but still small.

This is a meaningful diagnostic for F-12 step 5 / the equivalence ADR:

1. The ADR's threshold table is more conservative than the current harness
   would catch. Once the equivalence test is wired (step 5), the
   `in_process_runner` ↔ `concordia_runner` cross-builder distance is
   what the threshold gates — *that* delta is large by construction
   (deterministic stub returns 0-quantity holds; Concordia returns
   model-driven decisions), and that's what the threshold should be sized
   against, not the within-runner floor.
2. If we want the harness to also catch LLM stochasticity, the next
   iteration should plumb the seed all the way through to `complete()`
   (a one-line change in `Prefab.run()` and `ConcordiaPersonaBuilder`).
   Out of scope for today; recorded for follow-up.

## Follow-ups

* **Canonical recording**: redo step 3 against `claude-opus-4-7` once
  ANTHROPIC_API_KEY is available. Run
  `ANTHROPIC_API_KEY=… python scripts/record_svb_cassettes.py`.
  Cassettes land at `tests/fixtures/frozen-run/svb-replay-2023/` (the
  canonical dir, currently empty).
* **Canonical noise floor**: redo step 4 against
  `claude-opus-4-7`. Anthropic doesn't honor seed, so the variance source
  is internal batching — should be small but nonzero.
* **Seed propagation**: thread `seed` through `Prefab.run()` and
  `ConcordiaPersonaBuilder.__call__` so the harness can measure LLM-side
  stochasticity. ADR-worthy change because it touches the per-call
  contract.
* **Step 5 unblocked**: with DeepSeek cassettes committed, the
  `ReinsurerTreatyPricer` prompt-tuning loop can run end-to-end without
  API spend. The equivalence test against `deterministic_stub_personas`
  has not been written yet — it's the first deliverable of step 5.
