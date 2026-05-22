"""Leaderboard utilities for mimic-bench.

The leaderboard is a JSON file hosted in the repo (data/leaderboard.json).
Anyone can submit a score; scores are ranked by mean fidelity.

Usage:
    from mimic_bench.leaderboard import submit, display

    results = bench.run(my_twin)
    submit(results, model_name="mimic-v0.2", notes="Added SEC RAG")
    display()
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

_LB_PATH = Path(__file__).parent.parent / "data" / "leaderboard.json"


def _load() -> List[dict]:
    if not _LB_PATH.exists():
        return []
    with open(_LB_PATH) as fp:
        return json.load(fp)


def _save(entries: List[dict]) -> None:
    _LB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LB_PATH, "w") as fp:
        json.dump(entries, fp, indent=2)


def submit(
    results,  # BenchmarkResult
    model_name: str,
    notes: Optional[str] = None,
    submitter: Optional[str] = None,
    overwrite: bool = False,
) -> dict:
    """Add a benchmark result to the local leaderboard.

    Args:
        results: BenchmarkResult from bench.run().
        model_name: Identifier for this model/configuration.
        notes: Optional description of this submission.
        submitter: Optional name/org.
        overwrite: If True, replace an existing entry with the same model_name.

    Returns:
        The new leaderboard entry.
    """
    entries = _load()

    if not overwrite:
        existing = [e for e in entries if e["model_name"] == model_name]
        if existing:
            raise ValueError(
                f"Entry '{model_name}' already exists. Use overwrite=True to replace."
            )

    summary = results.summary
    entry: dict = {
        "model_name": model_name,
        "submitted_at": datetime.utcnow().isoformat() + "Z",
        "submitter": submitter or os.environ.get("USER", "anonymous"),
        "notes": notes,
        "fidelity_overall": summary.get("overall", {}).get("mean", 0.0),
        "fidelity_std": summary.get("overall", {}).get("std", 0.0),
        "n_pairs": summary.get("overall", {}).get("n", 0),
        "by_category": {k: v["mean"] for k, v in summary.get("by_category", {}).items()},
        "by_component": {
            k: v["mean"] for k, v in summary.get("by_component", {}).items()
        },
    }

    entries = [e for e in entries if e["model_name"] != model_name]
    entries.append(entry)
    entries.sort(key=lambda e: e["fidelity_overall"], reverse=True)
    _save(entries)
    return entry


def display(top_n: int = 20) -> None:
    """Print the leaderboard to stdout."""
    entries = _load()
    if not entries:
        print("Leaderboard is empty. Run bench.run() and call submit().")
        return

    print(f"\n{'Rank':<5} {'Model':<30} {'Fidelity':>9} {'Std':>7} {'N':>6}  {'Submitted'}")
    print("-" * 72)
    for rank, entry in enumerate(entries[:top_n], 1):
        print(
            f"{rank:<5} {entry['model_name']:<30} "
            f"{entry['fidelity_overall']:>9.4f} "
            f"{entry['fidelity_std']:>7.4f} "
            f"{entry['n_pairs']:>6}  "
            f"{entry['submitted_at'][:10]}"
        )
    print()


def get_entries() -> List[dict]:
    """Return all leaderboard entries sorted by fidelity."""
    return _load()
