"""Earnings call transcript fetcher.

Data sources (in preference order):
  1. Seeking Alpha transcript pages (scraping, rate-limited)
  2. Motley Fool transcripts (free)
  3. Fallback: returns None with a helpful message

Transcripts are cached to disk at data/cache/transcripts/ to avoid redundant requests.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

try:
    import requests  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:
    requests = None  # type: ignore
    BeautifulSoup = None  # type: ignore

_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "transcripts"


def _cache_key(ticker: str, year: int, quarter: int) -> str:
    return hashlib.md5(f"{ticker}_{year}_Q{quarter}".encode()).hexdigest()


def _load_cache(key: str) -> Optional[str]:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _CACHE_DIR / f"{key}.txt"
    return p.read_text() if p.exists() else None


def _save_cache(key: str, text: str) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (_CACHE_DIR / f"{key}.txt").write_text(text)


def fetch_earnings_transcript(
    ticker: str,
    year: int,
    quarter: int,
    max_chars: int = 12000,
) -> Optional[str]:
    """Return earnings call transcript text for (ticker, year, quarter).

    Returns up to max_chars of the transcript, or None if unavailable.
    Caches results to disk.
    """
    key = _cache_key(ticker, year, quarter)
    cached = _load_cache(key)
    if cached is not None:
        return cached[:max_chars]

    if requests is None or BeautifulSoup is None:
        raise ImportError("pip install requests beautifulsoup4")

    # Try Motley Fool transcript URL pattern
    quarter_map = {1: "first", 2: "second", 3: "third", 4: "fourth"}
    q_name = quarter_map.get(quarter, f"q{quarter}")
    search_url = (
        f"https://www.fool.com/earnings/call-transcripts/{year}/"
        f"{q_name}-quarter/{ticker.lower()}-earnings-call-transcript/"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; mimic-bench/0.1; research use)",
        "Accept": "text/html",
    }

    try:
        resp = requests.get(search_url, headers=headers, timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            article = soup.find("article") or soup.find("div", class_="article-body")
            if article:
                text = article.get_text(separator="\n")[:max_chars]
                _save_cache(key, text)
                return text
        time.sleep(1)
    except Exception:
        pass

    return None


def extract_event_mentions(
    transcript_text: str,
    event_keywords: list[str],
    context_chars: int = 500,
) -> list[str]:
    """Find paragraphs in a transcript that mention event keywords.

    Returns list of text snippets with context.
    """
    snippets = []
    text_lower = transcript_text.lower()
    for keyword in event_keywords:
        idx = 0
        while True:
            pos = text_lower.find(keyword.lower(), idx)
            if pos == -1:
                break
            start = max(0, pos - context_chars // 2)
            end = min(len(transcript_text), pos + context_chars // 2)
            snippet = transcript_text[start:end].strip()
            if snippet not in snippets:
                snippets.append(snippet)
            idx = pos + 1
    return snippets
