"""yfinance enrichment — market cap, beta, sector, employees."""
from __future__ import annotations
from typing import Optional


def enrich_from_yfinance(ticker: str) -> dict:
    """
    Pull market data from yfinance.
    Returns a partial CompanyContext-compatible dict to be merged in.
    Values: market_cap in $M, beta dimensionless.
    """
    import yfinance as yf

    info = yf.Ticker(ticker).info

    return {
        "market_cap": (info.get("marketCap") or 0) / 1_000_000,
        "sector": info.get("sector") or "",
        "industry": info.get("industry") or "",
        "employees": info.get("fullTimeEmployees") or 0,
        "beta": info.get("beta") or 1.0,
    }
