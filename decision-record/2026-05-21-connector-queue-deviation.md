# Connector queue: NOAA + GDELT before AM Best + LSEG

**Status:** accepted
**Date:** 2026-05-21

## Context

Plan §4.1 orders the Tier-1 connector queue around the lighthouse vertical
(reinsurance treaty pricing). The most lighthouse-relevant T1 connectors are
AM Best (insurance ratings) and LSEG (reference data + ratings). The plan
expects these to land first inside the T1 month-1-to-3 window.

We landed NOAA (Tier-1, weather/cat-risk) and GDELT (Tier-1, news) first.

## Why

Both AM Best and LSEG require paid licenses that we cannot self-obtain.
Per Plan §4.1, AM Best "needs license — design partner reinsurer can grant
access." Without a signed lighthouse, we have no procurement path.

NOAA and GDELT are free, have stable public schemas, and have direct uses:
- NOAA feeds parametric cat-risk events into `cyber-cat-2026`-style
  scenarios, plus the broader catastrophe modelling layer (W-06).
- GDELT feeds the signal pipeline retriever (F-10) for any scenario.

Both also let us validate the `Connector` ABC (Plan §4.1) and the
VCR-fixture testing discipline before we get the live AM Best schema.

## Options considered

A. Build AM Best with a stub schema and rewrite when access lands.
B. Wait on AM Best until lighthouse access is granted.
C. Land the free T1 connectors first, queue AM Best for the week the
   lighthouse contract is signed.

## Decision

Option C. The free connectors don't block on procurement; AM Best does.
Building C first costs nothing for the eventual A path and gives us
working T1 examples for partners to point at.

## Consequences

- AM Best connector lands within 1 week of design-partner contract signing,
  not before. Auth scaffolding (env-var resolution, rate-limit policy stub)
  should be drafted now so only the schema-mapping needs to follow.
- LSEG follows the same pattern — drafted scaffolding now, live integration
  on procurement.
- Plan §4.1 queue ordering is unchanged for future planning; this is a
  one-time pragmatic deviation, not a permanent re-prioritisation.

## Open items

- Draft AM Best auth + rate-limit scaffolding (just the `Connector` skeleton)
  so the "land in 1 week" promise is real.
