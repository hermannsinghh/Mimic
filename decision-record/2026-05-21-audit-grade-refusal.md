# Audit-grade refusal: ScenarioRunner contract for non-deterministic personas

**Status:** accepted
**Date:** 2026-05-21
**Relates to:** Plan §0 (auditability invariant), §7.3 (frozen-run), §12 (policy)
**Forced by:** F-12 (Concordia integration) about to start; need contract locked
before any real LLM call lands in the persona-builder path.

## Context

`ScenarioRunner` (in-process scenario runner, the day-30 closer) takes a
`PersonaBuilder` that produces `Decision`s. Today the only builder is
`deterministic_stub_personas`, which doesn't call an LLM and is bit-reproducible.

The moment F-12 lands a `ConcordiaPersonaBuilder` calling Claude Opus or Sonnet,
the runner's determinism depends on the determinism of the LLM provider, which
depends on the frozen-run cache (Plan §7.3) being primed.

The risk: an operator runs without `MIMIC_FROZEN_RUN=1`, gets a manifest with a
`world_state_hash_final`, and doesn't realize it isn't reproducible. A regulator
later replays from inputs, gets a different hash, and the audit story collapses
publicly.

## Options

A. **Always emit a hash.** Runner ignores frozen-run state; manifest carries a
   flag like `audit_grade: bool` indicating whether reproducibility was actually
   guaranteed. Operators are expected to check the flag.

B. **Soft warning.** Runner emits the hash and logs a warning when
   non-deterministic-without-frozen-run. The manifest contains the hash and a
   warning field.

C. **Refuse by default, explicit downgrade.** Runner raises `FrozenRunRequired`
   when (a) the persona builder declares it may be non-deterministic AND (b)
   frozen-run is off AND (c) `audit_grade=True` (the default). The operator may
   pass `audit_grade=False` explicitly — in that mode the manifest is emitted
   but `world_state_hash_initial` and `world_state_hash_final` are `None`. No
   hash without earning it.

## Decision

**Option C.** Reasoning:

- A is the default-no-one-notices trap. The whole product is sold on the
  reproducibility guarantee; emitting a hash that's not reproducible is worse
  than not emitting one.
- B doesn't survive contact with production. Warnings get filtered.
- C makes the operator decide. If they want a hash, they prime frozen-run
  first; if they want a quick exploratory run, they explicitly downgrade.

## Contract

```python
class PersonaBuilder(Protocol):
    is_deterministic: bool  # True if the builder does not call any non-frozen LLM
    def __call__(self, scenario_ctx: dict) -> list[Decision]: ...

class FrozenRunRequired(RuntimeError):
    """Raised by ScenarioRunner when a non-deterministic persona_builder is
    used outside frozen-run mode without an explicit audit_grade=False opt-out."""

class ScenarioRunner:
    def __init__(self, *, ..., audit_grade: bool = True): ...
    def run(self, spec, *, ...) -> ScenarioRunManifest:
        if (audit_grade
            and not persona_builder.is_deterministic
            and not is_frozen_run()):
            raise FrozenRunRequired(...)
        # ...
        # if audit_grade=False, set hash fields to None in the manifest
```

`ScenarioRunManifest` schema:
- `world_state_hash_initial: str | None`
- `world_state_hash_final: str | None`
- Both required when `audit_grade=True`; both `None` when `audit_grade=False`.

Plain `Callable` persona_builders are treated as deterministic only if they
carry an `is_deterministic = True` attribute. The bare lambda case defaults to
non-deterministic — safer.

## Consequences

- `deterministic_stub_personas` carries `is_deterministic = True`. The day-30
  demo continues to work without changes.
- Once `ConcordiaPersonaBuilder` lands (F-12), it declares
  `is_deterministic = False`. Operators must:
  (a) Set `MIMIC_FROZEN_RUN=1` after warming the cache, OR
  (b) Pass `audit_grade=False` and accept no hash.
- The error message on `FrozenRunRequired` must list the two paths above
  explicitly. No silent failures.
- F-08 (frozen-run cache on S3) is now the gating dependency for F-12 to be
  usable in any audit-relevant setting.
