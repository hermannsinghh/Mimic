#!/usr/bin/env python3
"""Scaffold new event JSON files from a CSV/spreadsheet of events.

Usage:
  python scripts/build_event_list.py --csv my_events.csv
  python scripts/build_event_list.py --interactive   # prompt for each event

Expected CSV columns: id, title, date, end_date, category, severity, description,
                      affected_sectors (semicolon-separated), keywords (semicolon-separated)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENTS_DIR = REPO_ROOT / "data" / "events"

CATEGORIES = [
    "supply_chain", "geopolitical", "macro", "energy",
    "natural_disaster", "industry", "pandemic", "regulatory",
]


def _make_event(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "date": row["date"],
        "end_date": row.get("end_date") or row["date"],
        "category": row.get("category", ""),
        "severity": float(row.get("severity", 0.5)),
        "description": row.get("description", ""),
        "affected_sectors": [s.strip() for s in row.get("affected_sectors", "").split(";") if s.strip()],
        "affected_geographies": [g.strip() for g in row.get("affected_geographies", "").split(";") if g.strip()],
        "keywords": [k.strip() for k in row.get("keywords", "").split(";") if k.strip()],
        "source": row.get("source", ""),
        "source_url": row.get("source_url", None),
    }


def _write_event(event: dict, overwrite: bool = False) -> None:
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EVENTS_DIR / f"{event['id']}.json"
    if path.exists() and not overwrite:
        print(f"  Skip (exists): {path.name}")
        return
    path.write_text(json.dumps(event, indent=2))
    print(f"  Wrote: {path.name}")


def from_csv(csv_path: str, overwrite: bool = False) -> None:
    with open(csv_path) as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            event = _make_event(row)
            _write_event(event, overwrite)


def interactive(overwrite: bool = False) -> None:
    print("Enter event details (blank to finish):\n")
    while True:
        eid = input("Event ID (e.g. 2024_01_red_sea_attacks): ").strip()
        if not eid:
            break
        row = {
            "id": eid,
            "title": input("Title: ").strip(),
            "date": input("Date (YYYY-MM-DD): ").strip(),
            "end_date": input("End date (YYYY-MM-DD, or blank): ").strip(),
            "category": input(f"Category {CATEGORIES}: ").strip(),
            "severity": input("Severity (0.0-1.0): ").strip() or "0.5",
            "description": input("Description: ").strip(),
            "affected_sectors": input("Affected sectors (semicolon-separated): ").strip(),
            "keywords": input("Keywords (semicolon-separated): ").strip(),
            "source": input("Source: ").strip(),
        }
        event = _make_event(row)
        _write_event(event, overwrite)
        print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="Path to CSV file")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.csv:
        from_csv(args.csv, overwrite=args.overwrite)
    elif args.interactive:
        interactive(overwrite=args.overwrite)
    else:
        print("Pass --csv <file> or --interactive")
        sys.exit(1)


if __name__ == "__main__":
    main()
