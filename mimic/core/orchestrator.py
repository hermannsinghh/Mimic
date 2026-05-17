"""
Orchestrator — the LLM composition layer.
Takes CompanyContext + formula outputs → structured Decision.
"""
from __future__ import annotations
import json
import os
from typing import Optional
from openai import OpenAI

from mimic.core.context import CompanyContext
from mimic.core.twin import Decision

SYSTEM_PROMPT = """You are simulating the decision-making behavior of a real public company.
You must respond AS THIS COMPANY WOULD — based on their actual financials, strategy, and historical behavior.
You are NOT an AI assistant giving generic advice. You are the company's decision-making system.

Output ONLY a valid JSON object. No prose, no markdown, no explanation outside the JSON.
"""

USER_PROMPT_TEMPLATE = """
# COMPANY PROFILE
{company_summary}

# FULL FINANCIAL CONTEXT
{financial_context}

# STRATEGIC PROFILE
Stated strategy: {strategy}
Risk factors: {risk_factors}
Capital allocation priorities: {capital_allocation}
Risk appetite (0=conservative, 1=aggressive): {risk_appetite}
Typical hedging approach: {hedging}

# ECONOMIC FORMULA OUTPUTS (pre-computed, use these)
{formula_context}

# EVENT
{event}
Severity (0-1): {severity}

# TASK
Decide how {ticker} would respond. Use their historical behavior and financial constraints.
If they lack the cash or capacity for an action, say so explicitly.

Output this exact JSON structure:
{{
  "immediate_action_0_24h": "string",
  "short_term_action_1_7d": "string",
  "medium_term_action_8_30d": "string",
  "financial_impact_low": float,
  "financial_impact_mid": float,
  "financial_impact_high": float,
  "confidence": float,
  "reasoning": "string (max 200 words, step by step)",
  "competitive_response_likely": ["string", ...],
  "secondary_risks_created": ["string", ...],
  "decision_constraints_hit": ["string", ...]
}}

Financial impacts are in $M. Negative = loss. Confidence is 0-1.
"""


def run_orchestrator(
    context: CompanyContext,
    event: str,
    severity: float,
    formula_context: dict,
    world_state: dict,
    model: str = "gpt-4o",
) -> Decision:
    """
    Main orchestrator function.
    Calls the LLM with full context and returns a structured Decision.
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    user_prompt = USER_PROMPT_TEMPLATE.format(
        company_summary=context.summary(),
        financial_context=json.dumps(context.financials.model_dump(), indent=2),
        strategy=context.strategy.stated_strategy[:500] or "Not available",
        risk_factors=", ".join(context.strategy.risk_factors[:5]) or "Not available",
        capital_allocation=", ".join(context.strategy.capital_allocation_priorities),
        risk_appetite=context.behavior.risk_appetite,
        hedging=context.behavior.typical_hedging_approach or "Standard",
        formula_context=json.dumps(formula_context, indent=2),
        event=event,
        severity=severity,
        ticker=context.ticker,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,        # low temp = more deterministic decisions
        response_format={"type": "json_object"},
    )

    raw = json.loads(response.choices[0].message.content)

    return Decision(
        ticker=context.ticker,
        event=event,
        model_used=model,
        **raw,
    )
