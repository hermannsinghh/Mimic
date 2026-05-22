---
name: mimic-prefab-author
description: Adds a Concordia prefab + LangGraph reasoning graph + BAML schema + calibration test
---

# Adding a Mimic agent prefab

Read this before adding anything under
`packages/mimic-framework/mimic/framework/agents/prefabs/`. Contract: Plan §9.

## Existing prefabs (Plan §9.2)

`ReinsurerTreatyPricer` (T1), `BankTreasuryALM` (T1), `HedgeFundRiskOfficer` (T2),
`CentralBankLiquidityProvider` (T1), `RatingAgencyAnalyst` (T2), `BrokerCedentAdvisor` (T2).

## Layout

```
mimic/framework/agents/
├── prefabs/<prefab_name>/
│   ├── __init__.py
│   ├── persona.py         # Concordia persona builder
│   ├── graph.py           # LangGraph reasoning graph
│   └── tests/
│       └── test_<name>.py # calibration against historical episodes
└── baml/
    └── <prefab_name>.baml  # strict output schema
```

## Authoring checklist

- [ ] Concordia persona built from FIBO-shaped inputs only. No raw 10-K text bypassing the
      schema layer.
- [ ] LangGraph reasoning graph emits a `mimic.framework.schema.Decision` — never free text.
- [ ] BAML schema in `agents/baml/<prefab_name>.baml` enforces the structured output.
- [ ] Tier assignment via `mimic.framework.routing.assign_tier`. Do not bypass routing.
- [ ] Every `Decision` carries `model_fingerprint`, `policy_version`, and a `rationale_chain`
      whose every `RationaleStep` has an `evidence_iri` resolvable in the canonical schema.
- [ ] Calibration test runs against ≥3 historical episodes from
      `eval/historical/` and meets directional accuracy ≥0.7.
- [ ] Calibration badge published to Mimic Hub.

## A prefab without a published calibration badge MUST NOT ship.

## Things to refuse

- Prefabs that emit Markdown-formatted reasoning. The output is a structured `Decision`.
- Prefabs that hardcode a tier (e.g. `tier = "T1"`). Tier comes from `assign_tier(entity)`.
- Prefabs that call an LLM directly. All calls go through `mimic.framework.routing.LLMProvider`.

## Declaring `is_deterministic` on a `PersonaBuilder`

Per [decision-record/2026-05-21-audit-grade-refusal.md](../../decision-record/2026-05-21-audit-grade-refusal.md),
`ScenarioRunner` refuses to emit a `world_state_hash` when the configured
`persona_builder` is non-deterministic and `MIMIC_FROZEN_RUN` is off. A builder
is treated as deterministic only if it carries `is_deterministic = True`. The
runner trusts this attribute — there is no runtime determinism probe in v0.2.

**Do not set `is_deterministic = True` unless every one of these is true.** If
any are violated, leave the attribute unset or set it to `False`.

Disqualifying patterns:

- Calls any LLM provider that isn't wrapped in `FrozenRunProvider` with a
  primed cache. (Real prefabs always disqualify here — set `False`.)
- Uses `time.time()`, `time.monotonic()`, `datetime.now()`, `datetime.utcnow()`,
  or any other wall-clock reader. Use `workflow.now()` inside Temporal
  workflows or a fixed timestamp passed in via `scenario_ctx`.
- Uses `uuid.uuid4()` or `os.urandom()` for any value that ends up in a
  Decision field. Use seeded UUIDv5 derived from the scenario `SeedManifest`.
- Uses the global `random` module, `numpy.random.seed()` (global), or
  `torch.manual_seed()` without `torch.use_deterministic_algorithms(True)`.
  Use `numpy.random.Generator` with a seed derived from `SeedManifest.per_agent_seed(agent_did)`.
- Iterates over a `set` or unsorted `dict` and lets the order affect the
  output. Sort explicitly.
- Calls any HTTP API that isn't routed through a fixture-backed transport
  (see `.claude/skills/mimic-connector-author.md`).
- Reads from `os.environ` for anything beyond the canonical seed/config
  variables (`MIMIC_FROZEN_RUN`, `MIMIC_CONFIG`).
- Uses Python `hash()` on strings (it's salted across processes since 3.3).
  Use `hashlib.sha256` instead.

If you can't satisfy all of these, set `is_deterministic = False` and operate
in frozen-run mode for any audit-relevant run.

Future work (P2): a `DeterminismProbe` pytest fixture that runs the builder
twice with the same `SeedManifest` and asserts byte-equal Decisions. Not a
proof, but cheap regression net.

## Expect cassette churn during prefab tuning

When you're iterating on a prefab's `system_prompt` to land it inside the
equivalence thresholds (see ADR
[2026-05-21-runner-equivalence-criterion.md](../../decision-record/2026-05-21-runner-equivalence-criterion.md)),
every change to the prompt invalidates every existing frozen-run cassette
for that prefab. `system_prompt` is an input to `model_fingerprint` (Plan
§6.2), which is the cache-key seed (Plan §7.3) — so a one-character prompt
edit changes the key for every conversation.

You will see `FrozenRunCacheMiss` fire across the board the first time this
happens. **The infrastructure is not broken.** That's the recording layer
working exactly as designed: the cassette tells you it was recorded against
a different `system_prompt_sha256` (see the `_recording_metadata` sidecar
in the JSON file).

Procedure when this happens:

1. Confirm the prompt change was intentional. If it wasn't, revert.
2. If it was, re-record the cassettes against the new prompt:
   ```
   recorder = RecordingProvider(real_provider, LocalFSBackend('tests/fixtures/frozen-run/<scenario>'))
   run_scenario_e2e(..., persona_builder=ConcordiaPersonaBuilder(provider=recorder, ...))
   ```
3. Commit the new cassettes. Note the system_prompt change in the commit
   message — `_recording_metadata.system_prompt_sha256` moves and the diff
   makes that explicit.
4. CI replays against the new cassettes.

The signal-to-noise discipline matters: cassettes get re-recorded only on
intentional prefab changes, never because "the tests are failing." If you
catch yourself re-recording to make a red CI green without changing the
prefab, **stop** — that's the equivalence test telling you something real,
and re-recording would hide it.
