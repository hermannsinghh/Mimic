# NEXT_STEPS.md — mimic-world

## Status as of 2026-05-18

### Install
PASS (installed via `pip install -e ".[dev]" --ignore-requires-python` — note: package requires Python >=3.11; sandbox runs 3.10.12 but install succeeds with flag and tests all pass)

### Tests
54 passing, 0 failing.

```
tests/test_cascade.py::TestCascadeEngineBasic::test_single_step_returns_world_result PASSED
tests/test_cascade.py::TestCascadeEngineBasic::test_cascade_timeline_has_correct_steps PASSED
tests/test_cascade.py::TestCascadeEngineBasic::test_decisions_made_for_affected_twins PASSED
tests/test_cascade.py::TestCascadeEngineBasic::test_mock_twins_called PASSED
tests/test_cascade.py::TestCascadeEngineBasic::test_system_stability_is_valid PASSED
tests/test_cascade.py::TestCascadeEngineBasic::test_financial_impacts_computed PASSED
tests/test_cascade.py::TestCascadeEngineBasic::test_most_affected_is_ordered_by_magnitude PASSED
tests/test_cascade.py::TestCascadeEngineBasic::test_who_acted_first_is_subset_of_twins PASSED
tests/test_cascade.py::TestCascadePropagation::test_world_state_updates_from_twin_decisions PASSED
tests/test_cascade.py::TestCascadePropagation::test_cascade_rules_apply PASSED
tests/test_cascade.py::TestCascadePropagation::test_second_order_effects_detected PASSED
tests/test_cascade.py::TestWorldResultExport::test_export_json PASSED
tests/test_cascade.py::TestWorldResultExport::test_export_unsupported_format_raises PASSED
tests/test_cascade.py::TestWorldResultExport::test_compare_two_results PASSED
tests/test_graph.py::TestAddEdge::test_edge_added PASSED
tests/test_graph.py::TestAddEdge::test_nodes_registered PASSED
tests/test_graph.py::TestAddEdge::test_len_is_node_count PASSED
tests/test_graph.py::TestUpstreamDownstream::test_downstream_from_tsmc PASSED
tests/test_graph.py::TestUpstreamDownstream::test_upstream_of_aapl PASSED
tests/test_graph.py::TestUpstreamDownstream::test_no_upstream_for_root PASSED
tests/test_graph.py::TestGetNeighbors::test_tsmc_neighbors PASSED
tests/test_graph.py::TestGetNeighbors::test_aapl_neighbors PASSED
tests/test_graph.py::TestPropagateShock::test_origin_has_full_shock PASSED
tests/test_graph.py::TestPropagateShock::test_downstream_has_attenuated_shock PASSED
tests/test_graph.py::TestPropagateShock::test_unconnected_company_not_affected PASSED
tests/test_graph.py::TestPropagateShock::test_tiny_shocks_pruned PASSED
tests/test_graph.py::TestGetEdgesFor::test_edges_for_tsmc PASSED
tests/test_graph.py::TestRepr::test_repr_shows_counts PASSED
tests/test_macro.py::TestMacroEnvironment::test_default_state PASSED
tests/test_macro.py::TestMacroEnvironment::test_apply_shock_interest_rate PASSED
tests/test_macro.py::TestMacroEnvironment::test_apply_shock_fx_rate PASSED
tests/test_macro.py::TestMacroEnvironment::test_apply_shock_commodity PASSED
tests/test_macro.py::TestMacroEnvironment::test_interest_rate_cannot_go_negative PASSED
tests/test_macro.py::TestMacroEnvironment::test_unknown_shock_key_is_ignored PASSED
tests/test_macro.py::TestMacroEnvironment::test_flat_dict_has_fx_rates PASSED
tests/test_macro.py::TestMacroEnvironment::test_forecast_macro_returns_state PASSED
tests/test_scenario.py::TestScenarioFromLibrary::test_loads_taiwan_strait PASSED
tests/test_scenario.py::TestScenarioFromLibrary::test_initial_shocks_are_floats PASSED
tests/test_scenario.py::TestScenarioFromLibrary::test_cascade_rules_loaded PASSED
tests/test_scenario.py::TestScenarioFromLibrary::test_unknown_scenario_raises PASSED
tests/test_scenario.py::TestScenarioFromLibrary::test_list_library_returns_50_scenarios PASSED
tests/test_scenario.py::TestScenarioFromLibrary::test_all_library_scenarios_are_loadable PASSED
tests/test_scenario.py::TestScenarioFromLibrary::test_all_library_scenarios_have_initial_shocks PASSED
tests/test_scenario.py::TestScenarioFromDict::test_round_trip PASSED
tests/test_scenario.py::TestScenarioFromDict::test_custom_scenario PASSED
tests/test_scenario.py::TestScenarioRepr::test_repr PASSED
tests/test_world.py::TestWorldConstruction::test_empty_world PASSED
tests/test_world.py::TestWorldConstruction::test_add_twin PASSED
tests/test_world.py::TestWorldConstruction::test_add_multiple_twins PASSED
tests/test_world.py::TestWorldConstruction::test_connect_creates_edge PASSED
tests/test_world.py::TestWorldConstruction::test_run_raises_on_empty_world PASSED
tests/test_world.py::TestWorldConstruction::test_repr PASSED
tests/test_world.py::TestWorldSnapshot::test_snapshot_has_twins PASSED
tests/test_world.py::TestWorldSnapshot::test_snapshot_has_macro PASSED

============================== 54 passed in 0.18s ==============================
```

### CI Workflow
ADDED (`.github/workflows/ci.yml`)

---

## What This Repo Does (One Paragraph)

`mimic-world` is the multi-company scenario engine that simulates supply chain cascade effects across a network of companies. You build a `World` by adding `Twin` objects and connecting them with supplier/customer relationships, load a scenario from the 50-scenario library (or define your own), and run the cascade — the `CascadeEngine` propagates shocks through the `RelationshipGraph` step by step, calling each affected twin's LLM to make decisions, updating `MacroEnvironment` state between steps, and collecting everything into a `WorldResult` with per-company financial impacts and timeline. The scenario library covers geopolitical, supply chain, energy, macro, and climate shocks.

---

## What Is Already Built

- `mimic_world/__init__.py` — public API; re-exports `World`, `Scenario`, `WorldResult`, `RelationshipGraph`, `MacroEnvironment`
- `mimic_world/world.py` — `World` container: `add_twin()`, `connect()`, `run(scenario)`, `snapshot()`
- `mimic_world/cascade.py` — `CascadeEngine`: multi-step shock propagation loop, `TimeStepResult` collection, `WorldResult` assembly, `export()` (JSON), `compare()`
- `mimic_world/graph.py` — `RelationshipGraph`: directed graph over company tickers using networkx, `upstream()`, `downstream()`, `propagate_shock()` with attenuation, pruning of sub-threshold shocks
- `mimic_world/scenario.py` — `Scenario` Pydantic model: `from_library(id)`, `from_dict()`, 50-scenario JSON library under `scenarios/library/`
- `mimic_world/result.py` — `WorldResult`, `TimeStepResult`, `Decision` output types; `export(format)`, `compare()`, `financial_impacts`, `most_affected`, `who_acted_first`
- `mimic_world/macro.py` — `MacroEnvironment`: interest rates, FX rates, commodity prices, credit spreads; `apply_shock()`, `flat_dict()`, `forecast_macro()` placeholder
- `mimic_world/twin.py` — LLM-backed `Twin` stub (calls Claude directly via `anthropic` client), used when `mimic-framework` is not installed
- `mimic_world/visualization.py` — cascade timeline charts and world graph rendering via matplotlib
- `scenarios/library/` — 50 hand-authored scenario JSON files

---

## Immediate Next Tasks

**Priority 1 — Auto relationship graph from 10-K**
In `mimic_world/graph.py`, add `RelationshipGraph.from_tickers(list[str])`. Reads each company's 10-K supplier section (via mimic's SEC module in `mimic-framework`) and populates edges automatically. Manual overrides via `graph.connect()` should still work on top of the auto-populated graph.

**Priority 2 — 5-company cascade integration test**
Create `tests/test_cascade_integration.py`. Build world with WMT, AAPL, FDX, XOM, TSMC (or AMD if TSMC unavailable). Run `taiwan_strait_closure_30d` scenario. Assert: at least 3 companies have non-null decisions at time step 7. Assert: `world_state` after step 1 differs from `world_state` before step 1. Use `unittest.mock.patch` to stub the LLM calls.

**Priority 3 — Scenario library validation**
All 50 JSON files in `scenarios/library/` must load without errors. `test_all_library_scenarios_are_loadable` already passes — verify it actually loads every file or just a subset. Add a test asserting all 50 files have non-empty `cascade_rules` and `initial_shocks` dicts.

**Priority 4 — `WorldResult.export(format="csv")` implementation**
In `mimic_world/result.py`, implement `export(format="csv")`. Output: one row per `(ticker, time_step)` with decision summary and financial impact. The JSON export already passes tests; CSV is not yet tested.

**Priority 5 — PyPI publish**
Package name: `mimic-world`. Dependencies: `mimic-framework`, `mimic-forecast`. Run `python -m build && twine upload dist/*`.

---

## How to Run (Developer Quick Reference)

```bash
cd ~/Desktop/mimic/Mimic-world
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v          # run tests
pip install -e ".[dev]"   # reinstall after changes
```

---

## Known Issues

- `mimic_world/macro.py`: `forecast_macro()` is a placeholder stub — Phase 3 integration with `mimic-forecast` (BISTRO/TimesFM) is noted in comments but not implemented.
- `mimic_world/twin.py` calls `anthropic` directly rather than routing through `mimic-framework`'s orchestrator, creating a potential divergence in prompting logic.
- CSV export via `WorldResult.export(format="csv")` has no test coverage yet.

---

## Dependencies on Other Mimic Repos

- `mimic-framework` — optional; `mimic_world/graph.py` `from_tickers()` (planned) will use mimic's SEC module. Currently `mimic_world/twin.py` calls `anthropic` directly.
- `mimic-forecast` — optional; `mimic_world/macro.py` `forecast_macro()` is a placeholder for Phase 3 integration with TimesFM/BISTRO.
