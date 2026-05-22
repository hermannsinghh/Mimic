# concordia_runtime — F-12 glue

This package is the bridge between:

* **`ScenarioRunner.persona_builder`** (the audit-grade refusal contract — ADR
  `decision-record/2026-05-21-audit-grade-refusal.md`); and
* **`Prefab.run(entity, inputs, agent_did)`** (Plan §9.2 domain prefabs).

`ConcordiaPersonaBuilder(prefab, llm_provider)` wires a DeepMind Concordia
agent into the persona slot:

```
scenario_ctx
  └── for each entity:
        ├── build a fresh Concordia EntityAgent
        ├── agent.observe(<rendered event>)
        ├── reasoning = agent.act(ActionSpec(FREE))     ← LLM provider used here
        ├── inputs = {"concordia_reasoning": reasoning, …entity facts}
        └── decision = prefab.run(entity, inputs, agent_did)   ← LLM provider via cascade
```

The builder declares `is_deterministic = False`. ``ScenarioRunner`` therefore
refuses to emit a hash unless either:

1. `MIMIC_FROZEN_RUN=1` (with primed cassettes), or
2. `audit_grade=False` is passed explicitly (manifest emits
   `world_state_hash_*=None`).

## Wrapper boundary

All Concordia access goes through `mimic_concordia.*`. The two source files
in this directory are checked by
`tests/agents/test_concordia_runtime.py::test_imports_route_through_mimic_concordia`
to ensure no `import concordia` or `from concordia` line creeps in. The
single swap point promised by ADR
`decision-record/2026-05-22-concordia-vendoring-strategy.md` is enforced by
that grep.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Public exports |
| `builder.py` | `ConcordiaPersonaBuilder` orchestrator |
| `language_model.py` | `MimicProviderAsConcordiaLM`: `LLMProvider` → Concordia `LanguageModel` |
| `embedder.py` | `SHA256UnitEmbedder` — deterministic stub for tests / noise-floor runs |

## `DEFAULT_SYSTEM_PROMPT`

The LM adapter uses a stable, version-pinned `DEFAULT_SYSTEM_PROMPT`. Changing
it invalidates every recorded cassette because `model_fingerprint`
(`provider | model | version | system_prompt | temperature | tool_schema`)
folds the system prompt in (Plan §4.2). That is the design — see
`.claude/skills/mimic-prefab-author.md` ("Expect cassette churn"). Treat any
edit to that constant as a deliberate, scenario-wide cassette refresh.

## Inputs passed to the Mimic prefab

Every prefab sees the same `inputs` dict from this builder:

```python
{
    "concordia_reasoning": "<the agent's act() output>",
    "entity_name":         "<entity['name']>",
    "entity_iri":          "<entity['iri']>",
    "event":               <event dict from scenario_ctx>,
    "scope":               <scope dict from scenario_ctx>,
    # best-effort prefab-friendly summaries:
    "treaty_summary":      "<json of cedent + event + reasoning excerpt>",
    "cat_model":           "<event.cat_model if present>",
    "loss_ratio":          "<entity.loss_ratio if present>",
}
```

Prefabs ignore keys they don't understand. F-12 step 5 will retune
`ReinsurerTreatyPricer._build_messages` to consume `concordia_reasoning`
directly — that's the prefab-tightening pass.

## Per-entity isolation

Each entity gets a fresh `AssociativeMemoryBank` and a fresh Concordia agent.
No cross-contamination of memory between entities. That keeps the cassette
keys per-entity stable and the noise-floor harness meaningful.
