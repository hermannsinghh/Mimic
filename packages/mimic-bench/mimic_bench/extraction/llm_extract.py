"""LLM-based structured extraction of corporate response labels.

Uses the Anthropic API (claude-opus-4-7) to extract ground truth labels
from raw SEC filing text and earnings call transcripts.
"""

from __future__ import annotations

import json
from typing import Optional

_EXTRACT_PROMPT = """\
You are a financial research assistant extracting structured corporate-response data.

Event: {event_title} ({event_date})
Observation window: {date_start} to {date_end}
Event context: {event_description}

Company: {company_name} ({ticker})
Sector: {sector}

Source material provided:
<source>
{source_text}
</source>

Based ONLY on the source material above, extract what this company actually did in response \
to the event during each time window. If a window has no documented action, use null.
Be precise and factual — do not infer beyond what the source states.

Return a single JSON object — no prose, no markdown fences:
{{
  "event_id": "{event_id}",
  "ticker": "{ticker}",
  "actual_action_0_24h": "<string or null>",
  "actual_action_1_7d": "<string or null>",
  "actual_action_8_30d": "<string or null>",
  "financial_impact_usdM": <float or null>,
  "financial_impact_reported": <true|false>,
  "source_type": "<8k|10q|earnings_call|press_release|news>",
  "confidence": <float 0.0-1.0>
}}"""


def extract_label(
    event: dict,
    company: dict,
    source_text: str,
    client=None,
    model: str = "claude-opus-4-7",
) -> dict:
    """Extract a structured ground truth label from source text.

    Args:
        event: Event dict (from data/events/).
        company: Company dict with ticker, name, sector.
        source_text: Raw text from an 8-K filing or earnings call transcript.
        client: anthropic.Anthropic() instance. Created automatically if None.
        model: Claude model to use.

    Returns:
        Structured label dict matching the labels_v1.jsonl schema.
    """
    if client is None:
        try:
            import anthropic

            client = anthropic.Anthropic()
        except ImportError:
            raise ImportError("pip install anthropic")

    dr = event.get("date_range", {})
    prompt = _EXTRACT_PROMPT.format(
        event_title=event["title"],
        event_date=event["date"],
        date_start=dr.get("start", event["date"]),
        date_end=dr.get("end", event.get("end_date", event["date"])),
        event_description=event["description"],
        company_name=company["name"],
        ticker=company["ticker"],
        sector=company["sector"],
        event_id=event["id"],
        source_text=source_text[:10000],
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result = json.loads(text[start:end])
    result.setdefault("extraction_method", f"llm_{model}")
    result.setdefault("human_reviewed", False)
    result.setdefault("source_url", None)
    return result


def extract_without_source(
    event: dict,
    company: dict,
    client=None,
    model: str = "claude-opus-4-7",
) -> dict:
    """Extract label using model's parametric knowledge (no source text).

    Lower confidence (0.7–0.85) than source-grounded extraction.
    Used when no 8-K or transcript is available.
    """
    synthetic_source = (
        f"[No primary source available. Use your knowledge of {company['ticker']}'s "
        f"documented public response to {event['title']} ({event['date']}).]"
    )
    result = extract_label(event, company, synthetic_source, client=client, model=model)
    # Downgrade confidence for knowledge-only extractions
    if result.get("confidence", 1.0) > 0.85:
        result["confidence"] = 0.82
    result["extraction_method"] = f"llm_{model}_no_source"
    return result
