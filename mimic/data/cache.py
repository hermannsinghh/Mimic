"""Simple file-based cache for SEC EDGAR + market data."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import date
from typing import Optional

CACHE_DIR = Path.home() / ".mimic" / "cache"


def _daily_path(ticker: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{ticker.upper()}_{date.today().isoformat()}.json"


def _quarterly_path(ticker: str, key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    now = date.today()
    quarter = (now.month - 1) // 3 + 1
    return CACHE_DIR / f"{ticker.upper()}_{now.year}_Q{quarter}_{key}.json"


def load(ticker: str, key: str = "context") -> Optional[dict]:
    path = _quarterly_path(ticker, key) if key == "tenk" else _daily_path(ticker)
    if path.exists():
        return json.loads(path.read_text())
    return None


def save(ticker: str, data: dict, key: str = "context") -> None:
    path = _quarterly_path(ticker, key) if key == "tenk" else _daily_path(ticker)
    path.write_text(json.dumps(data, indent=2, default=str))
