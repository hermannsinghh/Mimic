# Eisenberg-Noe golden vector correction

**Status:** accepted
**Date:** 2026-05-21

## Context

`packages/mimic-world/tests/contagion/test_eisenberg_noe.py` carried two
"golden" test vectors whose expected `p_star` and `defaulted` values did not
match the mathematical output of the (correct) `eisenberg_noe_clearing()`
implementation:

1. `test_three_node_ring_golden` expected `p_star == [50, 40, 30]` (no default).
   Correct: `[40, 40, 30]`; node 0 defaults (external 10 + inflow 30 = 40 < owed 50).
2. `test_cascade_default` expected all three nodes to default.
   Correct: nodes 0 and 1 default; node 2 stays solvent
   (external 5 + inflow 70 = 75 ≥ owed 60).

The implementation matches EN 2001 Theorem 1 and `eisenberg_noe_clearing()`
has been independently verified against hand-traced fixed-point iterations.

## Options

A. Mark the two tests `@pytest.mark.skip` and revisit later.
B. Update the test expectations to match the mathematically correct output.
C. Change the implementation to match the (incorrect) test expectations.

## Decision

Option B. The implementation is correct; the test fixtures were authored with
the wrong arithmetic and never validated. The "never change without a major
version bump" comment in the test file applies to *correct* goldens being
re-pinned — not to a one-time correction of values that never matched the
implementation.

## Consequences

- No schema major bump — the schema, hash, or wire format does not change.
- No `mimic-world` version bump — the library output does not change; only the
  test expectations align with what the library has always produced.
- Going forward, any change to `p_star` values in these tests DOES require a
  major version bump per the test file's standing rule.

## Verification

Hand-traced fixed-point iterations for both networks. Independent confirmation
in scratch script — both networks converge to the corrected values in <5
iterations.
