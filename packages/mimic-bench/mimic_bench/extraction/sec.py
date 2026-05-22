"""SEC EDGAR helpers for fetching 8-K filings and 10-Q text.

Uses the free SEC EDGAR full-text search API (https://efts.sec.gov/LATEST/search-index).
No authentication required.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional
from urllib.parse import urlencode

try:
    import requests  # type: ignore
except ImportError:
    requests = None  # type: ignore

_EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
_EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_EDGAR_FILING = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}"

_HEADERS = {"User-Agent": "mimic-bench research@example.com"}


def _get(url: str, params: Optional[dict] = None) -> dict:
    if requests is None:
        raise ImportError("pip install requests")
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_cik(ticker: str) -> Optional[int]:
    """Resolve a ticker to a CIK number via SEC EDGAR."""
    data = _get("https://www.sec.gov/cgi-bin/browse-edgar", params={
        "company": ticker,
        "CIK": ticker,
        "type": "",
        "dateb": "",
        "owner": "include",
        "count": "5",
        "search_text": "",
        "action": "getcompany",
        "output": "atom",
    })
    # This endpoint returns atom XML; parse for CIK
    # For production, use https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=AAPL&type=&output=atom
    raise NotImplementedError("Use get_cik_map() for a pre-built mapping")


# Pre-built CIK map for the 20 v0.1 benchmark companies
CIK_MAP: Dict[str, int] = {
    "AAPL": 320193,
    "MSFT": 789019,
    "AMZN": 1018724,
    "TSLA": 1318605,
    "GOOGL": 1652044,
    "NFLX": 1065280,
    "JPM": 19617,
    "GS": 886982,
    "BAC": 70858,
    "WMT": 104169,
    "TGT": 27419,
    "COST": 909832,
    "XOM": 34088,
    "CVX": 93410,
    "F": 37996,
    "GM": 1467858,
    "DAL": 27904,
    "UAL": 100517,
    "JNJ": 200406,
    "DIS": 1001039,
}


def fetch_8k_filings(
    ticker: str,
    after_date: str,
    before_date: str,
    max_results: int = 10,
) -> List[dict]:
    """Return list of 8-K filing metadata for a ticker in a date range.

    Args:
        ticker: Company ticker symbol.
        after_date: Start date in YYYY-MM-DD format.
        before_date: End date in YYYY-MM-DD format.
        max_results: Maximum number of filings to return.

    Returns:
        List of dicts with keys: accession, filing_date, form_type, items, url
    """
    cik = CIK_MAP.get(ticker.upper())
    if cik is None:
        raise ValueError(f"Unknown ticker: {ticker}")

    params = {
        "q": f'"{ticker}"',
        "dateRange": "custom",
        "startdt": after_date,
        "enddt": before_date,
        "forms": "8-K",
        "hits.hits._source": "period_of_report,file_date,entity_name,period_of_report",
        "hits.hits.total.value": max_results,
    }
    # Use submissions endpoint (more reliable)
    url = _EDGAR_SUBMISSIONS.format(cik=cik)
    data = _get(url)

    filings = []
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    for i, form in enumerate(forms):
        if form != "8-K":
            continue
        date = dates[i] if i < len(dates) else ""
        if date < after_date or date > before_date:
            continue
        accession = accessions[i].replace("-", "") if i < len(accessions) else ""
        doc = primary_docs[i] if i < len(primary_docs) else ""
        filings.append({
            "accession": accessions[i],
            "filing_date": date,
            "form_type": form,
            "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}",
        })
        if len(filings) >= max_results:
            break

    return filings


def fetch_10q_text(
    ticker: str,
    year: int,
    quarter: int,
    section: str = "MD&A",
    max_chars: int = 8000,
) -> Optional[str]:
    """Fetch the MD&A or risk factors section from a 10-Q filing.

    Returns truncated text string, or None if not found.
    """
    cik = CIK_MAP.get(ticker.upper())
    if cik is None:
        raise ValueError(f"Unknown ticker: {ticker}")

    # Approximate date range for the quarter
    quarter_end = {1: f"{year}-03-31", 2: f"{year}-06-30", 3: f"{year}-09-30"}
    if quarter not in quarter_end:
        raise ValueError(f"Invalid quarter: {quarter}")

    url = _EDGAR_SUBMISSIONS.format(cik=cik)
    data = _get(url)
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    target_end = quarter_end[quarter]
    for i, form in enumerate(forms):
        if form != "10-Q":
            continue
        date = dates[i] if i < len(dates) else ""
        if date > target_end or date < f"{year - 1}-10-01":
            continue
        accession = accessions[i].replace("-", "") if i < len(accessions) else ""
        doc = primary_docs[i] if i < len(primary_docs) else ""
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}"
        try:
            resp = requests.get(doc_url, headers=_HEADERS, timeout=30)
            resp.raise_for_status()
            text = resp.text
            # Crude section extraction
            idx = text.lower().find("management" if "mda" in section.lower() else section.lower())
            if idx != -1:
                return text[idx: idx + max_chars]
            return text[:max_chars]
        except Exception:
            return None
        finally:
            time.sleep(0.2)

    return None
