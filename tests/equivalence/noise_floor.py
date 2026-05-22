"""Noise-floor measurement — pre-F-12 prerequisite.

Per ADR 2026-05-21-runner-equivalence-criterion.md, the equivalence test
asserts ``W1(in_process_runner, concordia_runner) < THRESHOLD[prefab]``.
That bound is only meaningful if it's larger than the *within-runner*
variance — i.e. running the same runner twice with two different seeds
shouldn't produce a W1 larger than the threshold. If it does, the
threshold is testing against noise.

Usage::

    from tests.equivalence import measure_noise_floor

    result = measure_noise_floor(
        runner_factory=lambda: ScenarioRunner(pdp=..., persona_builder=...),
        spec=load_spec("scenarios/svb-replay-2023/scenario.yaml"),
        liability_network=...,
        seeds=[0x57AB1107, 0xC0V1D2020, 0x20080915, 0x6BD7BEEF],
    )
    print(result.max_w1_per_prefab)   # → use as floor when picking thresholds
    print(result.max_tv_per_prefab)

Run BEFORE the first ConcordiaPersonaBuilder run. The numbers feed into the
threshold-provenance discussion in the equivalence ADR — a threshold below
the measured floor is unacceptable, and is the kind of finding that wants
to surface BEFORE someone has spent two days iterating a prefab.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

import numpy as np


@dataclass(frozen=True)
class NoiseFloorResult:
    """Within-runner variance over a set of seeds, per prefab."""
    seeds: tuple[int, ...]
    n_pairs: int
    # max W1 distance observed across all seed pairs, keyed by action_type
    # (or by prefab name once F-12 attaches a prefab tag to each Decision)
    max_w1_per_group: dict[str, float] = field(default_factory=dict)
    mean_w1_per_group: dict[str, float] = field(default_factory=dict)
    max_tv_per_group: dict[str, float] = field(default_factory=dict)
    mean_tv_per_group: dict[str, float] = field(default_factory=dict)
    per_group_sample_counts: dict[str, int] = field(default_factory=dict)

    def floor_violated(self, threshold_w1: dict[str, float]) -> list[str]:
        """Return the groups where the noise floor exceeds the proposed
        threshold — those thresholds are unacceptable and must be loosened
        (which means the prefab needs tightening, per the equivalence ADR)."""
        return [
            g for g, t in threshold_w1.items()
            if self.max_w1_per_group.get(g, 0.0) >= t
        ]


def _w1_1d(a: Sequence[float], b: Sequence[float]) -> float:
    """Reuses the implementation in eval/harness/metrics.py so the noise
    floor and the equivalence test agree on what 'distance' means.
    """
    from eval.harness.metrics import wasserstein1
    return wasserstein1(a, b)


def _tv_histograms(a: Sequence[str], b: Sequence[str]) -> float:
    """Total-variation distance between two action-type histograms."""
    labels = set(a) | set(b)
    if not labels:
        return 0.0
    a_n = len(a) or 1
    b_n = len(b) or 1
    a_p = {l: sum(1 for x in a if x == l) / a_n for l in labels}
    b_p = {l: sum(1 for x in b if x == l) / b_n for l in labels}
    return 0.5 * sum(abs(a_p[l] - b_p[l]) for l in labels)


def measure_noise_floor(
    *,
    runner_factory: Callable[[], Any],
    spec: Any,
    liability_network: dict,
    seeds: Sequence[int],
    group_by: Callable[[Any], str] | None = None,
) -> NoiseFloorResult:
    """Run ``spec`` once per seed, collect decisions, compute pairwise W1/TV.

    ``runner_factory`` returns a fresh ``ScenarioRunner`` per call (so the
    only thing that changes between runs is the seed inside ``spec.spec.mc``).

    ``group_by`` extracts a group label from a Decision; defaults to
    ``action_type`` so we get one W1 number per action type. Once F-12
    attaches a ``prefab_name`` to Decisions, swap this to ``lambda d:
    d.prefab_name`` to get per-prefab floors.
    """
    if len(seeds) < 2:
        raise ValueError("measure_noise_floor needs at least 2 seeds")

    if group_by is None:
        group_by = lambda d: d.action_type

    # 1. Run once per seed and collect (decisions, mutated spec)
    runs_by_seed: dict[int, list] = {}
    for s in seeds:
        # mutate seed_global per run; everything else identical
        spec_for_run = spec.model_copy(deep=True)
        spec_for_run.spec.mc = spec_for_run.spec.mc.model_copy(update={"seed_global": int(s)})
        runner = runner_factory()
        manifest = runner.run(spec_for_run, liability_network=liability_network)
        runs_by_seed[s] = list(manifest.decisions)

    # 2. For each seed pair, compute per-group W1 (on quantity) + TV (on action_type)
    seeds_tuple = tuple(seeds)
    pair_w1: dict[str, list[float]] = defaultdict(list)
    pair_tv_action_type: list[float] = []

    for i, sa in enumerate(seeds_tuple):
        for sb in seeds_tuple[i + 1:]:
            decisions_a = runs_by_seed[sa]
            decisions_b = runs_by_seed[sb]

            # TV over action_type — global per pair
            pair_tv_action_type.append(_tv_histograms(
                [d.action_type for d in decisions_a],
                [d.action_type for d in decisions_b],
            ))

            # W1 over quantity, grouped (one number per group)
            groups_a: dict[str, list[float]] = defaultdict(list)
            groups_b: dict[str, list[float]] = defaultdict(list)
            for d in decisions_a:
                groups_a[group_by(d)].append(float(d.quantity))
            for d in decisions_b:
                groups_b[group_by(d)].append(float(d.quantity))

            for g in set(groups_a) | set(groups_b):
                a_q = groups_a.get(g, [])
                b_q = groups_b.get(g, [])
                if not a_q or not b_q:
                    # one side missing the group — treat as max distance for the
                    # observed range to surface the asymmetry loudly
                    pair_w1[g].append(float("inf"))
                    continue
                pair_w1[g].append(_w1_1d(a_q, b_q))

    # 3. Summarise
    max_w1 = {g: max(vs) for g, vs in pair_w1.items()}
    mean_w1 = {g: float(np.mean([v for v in vs if v != float("inf")] or [0.0]))
               for g, vs in pair_w1.items()}
    sample_counts: dict[str, int] = {}
    for s in seeds_tuple:
        for d in runs_by_seed[s]:
            g = group_by(d)
            sample_counts[g] = sample_counts.get(g, 0) + 1

    # TV is global across all decisions, not grouped — store under a sentinel
    max_tv = {"__global_action_type__": max(pair_tv_action_type) if pair_tv_action_type else 0.0}
    mean_tv = {"__global_action_type__": float(np.mean(pair_tv_action_type)) if pair_tv_action_type else 0.0}

    return NoiseFloorResult(
        seeds=seeds_tuple,
        n_pairs=len(pair_tv_action_type),
        max_w1_per_group=max_w1,
        mean_w1_per_group=mean_w1,
        max_tv_per_group=max_tv,
        mean_tv_per_group=mean_tv,
        per_group_sample_counts=sample_counts,
    )
