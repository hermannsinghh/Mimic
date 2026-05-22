# Architectural Decision Records (ADRs)

When in doubt — or before silently deviating from PLAN.md — write an ADR here.

## Format

```
decision-record/
└── YYYY-MM-DD-short-slug.md
```

```markdown
# Title

**Status:** proposed | accepted | superseded by <link>
**Date:** YYYY-MM-DD

## Context
What is the problem?

## Options
A, B, C — with trade-offs.

## Decision
Which option, and why.

## Consequences
What changes downstream. Which contracts (schema/hash/spec/routing) does this touch?
```

## When an ADR is required (per CLAUDE.md)

- Any change to canonical Decision/Outcome → schema major bump + ADR.
- Any change to `world_state_hash` computation → schema major bump + ADR.
- Any change to scenario spec apiVersion → ADR.
- Any change to routing systemic-score formula → minor bump + ADR.
- Any deviation from PLAN.md anti-goals or invariants → ADR.
