---
name: mimic-connector-author
description: Adds a new data connector with required fetch/schema/health/rate_limit_policy interfaces and VCR fixtures
---

# Adding a Mimic data connector

Read this before adding anything under `packages/mimic-framework/mimic/framework/signal/sources/`.
The contract comes from Plan §4.1.

## Layout

```
mimic/framework/signal/sources/<name>/
├── __init__.py
├── client.py         # HTTP client + auth resolver (uses mimic-secrets, never hardcoded)
├── translate.py      # vendor format -> FIBO/canonical
├── schema.py         # schema() returns dict describing record shape
├── ratelimit.py      # rate_limit_policy()
└── tests/
    ├── fixtures/     # VCR cassettes — committed
    └── test_<name>.py
```

## Required public interface

```python
def fetch(query: str, since: datetime, until: datetime) -> Iterator[CanonicalRecord]: ...
def schema() -> dict: ...
def health() -> dict: ...                  # {"ok": bool, "latency_ms": int, "errors_24h": int}
def rate_limit_policy() -> RateLimitPolicy: ...
```

`CanonicalRecord` is a Pydantic model under `mimic.framework.schema` — bind to a FIBO IRI.

## Tier classification (Plan §4.1)

- **T0 (MVP):** SEC EDGAR, FRED.
- **T1 (month 1-3):** AM Best, LSEG, Bloomberg BLPAPI, NOAA, AIS, news (GDELT/RavenPack), OpenSanctions.
- **T2 (month 3-6):** Lloyd's RDS, NAIC SERFF, ACORD feeds.

## Authoring checklist

- [ ] No live HTTP calls in CI — every test plays back a VCR cassette under `tests/fixtures/`.
- [ ] Auth via env vars OR `mimic-secrets` resolver. Never hardcoded keys. Never commit
      `.env` files with real credentials.
- [ ] `rate_limit_policy()` returns a real limit, not None. Connectors without a known limit
      get a conservative 1 req/sec default.
- [ ] `fetch()` is an iterator — must support resumable streaming, not list-all.
- [ ] `health()` is safe to call on every workflow start; ≤500 ms p99.
- [ ] Records emitted by `fetch()` pass `mimic.framework.schema.translate.<name>_to_internal`.
- [ ] Round-trip test: native → canonical → native is bit-equivalent on the stable subset.
- [ ] Documented in `docs/connectors/<name>.md` with tier, auth model, sample record.

## Forbidden patterns

- `requests.get(...)` directly. Use `httpx.AsyncClient` configured by the framework.
- Storing Bloomberg keys client-side. Bloomberg auth happens against enterprise auth on the
  Bloomberg side; we never store the key.
- Sleeping inside `fetch()`. Backoff is handled by `tenacity` per the rate-limit policy.
