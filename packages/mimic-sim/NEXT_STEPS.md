# NEXT_STEPS.md — mimic-sim

## Status as of 2026-05-18

### Install
PASS (`pip install -e ".[dev]"` succeeds cleanly on Python 3.10+)

### Tests
49 passing, 0 failing.

```
tests/test_parameter_space.py::TestDistribution::test_uniform_bounds PASSED
tests/test_parameter_space.py::TestDistribution::test_normal_mean PASSED
tests/test_parameter_space.py::TestDistribution::test_lognormal_positive PASSED
tests/test_parameter_space.py::TestDistribution::test_triangular_mode PASSED
tests/test_parameter_space.py::TestDistribution::test_empirical_sampling PASSED
tests/test_parameter_space.py::TestDistribution::test_constant PASSED
tests/test_parameter_space.py::TestDistribution::test_single_sample PASSED
tests/test_parameter_space.py::TestParameterSpace::test_sample_returns_sampled_params PASSED
tests/test_parameter_space.py::TestParameterSpace::test_severity_in_range PASSED
tests/test_parameter_space.py::TestParameterSpace::test_duration_positive PASSED
tests/test_parameter_space.py::TestParameterSpace::test_macro_keys_present PASSED
tests/test_parameter_space.py::TestParameterSpace::test_intervention_rate PASSED
tests/test_parameter_space.py::TestParameterSpace::test_reproducibility PASSED
tests/test_simulation.py::TestSimulationSetup::test_mode_tier2_not_implemented PASSED
tests/test_simulation.py::TestSimulationSetup::test_mode_tier1_not_implemented PASSED
tests/test_simulation.py::TestSimulationSetup::test_unknown_mode PASSED
tests/test_simulation.py::TestTier3Run::test_returns_simulation_result PASSED
tests/test_simulation.py::TestTier3Run::test_n_runs_correct PASSED
tests/test_simulation.py::TestTier3Run::test_tickers_present PASSED
tests/test_simulation.py::TestTier3Run::test_impacts_are_negative PASSED
tests/test_simulation.py::TestTier3Run::test_reproducibility PASSED
tests/test_simulation.py::TestSimulationResult::test_percentile_ordering PASSED
tests/test_simulation.py::TestSimulationResult::test_var_worse_than_mean PASSED
tests/test_simulation.py::TestSimulationResult::test_cvar_worse_than_var PASSED
tests/test_simulation.py::TestSimulationResult::test_correlation_matrix_shape PASSED
tests/test_simulation.py::TestSimulationResult::test_correlation_diagonal_ones PASSED
tests/test_simulation.py::TestSimulationResult::test_tail_coincidence_between_zero_and_one PASSED
tests/test_simulation.py::TestSimulationResult::test_sensitivity_sums_to_one PASSED
tests/test_simulation.py::TestSimulationResult::test_worst_runs_count PASSED
tests/test_simulation.py::TestSimulationResult::test_best_runs_better_than_worst PASSED
tests/test_simulation.py::TestSimulationResult::test_median_run_exists PASSED
tests/test_simulation.py::TestSimulationResult::test_summary_dataframe PASSED
tests/test_simulation.py::TestSimulationResult::test_describe_keys PASSED
tests/test_simulation.py::TestSimulationResult::test_unknown_ticker_raises PASSED
tests/test_simulation.py::TestSimulationResult::test_time_series_shape PASSED
tests/test_tier3_formulas.py::TestBaseRevenueImpact::test_higher_severity_higher_impact PASSED
tests/test_tier3_formulas.py::TestBaseRevenueImpact::test_longer_duration_higher_impact PASSED
tests/test_tier3_formulas.py::TestBaseRevenueImpact::test_impact_bounded PASSED
tests/test_tier3_formulas.py::TestMacroImpact::test_high_oil_increases_fedex_impact PASSED
tests/test_tier3_formulas.py::TestMacroImpact::test_baseline_macro_near_zero PASSED
tests/test_tier3_formulas.py::TestInterventionDampening::test_intervention_reduces_impact PASSED
tests/test_tier3_formulas.py::TestInterventionDampening::test_no_intervention_is_one PASSED
tests/test_tier3_formulas.py::TestSimulateCompany::test_financial_impact_negative PASSED
tests/test_tier3_formulas.py::TestSimulateCompany::test_outcome_has_action PASSED
tests/test_tier3_formulas.py::TestSimulateCompany::test_recovery_time_positive PASSED
tests/test_tier3_formulas.py::TestSimulateCompany::test_higher_severity_larger_loss PASSED
tests/test_tier3_formulas.py::TestRunTier3::test_run_tier3_returns_outcome PASSED
tests/test_tier3_formulas.py::TestRunTier3::test_time_steps_present PASSED
tests/test_tier3_formulas.py::TestRunTier3::test_from_ticker_fallback PASSED

49 passed in 1.92s
```

### CI Workflow
ADDED (`.github/workflows/ci.yml`)

---

## What This Repo Does (One Paragraph)

`mimic-sim` is a Monte Carlo simulation engine that runs thousands of scenario outcomes for a set of companies, producing economically coherent financial impact distributions rather than point estimates. It operates in three tiers: Tier 3 (formula-only, no LLM calls, fast), Tier 2 (cached LLM decisions on a parameter grid, moderate cost), and Tier 1 (live LLM call per run, most accurate, ~$0.12/scenario). The `Simulation` class accepts a list of tickers, a scenario description, and a run count, samples from a `ParameterSpace` (severity, duration, macro shocks, intervention rates), applies the economic formulas or LLM outcomes, and returns a `SimulationResult` with P10/P50/P90 impacts, VaR, CVaR, correlation matrices, sensitivity analysis, and tornado plots. Tier 1 and Tier 2 are currently stubs; Tier 3 is fully implemented and tested.

---

## What Is Already Built

- `mimic_sim/__init__.py` — public API; re-exports `Simulation`, `SimulationResult`, `ParameterSpace`
- `mimic_sim/simulation.py` — `Simulation` top-level entry point: `run(mode="tier3"|"tier2"|"tier1")`, dispatches to execution modules; Tier 1 and Tier 2 raise `NotImplementedError` (stubs)
- `mimic_sim/result.py` — `SimulationResult` analytics layer: `percentile()`, `var()`, `cvar()`, `correlation_matrix()`, `tail_coincidence()`, `sensitivity()`, `worst_runs()`, `best_runs()`, `median_run()`, `summary()` DataFrame, `describe()`, `time_series()`
- `mimic_sim/parameter_space.py` — `ParameterSpace` with `Distribution` wrappers: Uniform, Normal, LogNormal, Triangular, Empirical, Constant; reproducible seeded sampling
- `mimic_sim/cache.py` — `DecisionCache` (Tier 2): `build()`, `lookup()`, `save()`, `load()` — pre-computes LLM decisions over severity × duration grid; implemented but not yet connected to `Simulation.run(mode="tier2")`
- `mimic_sim/optimizer.py` — `DecisionOptimizer`: finds the company action minimising downside or maximising expected outcome across simulation runs
- `mimic_sim/execution/tier3_formulas.py` — Tier 3 pure-formula execution: `base_revenue_impact()`, `macro_impact()`, `intervention_dampening()`, `simulate_company()`, `run_tier3()`; self-contained ticker fallback profiles
- `mimic_sim/visualization/distributions.py` — matplotlib helpers: distribution histograms, tornado plots, time-series overlays, percentile fan charts; all accept optional `ax` parameter

---

## Immediate Next Tasks

**Priority 1 — Tier 2 decision cache connection (most important)**
`mimic_sim/cache.py` has `DecisionCache` fully implemented but `mimic_sim/simulation.py` still raises `NotImplementedError` for `mode="tier2"`. Wire `Simulation.run(mode="tier2")` to call `DecisionCache.lookup()` for each run. The grid is: severity [0.3, 0.5, 0.7, 0.9] × duration [7, 14, 30, 60, 90] = 20 configs; at 3 companies × 4 steps = 60 LLM calls per scenario (~$0.12 per scenario to pre-build the cache).

**Priority 2 — VaR calibration note**
In `README.md` and `SimulationResult`, add a `confidence_note` field with the text: `"Tier 3 (formula-only) distributions are wide by design. Tier 2 (cached LLM) narrows outcomes via behavioral anchoring. Do not use Tier 3 VaR numbers for production risk decisions."` Also surface this in `SimulationResult.describe()` output.

**Priority 3 — Sensitivity analysis tornado plot test**
`SimulationResult.sensitivity()` is implemented and tested (returns dict summing to 1.0). Confirm it is sorted by descending importance, then add a test for `plot_sensitivity_tornado()` in `mimic_sim/visualization/distributions.py` — assert the returned `matplotlib.Figure` has the correct number of bars. The duration > severity finding (~86% vs ~3%) must be reproducible by running `examples/02_sensitivity_analysis.py`.

**Priority 4 — Tier 1 parallel execution**
In `mimic_sim/execution/` add `tier1_llm.py`. Use `asyncio` + `asyncio.Semaphore(5)` to run multiple simulation runs concurrently (max 5 parallel LLM calls). This reduces 100-run Tier 1 from ~20 minutes to ~4 minutes. Wire `Simulation.run(mode="tier1")` to this module.

**Priority 5 — PyPI publish**
Package name: `mimic-sim`. Dependencies: `mimic-framework`, `mimic-world`, `mimic-forecast`. Run `python -m build && twine upload dist/*`.

---

## How to Run (Developer Quick Reference)

```bash
cd ~/Desktop/mimic/Mimic-sim
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v          # run tests
pip install -e ".[dev]"   # reinstall after changes
```

---

## Known Issues

- `Simulation.run(mode="tier2")` and `Simulation.run(mode="tier1")` both raise `NotImplementedError` — only Tier 3 (formula-only) is production-ready.
- `mimic_sim/cache.py` (`DecisionCache`) is fully implemented but not yet wired into `Simulation`.
- Tier 3 VaR distributions are intentionally wide; must not be used for production risk decisions without Tier 2/1 behavioral anchoring (see Priority 2 above).

---

## Dependencies on Other Mimic Repos

- `mimic-framework` — used by Tier 1 execution (planned): `mimic.Twin` provides the LLM decision per simulation run.
- `mimic-world` — used by Tier 1/2 execution (planned): `World.run(scenario)` drives the cascade per run.
- `mimic-forecast` — optional integration for macro covariate sampling in the `ParameterSpace`.
