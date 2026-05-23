# Runner IRI resolution: walking up instrument_iri instead of splitting on "/"

**Status:** accepted
**Date:** 2026-05-22
**Relates to:** ADR `decision-record/2026-05-21-audit-grade-refusal.md`
(day-30 demo contract), Plan §5.1 (Decision schema), Plan §7.2
(world_state_hash), Plan §9.2 (prefab outputs).
**Forced by:** F-12 step 5 work surfaced that `ScenarioRunner` had been
silently orphaning **every** persona action since pre-2.0. The network
state hash was computed against an un-perturbed network in every run —
including the day-30 audit-grade demo. Fix needs to land before F-12
fully lands; this ADR locks the resolution rule.

## Context

`mimic_world.contagion.fibo_builder.from_fibo_dict` keys network nodes
by **full entity IRI** (`name=ent["iri"]` at l.76). e.g.
`"https://example.com/svb"`.

`Decision.instrument_iri` carries different shapes depending on the
prefab that emitted it:

* **Deterministic stubs** (`deterministic_stub_personas`) set
  `instrument_iri = entity["iri"]`. The instrument *is* the entity.
* **Mimic prefabs** (`ReinsurerTreatyPricer` and likely future ones)
  set `instrument_iri = "<entity_iri>/reinsurance-treaty"` via the
  `inputs_to_instrument_iri(entity, suffix)` helper. The instrument is
  a derived artifact rooted at the entity.

The pre-fix runner did:

```python
node_name = str(d.instrument_iri).split("/")[-1] if "/" in str(d.instrument_iri) else d.agent_did
```

For both shapes this extracts the trailing path segment — `"svb"` or
`"reinsurance-treaty"` — which never matches a node name keyed as
`"https://example.com/svb"`. Every action was then filtered out by

```python
actions = [a for a in actions if a.node_name in names]
```

Symptom that exposed the bug: F-12 step 5 found that the equivalence
test's heuristic and Concordia runners produced **identical
world_state_hash_final** despite emitting materially different Decisions.
The network just propagated unmodified in both cases.

## Options

A. **Add `Decision.target_iri`** field — schema major bump. Each
   prefab populates this with the network-relevant target IRI.
   Pro: explicit, robust. Con: schema change is expensive (per
   CLAUDE.md hard rule: "Never change `Decision`/`Outcome` without
   bumping the schema major version AND updating golden vectors").

B. **Walk up `instrument_iri` until a network node matches** — pure
   runner-level fix. The runner tries the full IRI, then the parent,
   then the grandparent, etc. Handles both the stub shape
   (`instrument_iri == entity_iri`) and the prefab shape
   (`instrument_iri == entity_iri/<suffix>`).

C. **Smarter mapping via `agent_did`** — the stub builder's `agent_did`
   contains the entity tail (`"did:web:stub.svb"`). The Concordia
   builder's does too. But the network is keyed by full IRI, not
   tail — we'd still need a path → entity map, which is what option B
   provides directly.

## Decision

**Option B.** Walk up the instrument IRI. Pure runner-level fix; no
schema change; no golden-vector refresh.

Implementation in `mimic.framework.scenario.runner._resolve_target_node`:

* Try `instrument_iri` directly.
* If not in the network, drop the trailing path segment (`rpartition("/")`)
  and try again.
* Stop at the scheme (`"https://host".rpartition("/")` yields a malformed
  parent of `"https:"`).
* Bounded to 8 levels of upward walking.

Returns `None` for orphans (no network node contains the instrument),
which the runner then filters out — same external behavior as before,
just that the filter now correctly catches *only* genuine orphans.

## Why not Option A

Per CLAUDE.md, schema changes are major-bump territory and require
refreshing `tests/determinism/golden/`. Adding `Decision.target_iri`
would:

1. Force a Decision schema major bump (current is v1).
2. Force re-recording every committed cassette (model_fingerprint
   depends on schema only indirectly, but every prefab's
   `_response_to_decision` would have to populate the new field — that's
   a code change in every prefab, which is a *prefab* change, which
   invalidates cassettes via the system_prompt fingerprint chain).
3. Force every external consumer of `Decision` (Hub clients, eval
   harness, signal pipeline) to handle the new field.

None of that is warranted to solve "runner doesn't know which entity
owns this instrument." The instrument-to-entity relationship is *already*
implicit in the IRI path; option B just teaches the runner to read it.

If we later need a target IRI that's *not* a path-prefix of the
instrument IRI (e.g. a Decision about a derivative whose underlying is
a different entity), we revisit. That's not a current use case.

## Consequences

* **Hash values change** in any audit-grade scenario run that emits
  persona actions. Previously every action was orphaned, so the network
  propagated unmodified; now actions actually perturb the network. The
  hash is still deterministic per (inputs, persona builder), so the
  day-30 demo's "two consecutive runs produce identical hashes" still
  holds — just the hash *value* is different from what previous runs
  produced. **No committed hash values are invalidated** (the golden
  vectors in `tests/determinism/golden/world_state_hash_v1.json` test
  the hash function with explicit inputs, not via a full scenario run).
* **`test_runner_e2e.py:51`** which asserts `initial != final` still
  passes — actually now for the right reason (persona-driven perturbation
  in addition to baseline EN propagation).
* **F-12 equivalence test** is unaffected (it compares Decision-level
  outputs, not network hashes).
* **A new regression test** in `tests/scenario/test_runner_e2e.py`
  pins the persona→network linkage: running with a builder that emits
  a non-trivial reinsure action must produce a different
  world_state_hash than running with `deterministic_stub_personas`.
* **Prefabs that emit `instrument_iri` paths NOT rooted at an entity IRI**
  (e.g. a Decision about a market-wide rate) won't resolve. That's the
  right behavior — those actions don't belong on any specific node and
  should be modeled as `market_state` perturbations, not entity actions.

## Open items

* If a future prefab needs cross-entity target semantics (Decision about
  entity X by reinsurer Y), reconsider option A. Currently no such case.
* The equivalence test's `_heuristic_reinsurer_pricer` baseline uses
  `instrument_iri = entity_iri + "/reinsurance-treaty"` — same shape as
  the prefab. Will resolve correctly with this fix.
