# Mimic Hub — Agent Instructions

The Hub is the scenario registry service: FastAPI + Postgres + OCI registry (Harbor/GHCR) +
Sigstore + SLSA provenance. **AGPL-3.0** licensed to prevent AWS-clone-and-sell.

## Build queue (Plan §3.4)

P0: H-01 FastAPI endpoints, H-02 OCI artifact backend, H-03 Sigstore Fulcio + Rekor.
P1: H-04 SLSA Level 3 provenance, H-05 eval-badge service.
P2: H-06 Verified Publisher badge, H-07 revenue-share metering (70/30 publisher/platform).

## Endpoints

- `POST /publish` — author uploads a signed scenario artifact
- `GET /search` — search scenarios by name, license, FIBO IRI, tier, calibration score
- `GET /scenarios/{id}` — fetch signed manifest
- `GET /badges/{id}` — published calibration badge

## Hard rules

- Hub-client SDK is a **separate** package, Apache-2.0 licensed. Do not bundle client code into
  this AGPL service.
- Every published scenario must be Sigstore-signed; Rekor transparency log entry required.
- Calibration badge is written by the Hub on publish — not author-supplied.
- "Verified Publisher" badge requires SOC 2 attestation upload (Plan §3.4 H-06).
