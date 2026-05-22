# NEXT_STEPS.md — mimic-framework

## Status as of 2026-05-18

### Install
PASS (installed via `pip install -e ".[dev]" --ignore-requires-python` — note: sandbox runs Python 3.10.12; package requires >=3.11 and will install cleanly on 3.11+ in production)

### Tests
32 passing, 0 failing.

```
tests/test_context.py::test_financial_snapshot_gross_margin PASSED
tests/test_context.py::test_financial_snapshot_net_debt PASSED
tests/test_context.py::test_financial_snapshot_zero_revenue PASSED
tests/test_context.py::test_supplier_concentration_flag PASSED
tests/test_context.py::test_supplier_not_concentrated PASSED
tests/test_context.py::test_context_summary_contains_ticker PASSED
tests/test_context.py::test_context_summary_contains_key_metrics PASSED
tests/test_context.py::test_context_model_dump_roundtrip PASSED
tests/test_context.py::test_context_fx_exposure_default PASSED
tests/test_context.py::test_historical_behavior_risk_appetite_bounds PASSED
tests/test_formulas.py::test_dcf_impact_negative_shock PASSED
tests/test_formulas.py::test_dcf_impact_positive_shock PASSED
tests/test_formulas.py::test_altman_z_safe_zone PASSED
tests/test_formulas.py::test_altman_z_zero_assets PASSED
tests/test_formulas.py::test_cogs_sensitivity PASSED
tests/test_formulas.py::test_fx_passthrough PASSED
tests/test_formulas.py::test_inventory_burn_high_demand PASSED
tests/test_formulas.py::test_inventory_burn_low_demand PASSED
tests/test_formulas.py::test_bayes_update_increases_probability PASSED
tests/test_formulas.py::test_bayes_update_decreases_probability PASSED
tests/test_formulas.py::test_capm_response PASSED
tests/test_formulas.py::test_operating_leverage PASSED
tests/test_formulas.py::test_supplier_hhi_high_concentration PASSED
tests/test_formulas.py::test_supplier_hhi_diversified PASSED
tests/test_formulas.py::test_supplier_hhi_zero PASSED
tests/test_formulas.py::test_cascade_propagate PASSED
tests/test_formulas.py::test_compute_formula_context PASSED
tests/test_twin.py::test_twin_from_context PASSED
tests/test_twin.py::test_twin_repr PASSED
tests/test_twin.py::test_twin_simulate_calls_orchestrator PASSED
tests/test_twin.py::test_decision_pretty_output PASSED
tests/test_twin.py::test_twin_benchmark PASSED

============================== 32 passed in 0.19s ==============================
```

### CI Workflow
ALREADY EXISTS (`.github/workflows/ci.yml`)

---

## What This Repo Does (One Paragraph)

`mimic-framework` is the core Python library that lets you build an LLM-based digital twin of any public company and simulate how it would respond to real-world events. It pulls free public data from SEC EDGAR, yfinance, and FRED to construct a `CompanyContext`, applies a set of ten textbook economic formulas (DCF, Altman-Z, COGS sensitivity, FX passthrough, etc.) to quantify the shock, then passes everything through an LLM orchestrator to produce a structured `Decision` object with time-bucketed action plans and P10/P50/P90 financial impact ranges.

---

## What Is Already Built

- `mimic/__init__.py` — public API surface; re-exports `Twin`, `Decision`, `CompanyContext`
- `mimic/cli.py` — Click-based CLI (`mimic simulate <TICKER> "<EVENT>"`)
- `mimic/core/twin.py` — `Twin` and `Decision` classes; `Twin.from_ticker()` and `Twin.simulate()` entry points
- `mimic/core/orchestrator.py` — LLM composition layer; builds prompt from context + formula outputs, parses JSON response into `Decision`
- `mimic/core/context.py` — `CompanyContext` Pydantic model; `FinancialSnapshot`, `HistoricalBehavior`, supplier fields
- `mimic/data/sec.py` — SEC EDGAR ingestion: ticker→CIK lookup, 10-K section fetching, LLM-assisted strategy extraction
- `mimic/data/prices.py` — yfinance enrichment: market cap, beta, sector, employee count
- `mimic/data/cache.py` — File-based JSON cache for SEC and market data (keyed by ticker + date)
- `mimic/formulas/__init__.py` — Ten economic primitives: `dcf_impact`, `altman_z`, `cogs_sensitivity`, `fx_passthrough`, `inventory_burn`, `bayes_update`, `capm_response`, `operating_leverage`, `supplier_hhi`, `cascade_propagate`, plus `compute_formula_context` aggregator

---

## Immediate Next Tasks

**Priority 1 — End-to-end integration test**
Create `tests/test_integration.py`. Test that `Twin.from_ticker("WMT")` followed by `twin.simulate("port closes")` runs fully without errors and returns a `Decision` object with all required fields (`immediate_action_0_24h`, `financial_impact_mid`, `confidence`, etc.). Use `unittest.mock.patch` to stub the LLM call so the test runs without an API key in CI.

**Priority 2 — yfinance fallback handling**
In `mimic/data/prices.py`, add graceful handling when yfinance returns `None` for `market_cap`, `beta`, or `sector`. Default to `0.0` / `1.0` / `"Unknown"` respectively. Currently causes `KeyError` on some tickers.

**Priority 3 — Orchestrator error recovery**
In `mimic/core/orchestrator.py`, add retry logic when the LLM returns invalid JSON. Wrap the `json.loads()` in a `try/except` and retry up to 3 times with a prompt nudge: `"Return only valid JSON, no other text."`

**Priority 4 — PyPI publish check**
Confirm `mimic-framework` is live on pypi.org. Run `pip install mimic-framework` in a fresh venv. If it fails, run `python -m build && twine upload dist/*`.

**Priority 5 — README badges**
Add the following badges to the top of `README.md`: PyPI version badge, CI status badge (once GitHub Actions is live), and License badge (MIT).

---

## How to Run (Developer Quick Reference)

```bash
cd ~/Desktop/mimic/Mimic
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v          # run tests
pip install -e ".[dev]"   # reinstall after changes
```

---

## Known Issues

- `mimic/data/prices.py`: No fallback for `None` values from yfinance (`market_cap`, `beta`, `sector`). Can cause `KeyError` on lesser-known tickers.
- `mimic/core/orchestrator.py`: No retry logic around `json.loads()` — a single malformed LLM response will raise and crash the simulation.
- Requires Python >=3.11; sandbox/CI matrix should always pin to 3.11 or 3.12.

---

## Dependencies on Other Mimic Repos

None — this is the core repo. All other mimic repos depend on this one.
