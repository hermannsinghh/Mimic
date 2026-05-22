# NEXT_STEPS.md — mimic-forecast

## Status as of 2026-05-18

### Install
PASS (`pip install -e ".[dev]"` succeeds cleanly on Python 3.10+)

### Tests
35 passing, 1 failing.

```
tests/test_base.py::test_dummy_forecast_shape PASSED
tests/test_base.py::test_future_index_starts_after_series PASSED
tests/test_base.py::test_summary_keys PASSED
tests/test_base.py::test_validate_series_rejects_short PASSED
tests/test_base.py::test_validate_series_rejects_non_datetime PASSED
tests/test_base.py::test_forecast_result_quantile_ordering PASSED
tests/test_benchmarks.py::test_persistence_beats_zero PASSED
tests/test_benchmarks.py::test_metric_options PASSED
tests/test_benchmarks.py::test_invalid_metric PASSED
tests/test_benchmarks.py::test_series_too_short_raises PASSED
tests/test_benchmarks.py::test_forecasts_accessible_in_result PASSED
tests/test_data.py::test_pull_series_yfinance_success PASSED
tests/test_data.py::test_pull_series_yfinance_empty_raises PASSED
tests/test_data.py::test_pull_series_fred_missing_key_raises PASSED
tests/test_data.py::test_pull_series_fred_success FAILED   ← ModuleNotFoundError: No module named 'fredapi'
tests/test_data.py::test_looks_like_fred PASSED
tests/test_ensemble.py::test_equal_weight_average PASSED
tests/test_ensemble.py::test_custom_weights PASSED
tests/test_ensemble.py::test_ensemble_name_contains_members PASSED
tests/test_ensemble.py::test_empty_models_raises PASSED
tests/test_ensemble.py::test_weight_mismatch_raises PASSED
tests/test_ensemble.py::test_single_model_ensemble PASSED
tests/test_ensemble.py::test_ensemble_quantiles_present PASSED
tests/test_ensemble.py::test_failing_member_is_skipped PASSED
tests/test_integration.py::test_forecast_for_event_energy PASSED
tests/test_integration.py::test_auto_forecaster_delegates PASSED
tests/test_integration.py::test_get_forecaster_returns_auto_forecaster PASSED
tests/test_registry.py::test_detect_event_type_energy PASSED
tests/test_registry.py::test_detect_event_type_supply_chain PASSED
tests/test_registry.py::test_detect_event_type_macro PASSED
tests/test_registry.py::test_detect_event_type_geopolitical PASSED
tests/test_registry.py::test_series_for_event_energy PASSED
tests/test_registry.py::test_series_for_event_macro PASSED
tests/test_registry.py::test_series_for_event_unknown_returns_empty PASSED
tests/test_registry.py::test_series_registry_has_best_model PASSED
tests/test_registry.py::test_get_adapter_invalid_name PASSED

========================= 1 failed, 35 passed in 0.34s =========================
```

Failure detail: `test_pull_series_fred_success` patches `fredapi.Fred` but `fredapi` is not installed (it's not in `[dev]` extras). Fix: add `fredapi` to the `[dev]` extras in `pyproject.toml`, or mark the test with `pytest.importorskip("fredapi")`.

### CI Workflow
ADDED (`.github/workflows/ci.yml`)

---

## What This Repo Does (One Paragraph)

`mimic-forecast` is the foundation model adapter layer that plugs time-series forecasting into the mimic ecosystem. It defines a common `ForecasterAdapter` interface (in `base.py`) so that any forecasting model — TimesFM, Chronos, Moirai, Kronos, or a custom one — can be swapped in with a single line. It includes a model registry that auto-selects the best adapter for a given event type (energy vs. macro vs. supply chain), a weighted `EnsembleAdapter` that combines multiple models, data connectors to pull historical series from FRED and yfinance, and a `mimic_plugin.py` shim that lets `mimic.Twin` delegate forecast context generation to this package with zero hard dependency.

---

## What Is Already Built

- `mimic_forecast/__init__.py` — public API; re-exports `TimesFMAdapter`, `ChronosAdapter`, `EnsembleAdapter`, `ForecastResult`, `get_forecaster`
- `mimic_forecast/base.py` — `ForecasterAdapter` ABC and `ForecastResult` Pydantic model (`.point`, `.quantiles`, `.summary()`)
- `mimic_forecast/registry.py` — model registry: event-type detection, `get_adapter(name)`, `get_forecaster(event_type)` auto-selector, `SeriesRegistry` mapping event types to FRED/yfinance series IDs
- `mimic_forecast/ensemble.py` — `EnsembleAdapter`: weighted combination of multiple adapters, skips failing members gracefully
- `mimic_forecast/benchmarks.py` — in-process model comparison: persistence baseline, MAPE/SMAPE/CRPS metrics, `BenchmarkResult`
- `mimic_forecast/data/series.py` — `pull_series(ticker_or_fred_id, start, end)` — unified fetcher for FRED and yfinance series
- `mimic_forecast/data/covariates.py` — covariate matrix builder for multivariate adapters
- `mimic_forecast/adapters/timesfm.py` — TimesFM 2.0 adapter (`google/timesfm-2.0-500m-pytorch`), lazy import, HuggingFace model cache at `~/.mimic/models/timesfm/`
- `mimic_forecast/adapters/chronos.py` — Chronos adapter (`amazon/chronos-t5-large`), same interface as TimesFM
- `mimic_forecast/adapters/moirai.py` — Moirai adapter (Salesforce MOIRAI-large)
- `mimic_forecast/adapters/kronos.py` — Kronos adapter stub
- `mimic_forecast/adapters/bistro.py` — Bistro adapter stub
- `mimic_forecast/adapters/finbert.py` — FinBERT sentiment adapter
- `mimic_forecast/integration/mimic_plugin.py` — plugin shim: `get_forecaster()` and `forecast_for_event()` called by `mimic.Twin.use_forecaster()`

---

## Immediate Next Tasks

**Priority 1 — Fix failing FRED test**
Add `fredapi` to the `[dev]` extras in `pyproject.toml` so `test_pull_series_fred_success` passes in CI. Alternatively, add `pytest.importorskip("fredapi")` at the top of that test. Either approach is a one-line fix; adding it to `[dev]` is preferred for completeness.

**Priority 2 — TimesFMAdapter smoke test**
In `examples/01_timesfm_quickstart.py`, confirm the adapter:
- Downloads the model from HuggingFace on first run
- Caches it to `~/.mimic/models/timesfm/`
- Returns a `ForecastResult` with `.point`, `.quantiles[0.1]`, `.quantiles[0.9]`
If `torch` is not available, the adapter must raise `ImportError` with message: `"Install mimic-forecast[timesfm] to use TimesFMAdapter"`. Write a test for this guard in `tests/test_adapters.py`.

**Priority 3 — ChronosAdapter full test parity**
Parametrize the TimesFM unit tests to also cover `ChronosAdapter` — both should pass the same interface contract. Add `@pytest.mark.parametrize("adapter_class", [TimesFMAdapter, ChronosAdapter])` to `tests/test_adapters.py`.

**Priority 4 — FRED data connector test**
In `tests/test_data.py`, add `test_fetch_fred_series_wti` and `test_fetch_fred_series_fedfunds`. Use `responses` or `unittest.mock` to mock the FRED HTTP call; confirm returned `pd.Series` has `DatetimeIndex` and float values.

**Priority 5 — mimic plugin integration test**
In `tests/test_integration.py`, add `test_twin_use_forecaster` that mocks `mimic.Twin` (to avoid the LLM call) and confirms that `twin.use_forecaster(TimesFMAdapter())` populates `forecast_context` in the decision dict.

**Priority 6 — PyPI publish**
Package name: `mimic-forecast`. Extras: `mimic-forecast[timesfm]`, `mimic-forecast[chronos]`, `mimic-forecast[all]`. Run `python -m build && twine upload dist/*`.

---

## How to Run (Developer Quick Reference)

```bash
cd ~/Desktop/mimic/Mimic-forecast
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v          # run tests
pip install -e ".[dev]"   # reinstall after changes
```

---

## Known Issues

- `test_pull_series_fred_success` fails with `ModuleNotFoundError: No module named 'fredapi'` — `fredapi` is not listed in `[dev]` extras. One-line fix in `pyproject.toml`.
- The `ChronosAdapter`, `MoiraiAdapter`, `KronosAdapter`, and `BistroAdapter` are likely stubs — need smoke tests to confirm they implement the full `ForecasterAdapter` interface.
- The `benchmarks/` directory at repo root contains only `model_comparison.py` and no `__init__.py`; it is separate from the `mimic_forecast/benchmarks.py` module and may cause import confusion.

---

## Dependencies on Other Mimic Repos

Optional — `mimic_forecast/integration/mimic_plugin.py` is designed to be called by `mimic-framework`'s `Twin.use_forecaster()`, but the import is guarded so this package has no hard dependency on `mimic-framework`. When used together, `mimic-framework` must be installed separately.
