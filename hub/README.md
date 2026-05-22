# Mimic Hub

Scenario registry service. FastAPI + Postgres + OCI registry (Harbor/GHCR) + Sigstore + SLSA.

**License: AGPL-3.0.** The hub-client SDK is a separate Apache-2.0 package.

## Endpoints (Plan §3.4)

| Endpoint | Method | Purpose |
|---|---|---|
| `/publish` | POST | Author uploads a signed scenario artifact |
| `/search` | GET | Search by name, license, FIBO IRI, tier, calibration |
| `/scenarios/{id}` | GET | Fetch signed manifest |
| `/badges/{id}` | GET | Calibration badge for the scenario |
| `/attest` | POST | SLSA Level 3 provenance attestation |

## Run locally

```bash
cd hub
uvicorn app.main:app --reload
```

Postgres + Harbor are required for full publishing flow; see `infra/` for compose stack.
