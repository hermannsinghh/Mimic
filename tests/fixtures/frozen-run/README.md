# Frozen-run cassettes

This directory holds the committed LLM-response cassettes that CI replays
via `FrozenRunProvider` instead of hitting a live LLM API.

## Layout

```
tests/fixtures/frozen-run/
├── README.md                          # this file
├── svb-replay-2023/                   # CANONICAL Anthropic baseline (audit-grade)
│   └── <cache_key>.json               # one file per (model_fingerprint × messages) pair
├── svb-replay-2023-deepseek/          # development cassettes against DeepSeek V3.2
│   └── <cache_key>.json               # NOT the audit baseline — see "Provider variants"
├── 2008-gfc-bank-cascade/
└── ...
```

`<cache_key>` is `sha256(model_fingerprint || canonical_json(messages))` per
Plan §7.3 — the same key the production `FrozenRunProvider` computes.

### Provider variants

The `<scenario>/` directory (no provider suffix) holds the audit-grade
canonical cassettes recorded against the Plan §4.2-named model for that
tier. Today that's Claude Opus 4.7 (see
[`decision-record/2026-05-22-anthropic-model-choice.md`](../../../decision-record/2026-05-22-anthropic-model-choice.md))
for T1 scenarios like svb-replay-2023.

`<scenario>-<provider>/` directories hold non-canonical fixtures recorded
against secondary providers. Useful for:

* **Forward progress** when the canonical provider's API key isn't
  available yet (DeepSeek covers F-12 step 5 prefab tightening without
  blocking on Anthropic procurement).
* **Cross-provider equivalence testing** — eventually F-11's calibration
  bench runs the same scenario across providers and reports per-provider
  noise floors.
* **Cost-tier sanity checks** — DeepSeek (T3) is 18× cheaper than Anthropic
  (T1) per Plan §4.2; the cross-provider Decision delta surfaces in
  `eval/harness/` once we have both sets.

A run against `<scenario>-deepseek/` cassettes is **never** audit-grade.
The `ScenarioRunner`'s hash is computed correctly, but the model that
produced the underlying decisions doesn't match the scenario's claimed
canonical model.

## How cassettes get created

**Never** edit a cassette by hand. They are produced exclusively by a recording
session using `RecordingProvider`:

```python
from mimic.framework.determinism import (
    LocalFSBackend, RecordingProvider,
)
from mimic.framework.scenario import run_scenario_e2e

# Wrap the live provider with RecordingProvider; everything is captured.
live = build_real_anthropic_provider(api_key=...)
fixture_dir = "tests/fixtures/frozen-run/svb-replay-2023"
recorder = RecordingProvider(live, LocalFSBackend(fixture_dir))

# Run the scenario once with the recording provider in the LLM path.
run_scenario_e2e(
    "scenarios/svb-replay-2023",
    liability_network=...,
    # ConcordiaPersonaBuilder injects `recorder` here
    persona_builder=ConcordiaPersonaBuilder(provider=recorder, ...),
)
# fixture_dir now contains every (key.json) the run produced. Commit them.
```

## When to re-record

- Anthropic announces a model deprecation or version bump that touches the
  pinned `model_version` in the affected adapter.
- A prefab's `system_prompt` changes (which moves the `model_fingerprint`).
- The scenario inputs change in a way that touches the message list (e.g. new
  evidence_iri added to the retrieved context).

Every other case: **do not re-record**. Re-recording is the equivalent of
hand-editing the test — it makes the test pass without telling you what
broke. If a cassette miss surfaces in CI as `FrozenRunCacheMiss`, that's
diagnostic information; chase it before deciding to re-record.

## Why this matters

Per `decision-record/2026-05-21-audit-grade-refusal.md`: a non-deterministic
persona builder + no frozen-run cache = `ScenarioRunner` refuses to emit a
hash. The cassettes here are what put CI into "frozen-run primed" mode so the
e2e equivalence test (per `2026-05-21-runner-equivalence-criterion.md`) can
run deterministically without live API credentials.

If a contributor adds a new scenario or a new prefab and forgets to commit
the cassettes, the e2e CI job fails loudly with `FrozenRunCacheMiss`. That's
the intended behavior — better than silently calling Anthropic in CI.
