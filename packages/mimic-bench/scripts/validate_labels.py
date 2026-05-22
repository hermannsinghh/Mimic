#!/usr/bin/env python3
"""Human review tool for spot-checking ground truth labels.

Randomly samples N pairs and presents them for review via CLI.
Updates confidence and human_reviewed fields in place.

Usage:
  python scripts/validate_labels.py --sample 28   # review 28 random pairs
  python scripts/validate_labels.py --event 2020_03_covid_lockdowns
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LABELS_FILE = REPO_ROOT / "data" / "ground_truth" / "labels_v1.jsonl"


def load_all() -> list[dict]:
    if not LABELS_FILE.exists():
        return []
    records = []
    with open(LABELS_FILE) as fp:
        for line in fp:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def save_all(records: list[dict]) -> None:
    with open(LABELS_FILE, "w") as fp:
        for rec in records:
            fp.write(json.dumps(rec) + "\n")


def review_record(rec: dict) -> dict:
    print("\n" + "=" * 60)
    print(f"Event: {rec['event_id']}")
    print(f"Ticker: {rec['ticker']}")
    print(f"  0-24h : {rec.get('actual_action_0_24h')}")
    print(f"  1-7d  : {rec.get('actual_action_1_7d')}")
    print(f"  8-30d : {rec.get('actual_action_8_30d')}")
    print(f"  $M    : {rec.get('financial_impact_usdM')}")
    print(f"  Confidence: {rec.get('confidence'):.2f}  |  human_reviewed: {rec.get('human_reviewed')}")
    print()

    action = input("Action: [a]ccept / [e]dit / [s]kip / [q]uit > ").strip().lower()

    if action == "q":
        raise SystemExit(0)
    if action == "s":
        return rec
    if action == "a":
        rec["human_reviewed"] = True
        rec["confidence"] = min(rec.get("confidence", 0.8) + 0.05, 1.0)
        print(f"  → Accepted (confidence now {rec['confidence']:.2f})")
        return rec
    if action == "e":
        for field in ["actual_action_0_24h", "actual_action_1_7d", "actual_action_8_30d"]:
            current = rec.get(field) or ""
            new_val = input(f"  {field} [{current[:60]}...]: ").strip()
            if new_val:
                rec[field] = new_val
        fi = input(f"  financial_impact_usdM [{rec.get('financial_impact_usdM')}]: ").strip()
        if fi:
            try:
                rec["financial_impact_usdM"] = float(fi)
                rec["financial_impact_reported"] = True
            except ValueError:
                pass
        conf = input(f"  confidence [{rec.get('confidence'):.2f}]: ").strip()
        if conf:
            try:
                rec["confidence"] = float(conf)
            except ValueError:
                pass
        rec["human_reviewed"] = True
        print("  → Updated")
    return rec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=10, help="Number of pairs to review")
    parser.add_argument("--event", help="Limit to a specific event_id")
    parser.add_argument("--not-reviewed", action="store_true",
                        help="Only show not-yet-human-reviewed records")
    args = parser.parse_args()

    records = load_all()
    if not records:
        print("No labels found.")
        return

    pool = records
    if args.event:
        pool = [r for r in pool if r["event_id"] == args.event]
    if args.not_reviewed:
        pool = [r for r in pool if not r.get("human_reviewed")]

    sample = random.sample(pool, min(args.sample, len(pool)))
    print(f"Reviewing {len(sample)} records (out of {len(pool)} in scope).")

    updated: dict[str, dict] = {}
    for rec in sample:
        key = f"{rec['event_id']}|{rec['ticker']}"
        reviewed = review_record(dict(rec))
        updated[key] = reviewed

    # Merge updates back
    for i, rec in enumerate(records):
        key = f"{rec['event_id']}|{rec['ticker']}"
        if key in updated:
            records[i] = updated[key]

    save_all(records)
    print(f"\nSaved {len(updated)} reviewed records.")


if __name__ == "__main__":
    main()
