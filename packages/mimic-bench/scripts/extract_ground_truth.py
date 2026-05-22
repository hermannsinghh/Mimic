#!/usr/bin/env python3
"""Stage 1 + Stage 2 ground truth extraction pipeline.

Stage 1 (signal detection): Check SEC EDGAR for 8-K filings within 30 days
of each event. Mark companies as 'potentially affected' if found.

Stage 2 (LLM extraction): Feed 8-K text + optional transcript excerpt to
Claude and extract structured labels.

Usage:
  python scripts/extract_ground_truth.py                          # all events, all tickers
  python scripts/extract_ground_truth.py --event 2021_03_suez_canal
  python scripts/extract_ground_truth.py --ticker FDX --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mimic_bench.datasets import load_companies, load_events  # noqa: E402
from mimic_bench.extraction.sec import fetch_8k_filings  # noqa: E402
from mimic_bench.extraction.llm_extract import (  # noqa: E402
    extract_label, extract_without_source,
)

LABELS_FILE = REPO_ROOT / "data" / "ground_truth" / "labels_v1.jsonl"


def _load_existing(path: Path) -> dict[str, set[str]]:
    """Return {event_id: {ticker, ...}} for already-extracted pairs."""
    done: dict[str, set[str]] = {}
    if not path.exists():
        return done
    with open(path) as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            done.setdefault(rec["event_id"], set()).add(rec["ticker"])
    return done


def _append(path: Path, record: dict) -> None:
    with open(path, "a") as fp:
        fp.write(json.dumps(record) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", help="Event ID to process (default: all)")
    parser.add_argument("--ticker", help="Ticker to process (default: all)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--skip-stage1", action="store_true",
                        help="Skip signal detection, extract all pairs")
    args = parser.parse_args()

    events = load_events()
    companies = load_companies()
    done = _load_existing(LABELS_FILE)

    target_events = (
        [events[args.event]] if args.event else sorted(events.values(), key=lambda e: e["date"])
    )
    target_companies = [c for c in companies if not args.ticker or c["ticker"] == args.ticker]

    if not args.dry_run:
        try:
            import anthropic
            client = anthropic.Anthropic()
        except ImportError:
            print("pip install anthropic", file=sys.stderr)
            sys.exit(1)
    else:
        client = None

    LABELS_FILE.parent.mkdir(parents=True, exist_ok=True)

    for event in target_events:
        eid = event["id"]
        already_done = done.get(eid, set())
        print(f"\n[{eid}] ({event['date']})")

        for company in target_companies:
            ticker = company["ticker"]
            if ticker in already_done:
                print(f"  {ticker}: skip (already extracted)")
                continue

            # --- Stage 1: signal detection ---
            source_text = None
            if not args.skip_stage1:
                try:
                    from mimic_bench.extraction.sec import fetch_8k_filings
                    filings = fetch_8k_filings(
                        ticker,
                        after_date=event["date"],
                        before_date=event.get("end_date", event["date"]),
                        max_results=3,
                    )
                    if not filings:
                        print(f"  {ticker}: no 8-K found in window, using model knowledge")
                    else:
                        print(f"  {ticker}: {len(filings)} 8-K(s) found")
                        # For now use extract_without_source; production would fetch doc text
                        source_text = None
                except Exception as exc:
                    print(f"  {ticker}: stage1 error ({exc}), using model knowledge")

            # --- Stage 2: LLM extraction ---
            print(f"  {ticker}: extracting...", end=" ", flush=True)
            if args.dry_run:
                print("[dry-run]")
                continue

            try:
                if source_text:
                    record = extract_label(event, company, source_text, client=client)
                else:
                    record = extract_without_source(event, company, client=client)
                _append(LABELS_FILE, record)
                print(f"done (confidence={record.get('confidence', '?'):.2f})")
            except Exception as exc:
                print(f"ERROR: {exc}", file=sys.stderr)

            time.sleep(args.delay)

    print("\nExtraction complete.")


if __name__ == "__main__":
    main()
