"""MimicBench — evaluate any twin (or callable) against the ground truth dataset."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

from .datasets import get_company_map, load_events, load_ground_truth
from .scoring import aggregate_scores, fidelity_score

_PROMPT_TEMPLATE = """\
You are analyzing how a specific company responded to a major macro event.

Event: {event_title} ({event_date})
Category: {event_category} | Severity: {event_severity_pct}%
{event_description}

Company: {company_name} ({ticker})
Sector: {sector} | Industry: {industry}

Based on your knowledge of this historical event and this company's documented actions \
(SEC 8-K filings, earnings call transcripts, press releases), predict what the company \
actually did in response.

Respond ONLY with a JSON object — no prose, no markdown fences:
{{
  "action_0_24h": "<string: what the company announced/did in the first 24 hours, or null>",
  "action_1_7d": "<string: key actions taken in days 1–7, or null>",
  "action_8_30d": "<string: actions and disclosures in days 8–30, or null>",
  "financial_impact_usdM": <float: estimated $ impact in millions, negative = loss, or null>,
  "direction": "<positive|negative|neutral|mixed>",
  "primary_timing_window": "<action_0_24h|action_1_7d|action_8_30d>",
  "reasoning": "<one sentence explaining your prediction>"
}}"""


class BenchmarkResult:
    def __init__(self, results: List[dict]):
        self.results = results
        self.summary = aggregate_scores(results)
        self.fidelity_score = self.summary.get("overall", {}).get("mean", 0.0)

    def __repr__(self) -> str:
        n = len(self.results)
        errors = sum(1 for r in self.results if "error" in r)
        return (
            f"BenchmarkResult(n={n}, errors={errors}, "
            f"fidelity={self.fidelity_score:.3f})"
        )

    def by_category(self) -> Dict[str, float]:
        return {k: v["mean"] for k, v in self.summary.get("by_category", {}).items()}

    def worst_events(self, n: int = 5) -> List[dict]:
        by_event = self.summary.get("by_event", {})
        ranked = sorted(by_event.items(), key=lambda x: x[1]["mean"])
        return [{"event_id": eid, **stats} for eid, stats in ranked[:n]]

    def best_events(self, n: int = 5) -> List[dict]:
        by_event = self.summary.get("by_event", {})
        ranked = sorted(by_event.items(), key=lambda x: x[1]["mean"], reverse=True)
        return [{"event_id": eid, **stats} for eid, stats in ranked[:n]]

    def to_dict(self) -> dict:
        return {"results": self.results, "summary": self.summary}

    def to_json(self, path: Optional[Union[str, Path]] = None) -> str:
        text = json.dumps(self.to_dict(), indent=2)
        if path:
            Path(path).write_text(text)
        return text


class Benchmark:
    """Main benchmark class.

    Usage:
        bench = Benchmark.load("v1")
        results = bench.run(predict_fn, subset="supply_chain")

    The ``predict_fn`` is any callable that takes a prompt string and returns
    a raw string response containing a JSON object.  Pass a ``mimic.Twin``
    directly — it will be auto-wrapped.
    """

    def __init__(
        self,
        predict_fn: Callable[[str], str],
        data_dir: Optional[Path] = None,
        gt_version: str = "v1",
    ):
        self.predict_fn = predict_fn
        self._data_dir = data_dir
        self.events = load_events(data_dir)
        self.ground_truth = load_ground_truth(gt_version, data_dir)
        self.companies = get_company_map(data_dir)

    @classmethod
    def load(
        cls,
        gt_version: str = "v1",
        predict_fn: Optional[Callable[[str], str]] = None,
        data_dir: Optional[Path] = None,
    ) -> "Benchmark":
        if predict_fn is None:
            raise ValueError("Pass predict_fn=<callable> or a mimic.Twin")
        return cls(predict_fn, data_dir=data_dir, gt_version=gt_version)

    def run(
        self,
        predict_fn: Optional[Callable[[str], str]] = None,
        *,
        subset: Optional[str] = None,
        event_ids: Optional[List[str]] = None,
        tickers: Optional[List[str]] = None,
        delay: float = 0.5,
        verbose: bool = False,
    ) -> BenchmarkResult:
        """Run the benchmark.

        Args:
            predict_fn: Override the stored callable for this run.
            subset: Filter events by category (e.g. "supply_chain", "macro").
            event_ids: Explicit list of event IDs to evaluate.
            tickers: Explicit list of company tickers to evaluate.
            delay: Seconds to sleep between API calls (rate limiting).
            verbose: Print per-pair progress.
        """
        fn = predict_fn or self.predict_fn
        if fn is None:
            raise ValueError("No predict_fn provided")

        # Resolve target events
        all_events = list(self.events.values())
        if event_ids:
            all_events = [e for e in all_events if e["id"] in event_ids]
        elif subset:
            all_events = [e for e in all_events if e.get("category") == subset]
        all_events.sort(key=lambda e: e["date"])

        results: List[dict] = []

        for event in all_events:
            eid = event["id"]
            gt_event = self.ground_truth.get(eid, {})
            target_tickers = tickers or sorted(gt_event.keys())

            for ticker in target_tickers:
                if ticker not in gt_event:
                    continue
                gt = gt_event[ticker]
                company = self.companies.get(ticker, {"name": ticker, "sector": "unknown", "industry": "unknown"})

                prompt = _PROMPT_TEMPLATE.format(
                    event_title=event["title"],
                    event_date=event["date"],
                    event_category=event.get("category", ""),
                    event_severity_pct=int(event.get("severity", 0.5) * 100),
                    event_description=event["description"],
                    company_name=company["name"],
                    ticker=ticker,
                    sector=company["sector"],
                    industry=company.get("industry", ""),
                )

                if verbose:
                    print(f"  {eid} / {ticker} ... ", end="", flush=True)

                try:
                    raw = fn(prompt)
                    prediction = _parse_json(raw)
                    score = fidelity_score(prediction, gt)
                    results.append(
                        {
                            "event_id": eid,
                            "event_category": event.get("category", "unknown"),
                            "ticker": ticker,
                            "sector": company["sector"],
                            "prediction": prediction,
                            "ground_truth": {
                                "actual_action_0_24h": gt.get("actual_action_0_24h"),
                                "actual_action_1_7d": gt.get("actual_action_1_7d"),
                                "actual_action_8_30d": gt.get("actual_action_8_30d"),
                                "financial_impact_usdM": gt.get("financial_impact_usdM"),
                            },
                            "score": score,
                        }
                    )
                    if verbose:
                        print(f"fidelity={score['composite']:.3f}")
                except Exception as exc:
                    results.append(
                        {
                            "event_id": eid,
                            "event_category": event.get("category", "unknown"),
                            "ticker": ticker,
                            "sector": company["sector"],
                            "error": str(exc),
                            "score": {"composite": 0.0, "components": {}},
                        }
                    )
                    if verbose:
                        print(f"ERROR: {exc}")

                if delay > 0:
                    time.sleep(delay)

        return BenchmarkResult(results)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if "```" in raw:
        start = raw.find("{", raw.find("```"))
        end = raw.rfind("}") + 1
        raw = raw[start:end]
    elif "{" in raw:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        raw = raw[start:end]
    return json.loads(raw)


# Convenience alias
MimicBench = Benchmark
