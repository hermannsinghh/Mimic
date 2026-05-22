# Frozen-run cassettes

This directory holds the committed LLM-response cassettes that CI replays
via `FrozenRunProvider` instead of hitting a live LLM API.

## Layout

```
tests/fixtures/frozen-run/
├── README.md                          # this file
├── svb-replay-2023/                   # one subdir per scenario
│   └── <cache_key>.json               # one file per (model_fingerprint × messages) pair
├── 2008-gfc-bank-cascade/
└── ...
```

`<cache_key>` is `sha256(model_fingerprint || canonical_json(messages))` per
Plan §7.3 — the same key the production `FrozenRunProvider` computes.

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
