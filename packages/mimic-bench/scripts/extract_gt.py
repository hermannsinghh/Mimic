#!/usr/bin/env python3
"""LLM-assisted ground truth extraction from public SEC filings and earnings transcripts.

Usage:
  python scripts/extract_gt.py                       # all events, all companies
  python scripts/extract_gt.py --event svb_collapse_2023
  python scripts/extract_gt.py --event covid19_lockdowns_2020 --ticker AAPL
  python scripts/extract_gt.py --dry-run             # print prompts, skip API calls
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mimic_bench.datasets import get_companies, load_events  # noqa: E402

EXTRACT_PROMPT = """\
You are a financial research assistant extracting structured corporate-response data from \
publicly available SEC filings (8-K, 10-Q, 10-K), earnings call transcripts, and press releases.

Event: {event_name} ({event_date})
Context: {event_description}
Observation window: {date_start} to {date_end}

Company: {company_name} ({ticker})
Sector: {sector}

Based only on documented, public sources, extract what this company actually did in response \
to the above event. Be precise and factual. If a dimension is not applicable or not documented, \
use "na".

Return a single JSON object — no prose, no markdown fences:
{{
  "ticker": "{ticker}",
  "name": "{company_name}",
  "sector": "{sector}",
  "event_id": "{event_id}",
  "response": {{
    "operations":   "<maintained|expanded|reduced|suspended|pivoted>",
    "financial":    "<guidance_raised|guidance_maintained|guidance_cut|guidance_withdrawn|na>",
    "supply_chain": "<maintained|disrupted|improved|diversified|na>",
    "workforce":    "<expanded|maintained|furloughed|reduced|remote|na>",
    "capex":        "<increased|maintained|cut|na>",
    "direction":    "<positive|negative|neutral|mixed>",
    "magnitude":    "<minimal|low|medium|high|extreme>",
    "primary_action": "<one sentence: the single most important documented action>"
  }},
  "filing_refs": ["<filing type + date, e.g. '8-K 2020-03-13'>"],
  "summary": "<2-3 sentence factual summary of the company response>"
}}"""


def _build_prompt(event: dict, company: dict) -> str:
    dr = event.get("date_range", {})
    return EXTRACT_PROMPT.format(
        event_name=event["name"],
        event_date=event["date"],
        event_description=event["description"],
        date_start=dr.get("start", event["date"]),
        date_end=dr.get("end", event["date"]),
        company_name=company["name"],
        ticker=company["ticker"],
        sector=company["sector"],
        event_id=event["id"],
    )


def extract_one(event: dict, company: dict, client) -> dict:
    prompt = _build_prompt(event, company)
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    return json.loads(text[start:end])


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract ground truth for mimic-bench")
    parser.add_argument("--event", help="Event ID to process (default: all)")
    parser.add_argument("--ticker", help="Ticker to process (default: all)")
    parser.add_argument("--output-dir", default="ground_truth")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between API calls")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts, skip API")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(exist_ok=True)

    events = load_events()
    companies = get_companies()

    target_events = [events[args.event]] if args.event else sorted(events.values(), key=lambda e: e["date"])
    target_companies = [c for c in companies if not args.ticker or c["ticker"] == args.ticker]

    if not args.dry_run:
        try:
            import anthropic
            client = anthropic.Anthropic()
        except ImportError:
            print("anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
            sys.exit(1)
    else:
        client = None

    for event in target_events:
        out_file = output_dir / f"{event['id']}.json"
        existing: list = json.loads(out_file.read_text()) if out_file.exists() else []
        done = {r["ticker"] for r in existing}
        records = list(existing)

        print(f"\n[{event['id']}]")
        for company in target_companies:
            ticker = company["ticker"]
            if ticker in done:
                print(f"  {ticker}: already extracted, skipping")
                continue

            print(f"  {ticker}: ", end="", flush=True)
            if args.dry_run:
                print(_build_prompt(event, company))
                print("  [dry-run]")
                continue

            try:
                record = extract_one(event, company, client)
                records.append(record)
                out_file.write_text(json.dumps(records, indent=2))
                print("done")
            except Exception as exc:
                print(f"ERROR: {exc}", file=sys.stderr)

            if args.delay > 0:
                time.sleep(args.delay)

    print("\nExtraction complete.")


if __name__ == "__main__":
    main()
