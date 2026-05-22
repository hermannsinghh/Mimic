# mimic-forecast — Agent Instructions

Frontier time-series adapters. Existing adapters (Chronos, FinBERT, Kronos, Moirai, TimesFM 2.5,
Bistro) stay. The 2026-frontier tier is added on top, not in place of.

## Build queue (Plan §3.2)

P0: FC-01 Toto 2.0, FC-02 Timer-S1, FC-04 keep existing adapters, FC-05 bench harness, FC-06 per-node forecast API.
P1: FC-03 TiRex.

## Hard rules

- Every adapter exposes the same interface: `forecast(node, horizon, quantiles)` returning a
  distribution. No bespoke per-adapter APIs.
- The bench harness (FC-05) emits a signed `badges/calibration.json` per release. A regression
  blocks merge.
- License is BSL 1.1 with 3-year Apache-2.0 conversion. Keep LICENSE, LICENSE-BSL,
  LICENSE-CHANGE-DATE, NOTICE in sync with the other BSL packages.
