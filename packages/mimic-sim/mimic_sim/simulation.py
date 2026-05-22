"""
Simulation — the top-level entry point for mimic-sim.

Usage:
    from mimic_sim import Simulation, ParameterSpace, Distribution
    from mimic_sim.execution.tier3_formulas import CompanyProfile

    space = ParameterSpace(
        severity=Distribution.triangular(0.4, 0.7, 0.95),
        duration_days=Distribution.lognormal(mean=3.4, sigma=0.5),
        macro_conditions={"oil_price": Distribution.normal(85, 20)},
    )
    sim = Simulation(
        profiles=[CompanyProfile.walmart(), CompanyProfile.apple()],
        scenario_name="taiwan_strait_closure_30d",
        parameter_space=space,
        n_runs=1000,
    )
    result = sim.run(mode="tier3")
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from tqdm import tqdm

from mimic_sim.execution.tier3_formulas import CompanyProfile, RunOutcome, run_tier3
from mimic_sim.parameter_space import ParameterSpace, SampledParams
from mimic_sim.result import SimulationResult


# ── Simulation configuration ───────────────────────────────────────────────────

@dataclass
class Simulation:
    """
    Monte Carlo simulation over a scenario and a set of company profiles.

    profiles         : companies to simulate (Tier 3: CompanyProfile; Tier 1/2: mimic Twins)
    scenario_name    : identifier for the event scenario
    parameter_space  : defines the randomness across runs
    n_runs           : number of Monte Carlo draws
    seed             : reproducibility seed (None = random)
    """

    profiles: list[CompanyProfile]
    scenario_name: str
    parameter_space: ParameterSpace
    n_runs: int = 1000
    seed: int | None = 42

    def run(
        self,
        mode: str = "tier3",
        *,
        cache: object | None = None,
        parallel: bool = False,
        n_workers: int = 4,
    ) -> SimulationResult:
        """
        Execute the simulation.

        mode     : "tier3" (formula-only) | "tier2" (cached LLM) | "tier1" (live LLM)
        cache    : DecisionCache for mode="tier2"; auto-built with formula proxy if None
        parallel : use multiprocessing for Tier 3 runs (useful for n > 5000)
        """
        if mode == "tier3":
            return self._run_tier3(parallel=parallel, n_workers=n_workers)
        elif mode == "tier2":
            return self._run_tier2(cache=cache)
        elif mode == "tier1":
            raise NotImplementedError("Tier 1 (live LLM) is coming in v0.4.0")
        else:
            raise ValueError(f"Unknown mode '{mode}'. Choose 'tier1', 'tier2', or 'tier3'.")

    def _run_tier3(self, parallel: bool, n_workers: int) -> SimulationResult:
        rng = np.random.default_rng(self.seed)
        param_batch = self.parameter_space.sample_batch(self.n_runs, seed=int(rng.integers(0, 2**31)))

        t0 = time.perf_counter()

        if parallel and self.n_runs >= 500:
            runs = self._run_parallel(param_batch, n_workers)
        else:
            runs = self._run_serial(param_batch)

        elapsed = time.perf_counter() - t0
        print(
            f"  Tier 3 complete: {self.n_runs:,} runs in {elapsed:.2f}s "
            f"({self.n_runs / elapsed:,.0f} runs/s)"
        )

        return SimulationResult(
            n_runs=self.n_runs,
            scenario_name=self.scenario_name,
            tickers=[p.ticker for p in self.profiles],
            runs=runs,
            mode="tier3",
        )

    def _run_tier2(self, cache: object | None) -> SimulationResult:
        from mimic_sim.cache import DecisionCache
        from mimic_sim.execution.tier2_cached import run_tier2

        if cache is None:
            cache = DecisionCache()
            cache.build(self.profiles, self.scenario_name)

        rng = np.random.default_rng(self.seed)
        param_batch = self.parameter_space.sample_batch(self.n_runs, seed=int(rng.integers(0, 2**31)))

        t0 = time.perf_counter()
        runs = [
            run_tier2(self.profiles, params, run_id, cache)
            for run_id, params in enumerate(
                tqdm(param_batch, desc="Simulating (Tier 2)", unit="run")
            )
        ]
        elapsed = time.perf_counter() - t0
        print(
            f"  Tier 2 complete: {self.n_runs:,} runs in {elapsed:.2f}s "
            f"({self.n_runs / elapsed:,.0f} runs/s)"
        )

        return SimulationResult(
            n_runs=self.n_runs,
            scenario_name=self.scenario_name,
            tickers=[p.ticker for p in self.profiles],
            runs=runs,
            mode="tier2",
        )

    def _run_serial(self, param_batch: list[SampledParams]) -> list[RunOutcome]:
        runs = []
        for run_id, params in enumerate(tqdm(param_batch, desc="Simulating", unit="run")):
            runs.append(run_tier3(self.profiles, params, run_id))
        return runs

    def _run_parallel(self, param_batch: list[SampledParams], n_workers: int) -> list[RunOutcome]:
        # Chunk into equal-sized batches for each worker
        chunk_size = max(1, len(param_batch) // n_workers)
        chunks = [
            (i * chunk_size, param_batch[i * chunk_size: (i + 1) * chunk_size])
            for i in range(n_workers)
        ]
        # Handle remainder
        remainder_start = n_workers * chunk_size
        if remainder_start < len(param_batch):
            chunks[-1] = (
                chunks[-1][0],
                param_batch[chunks[-1][0]:],
            )

        results: dict[int, RunOutcome] = {}
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = {
                pool.submit(_run_chunk, self.profiles, offset, chunk): offset
                for offset, chunk in chunks
            }
            with tqdm(total=self.n_runs, desc="Simulating (parallel)", unit="run") as pbar:
                for future in as_completed(futures):
                    chunk_runs = future.result()
                    for r in chunk_runs:
                        results[r.run_id] = r
                    pbar.update(len(chunk_runs))

        return [results[i] for i in sorted(results)]


def _run_chunk(
    profiles: list[CompanyProfile],
    offset: int,
    params_chunk: list[SampledParams],
) -> list[RunOutcome]:
    """Top-level (picklable) worker function for parallel execution."""
    return [run_tier3(profiles, p, offset + i) for i, p in enumerate(params_chunk)]
