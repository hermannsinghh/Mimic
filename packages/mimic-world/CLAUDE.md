# mimic-world — Agent Instructions

Promote graph contagion from heuristic to provably-correct math, with the heuristic as a
*narrative* overlay.

## Build queue (Plan §3.3)

P0: W-01 Eisenberg-Noe clearing vector, W-02 DebtRank, W-03 demote current cascade.py to
`mimic.world.narrative`, W-04 FIBO-shaped network builder.
P1: W-05 combined stress propagation, W-06 treaty math (chainladder, gemact, rippy, lifelib).

## Hard rules

- `cascade.py` becomes `mimic.world.narrative` — a *descriptive* layer over EN + DebtRank, not
  the primary contagion engine.
- EN clearing vector ≈80 lines numpy + tests. Benchmark DebtRank against `neva` for behavioural
  correctness.
- Treaty math libraries (chainladder, gemact, rippy, lifelib) are adapted read-only — do not
  reimplement.
