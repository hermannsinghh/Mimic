"""
SEC EDGAR ingestion — all free, no API key required.

Endpoints used:
  - https://www.sec.gov/files/company_tickers.json   (ticker → CIK map)
  - https://data.sec.gov/submissions/CIK{cik}.json   (company info + filings)
  - https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json  (financials)
"""
from __future__ import annotations
import httpx
import json
from functools import lru_cache
from datetime import date, datetime
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential

EDGAR_BASE = "https://data.sec.gov"
EDGAR_SUBMISSIONS = f"{EDGAR_BASE}/submissions"
EDGAR_FACTS = f"{EDGAR_BASE}/api/xbrl/companyfacts"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

HEADERS = {
    "User-Agent": "mimic-framework contact@trymimic.dev",  # SEC requires this
    "Accept-Encoding": "gzip, deflate",
}


@lru_cache(maxsize=1)
def _get_ticker_map() -> dict[str, str]:
    """Returns {TICKER: cik_str} mapping. Cached for session."""
    with httpx.Client(headers=HEADERS) as client:
        r = client.get(TICKERS_URL, timeout=30)
        r.raise_for_status()
    raw = r.json()
    # SEC returns {0: {cik_str, ticker, title}, 1: ...}
    return {
        v["ticker"].upper(): str(v["cik_str"]).zfill(10)
        for v in raw.values()
    }


def ticker_to_cik(ticker: str) -> str:
    mapping = _get_ticker_map()
    cik = mapping.get(ticker.upper())
    if not cik:
        raise ValueError(f"Ticker '{ticker}' not found in SEC EDGAR.")
    return cik


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def fetch_company_info(cik: str) -> dict:
    """Fetch company metadata + recent filings index."""
    url = f"{EDGAR_SUBMISSIONS}/CIK{cik}.json"
    with httpx.Client(headers=HEADERS) as client:
        r = client.get(url, timeout=30)
        r.raise_for_status()
    return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def fetch_company_facts(cik: str) -> dict:
    """
    Fetch all XBRL financial facts for a company.
    Returns a dict with keys like 'us-gaap', 'dei'.
    Each key maps to {concept: {label, description, units: {unit: [periods]}}}
    """
    url = f"{EDGAR_FACTS}/CIK{cik}.json"
    with httpx.Client(headers=HEADERS) as client:
        r = client.get(url, timeout=60)
        r.raise_for_status()
    return r.json()


def extract_metric_ttm(
    facts: dict,
    concept: str,
    namespace: str = "us-gaap",
    unit: str = "USD"
) -> Optional[float]:
    """
    Extract the trailing twelve months value for a given XBRL concept.
    Falls back to most recent annual if TTM isn't available.
    Returns value in $M.
    """
    try:
        periods = facts[namespace][concept]["units"][unit]
    except KeyError:
        return None

    # Filter for 10-K annual filings (form == "10-K") and sort by end date
    annual = [
        p for p in periods
        if p.get("form") in ("10-K", "10-K/A")
        and "end" in p
    ]
    if not annual:
        return None

    annual.sort(key=lambda x: x["end"], reverse=True)
    return annual[0]["val"] / 1_000_000  # convert to $M


def build_financial_snapshot(facts: dict) -> dict:
    """
    Build a FinancialSnapshot-compatible dict from EDGAR facts.
    All values in $M.
    """
    def get(concept, namespace="us-gaap", unit="USD"):
        return extract_metric_ttm(facts, concept, namespace, unit) or 0.0

    revenue = (
        get("Revenues")
        or get("RevenueFromContractWithCustomerExcludingAssessedTax")
        or get("SalesRevenueNet")
    )
    cogs = (
        get("CostOfRevenue")
        or get("CostOfGoodsSold")
        or get("CostOfGoodsAndServicesSold")
    )
    ebitda_proxy = get("OperatingIncomeLoss") + get("DepreciationDepletionAndAmortization")
    op_income = get("OperatingIncomeLoss")
    op_margin = (op_income / revenue) if revenue else 0.0

    inventory = (
        get("InventoryNet")
        or get("InventoryFinishedGoodsNetOfReserves")
    )
    inv_days = (inventory / (cogs / 365)) if cogs > 0 and inventory > 0 else 0.0

    cash = get("CashAndCashEquivalentsAtCarryingValue")
    debt = (
        get("LongTermDebt")
        or get("LongTermDebtAndCapitalLeaseObligations")
    )
    capex = abs(get("PaymentsToAcquirePropertyPlantAndEquipment"))

    return {
        "revenue_ttm": revenue,
        "cogs_ttm": cogs,
        "operating_margin": op_margin,
        "ebitda": ebitda_proxy,
        "cash": cash,
        "total_debt": debt,
        "inventory_value": inventory,
        "inventory_turnover_days": inv_days,
        "fx_exposure": {},  # populated later from 10-K text parsing
        "capex_ttm": capex,
    }


def build_context_from_edgar(ticker: str) -> dict:
    """
    Main entry point. Returns a dict compatible with CompanyContext.
    Used by Twin.from_ticker().
    """
    from rich.console import Console
    console = Console()

    console.print(f"[cyan]→ Fetching SEC EDGAR data for {ticker}...[/cyan]")

    cik = ticker_to_cik(ticker)
    console.print(f"  CIK: {cik}")

    info = fetch_company_info(cik)
    console.print(f"  Company: {info.get('name', 'Unknown')}")

    facts = fetch_company_facts(cik)
    financials = build_financial_snapshot(facts)

    console.print(f"  Revenue TTM: ${financials['revenue_ttm']:,.0f}M")
    console.print(f"  Operating Margin: {financials['operating_margin']:.1%}")

    return {
        "ticker": ticker.upper(),
        "name": info.get("name", ""),
        "sector": info.get("sic", ""),        # SIC code for now; map to sector later
        "industry": info.get("sicDescription", ""),
        "as_of": date.today().isoformat(),
        "market_cap": 0.0,                    # filled by yfinance layer
        "employees": info.get("ein", 0),
        "cik": cik,
        "financials": financials,
        "suppliers": {
            "tier1_suppliers": [],
            "geographic_concentration": {},
            "single_source_components": [],
            "top_customers": {},
        },
        "strategy": {
            "stated_strategy": "",
            "risk_factors": [],
            "competitive_moat": "",
            "capital_allocation_priorities": [],
            "recent_guidance": "",
        },
        "behavior": {
            "past_crisis_responses": [],
            "decision_speed": "medium",
            "risk_appetite": 0.5,
            "typical_hedging_approach": "",
        }
    }
