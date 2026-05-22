"""Tests for SEC EDGAR XBRL financial parsing."""
from __future__ import annotations

from mimic.data.sec import (
    build_financial_snapshot,
    extract_metric_annual,
    extract_metric_first,
    unwrap_company_facts,
)


def _make_facts(concept: str, val: float, end: str = "2025-01-31") -> dict:
    return {
        "facts": {
            "us-gaap": {
                concept: {
                    "units": {
                        "USD": [
                            {
                                "val": val,
                                "end": end,
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2025-03-01",
                            }
                        ]
                    }
                }
            }
        }
    }


def test_unwrap_company_facts():
    inner = {"us-gaap": {}}
    assert unwrap_company_facts({"facts": inner}) == inner
    assert unwrap_company_facts(inner) == inner


def test_extract_metric_annual_from_wrapped_payload():
    payload = _make_facts("Revenues", 500_000_000_000)
    assert extract_metric_annual(payload["facts"], "Revenues") == 500_000.0


def test_build_financial_snapshot_unwraps_facts_key():
    payload = _make_facts("Revenues", 100_000_000_000)
    payload["facts"]["us-gaap"]["CostOfRevenue"] = {
        "units": {
            "USD": [
                {
                    "val": 70_000_000_000,
                    "end": "2025-01-31",
                    "fp": "FY",
                    "form": "10-K",
                }
            ]
        }
    }
    payload["facts"]["us-gaap"]["OperatingIncomeLoss"] = {
        "units": {
            "USD": [
                {
                    "val": 10_000_000_000,
                    "end": "2025-01-31",
                    "fp": "FY",
                    "form": "10-K",
                }
            ]
        }
    }
    snap = build_financial_snapshot(payload)
    assert snap["revenue_ttm"] == 100_000.0
    assert snap["cogs_ttm"] == 70_000.0
    assert snap["operating_margin"] == 0.1


def test_extract_metric_first_fallback_concepts():
    facts = {
        "us-gaap": {
            "SalesRevenueNet": {
                "units": {
                    "USD": [
                        {
                            "val": 42_000_000_000,
                            "end": "2024-12-31",
                            "fp": "FY",
                            "form": "10-K",
                        }
                    ]
                }
            }
        }
    }
    assert extract_metric_first(facts, ["Revenues", "SalesRevenueNet"]) == 42_000.0


def test_build_financial_snapshot_empty_payload():
    snap = build_financial_snapshot({"facts": {"us-gaap": {}}})
    assert snap["revenue_ttm"] == 0.0
