"""
SEC EDGAR ingestion — all free, no API key required.

Endpoints used:
  - https://www.sec.gov/files/company_tickers.json   (ticker → CIK map)
  - https://data.sec.gov/submissions/CIK{cik}.json   (company info + filings)
  - https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json  (financials)
  - https://www.sec.gov/Archives/edgar/data/...       (10-K documents)
"""
from __future__ import annotations
import json
import os
import re
from functools import lru_cache
from datetime import date
from typing import Optional

import httpx
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
    unit: str = "USD",
) -> Optional[float]:
    """
    Extract the most recent annual value for a given XBRL concept.
    Returns value in $M.
    """
    try:
        periods = facts[namespace][concept]["units"][unit]
    except KeyError:
        return None

    annual = [
        p for p in periods
        if p.get("form") in ("10-K", "10-K/A") and "end" in p
    ]
    if not annual:
        return None

    annual.sort(key=lambda x: x["end"], reverse=True)
    return annual[0]["val"] / 1_000_000


def build_financial_snapshot(facts: dict) -> dict:
    """Build a FinancialSnapshot-compatible dict from EDGAR facts. All values in $M."""
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

    inventory = get("InventoryNet") or get("InventoryFinishedGoodsNetOfReserves")
    inv_days = (inventory / (cogs / 365)) if cogs > 0 and inventory > 0 else 0.0

    cash = get("CashAndCashEquivalentsAtCarryingValue")
    debt = get("LongTermDebt") or get("LongTermDebtAndCapitalLeaseObligations")
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
        "fx_exposure": {},
        "capex_ttm": capex,
    }


# ─────────────────────────────────────────────
# 10-K text extraction
# ─────────────────────────────────────────────

def _find_latest_10k(submissions: dict) -> Optional[tuple[str, str]]:
    """Return (accession_no_dashes, primary_doc) for the most recent 10-K."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])

    for i, form in enumerate(forms):
        if form == "10-K":
            return accessions[i].replace("-", ""), docs[i]
    return None


def _strip_html(html: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s{3,}", "\n\n", text)
    return text.strip()


def _extract_item_section(text: str, item: str, next_item: str) -> str:
    """Extract a specific Item section from 10-K plain text (up to 12k chars)."""
    pattern = (
        rf"Item\s+{re.escape(item)}[\.\s][^\n]{{0,120}}\n"
        rf"(.*?)"
        rf"(?=Item\s+{re.escape(next_item)}[\.\s])"
    )
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()[:12_000]
    return ""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def fetch_10k_sections(cik: str, submissions: dict) -> dict[str, str]:
    """
    Fetch the most recent 10-K and extract Item 1 (Business) and Item 1A (Risk Factors).
    Returns {"item1": str, "item1a": str}. Empty strings on failure.
    """
    result = _find_latest_10k(submissions)
    if not result:
        return {"item1": "", "item1a": ""}

    accession, doc = result
    cik_int = str(int(cik))
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{doc}"

    try:
        with httpx.Client(headers=HEADERS) as client:
            r = client.get(url, timeout=60)
            r.raise_for_status()
        text = _strip_html(r.text)
    except Exception:
        return {"item1": "", "item1a": ""}

    return {
        "item1": _extract_item_section(text, "1", "1A"),
        "item1a": _extract_item_section(text, "1A", "1B"),
    }


def extract_strategy_with_llm(sections: dict[str, str], ticker: str) -> dict:
    """
    Use GPT-4o-mini to extract structured strategic data from 10-K sections.
    Returns a StrategicProfile-compatible dict. Falls back to empty values on error.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not (sections.get("item1") or sections.get("item1a")):
        return {
            "stated_strategy": "",
            "risk_factors": [],
            "competitive_moat": "",
            "capital_allocation_priorities": [],
        }

    from openai import OpenAI

    combined = (
        f"[Item 1 — Business]\n{sections['item1'][:8000]}\n\n"
        f"[Item 1A — Risk Factors]\n{sections['item1a'][:6000]}"
    )

    client = OpenAI(api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract structured strategy data from 10-K text. "
                        "Return valid JSON only — no prose."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Company: {ticker}\n\n{combined}\n\n"
                        "Return this JSON structure:\n"
                        "{\n"
                        '  "stated_strategy": "2-3 sentence summary",\n'
                        '  "risk_factors": ["top risk 1", "top risk 2", ...],\n'
                        '  "competitive_moat": "what gives this company durable advantage",\n'
                        '  "capital_allocation_priorities": ["e.g. buybacks", "R&D", ...]\n'
                        "}"
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {
            "stated_strategy": "",
            "risk_factors": [],
            "competitive_moat": "",
            "capital_allocation_priorities": [],
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
        "sector": info.get("sic", ""),
        "industry": info.get("sicDescription", ""),
        "as_of": date.today().isoformat(),
        "market_cap": 0.0,
        "employees": 0,
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
        },
        # Pass through raw objects needed for enrichment
        "_submissions": info,
        "_cik": cik,
    }
