"""
Twin — the main user-facing class.

Usage:
    twin = Twin.from_ticker("WMT")
    result = twin.simulate("China port closes for 30 days")
    print(result.decision)
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from pydantic import BaseModel

from mimic.core.context import CompanyContext
from mimic.data.sec import build_context_from_edgar


class Decision(BaseModel):
    """Structured output from a simulation run."""
    ticker: str
    event: str
    immediate_action_0_24h: str
    short_term_action_1_7d: str
    medium_term_action_8_30d: str
    financial_impact_low: float   # $M, P10
    financial_impact_mid: float   # $M, P50
    financial_impact_high: float  # $M, P90
    confidence: float             # 0-1
    reasoning: str
    competitive_response_likely: list[str]
    secondary_risks_created: list[str]
    decision_constraints_hit: list[str]
    model_used: str = "gpt-4o"

    def pretty(self) -> str:
        return (
            f"\n{'='*60}\n"
            f"TWIN SIMULATION: {self.ticker}\n"
            f"EVENT: {self.event}\n"
            f"{'='*60}\n"
            f"0-24h:  {self.immediate_action_0_24h}\n"
            f"1-7d:   {self.short_term_action_1_7d}\n"
            f"8-30d:  {self.medium_term_action_8_30d}\n"
            f"\nFinancial impact (P10/P50/P90): "
            f"${self.financial_impact_low:,.0f}M / "
            f"${self.financial_impact_mid:,.0f}M / "
            f"${self.financial_impact_high:,.0f}M\n"
            f"Confidence: {self.confidence:.0%}\n"
            f"\nReasoning: {self.reasoning}\n"
            f"\nSecondary risks: {', '.join(self.secondary_risks_created)}\n"
            f"{'='*60}\n"
        )


class Twin:
    """
    An LLM-based digital twin of a public company.
    Composes SEC data + foundation model forecasts + economic formulas
    into structured decision outputs.
    """

    def __init__(self, context: CompanyContext):
        self.context = context

    @classmethod
    def from_ticker(
        cls,
        ticker: str,
        as_of: Optional[date] = None,
    ) -> "Twin":
        """
        Build a Twin from a stock ticker symbol.
        Pulls data automatically from SEC EDGAR + yfinance.

        Args:
            ticker: Stock ticker, e.g. "WMT", "AAPL"
            as_of: Date for historical context (default: today)
        """
        raw = build_context_from_edgar(ticker)
        context = CompanyContext.model_validate(raw)
        return cls(context)

    @classmethod
    def from_context(cls, context: CompanyContext) -> "Twin":
        """Build a Twin from a pre-built CompanyContext."""
        return cls(context)

    def simulate(
        self,
        event: str,
        horizon: str = "30d",
        severity: float = 0.7,
        world_state: Optional[dict] = None,
        model: str = "gpt-4o",
    ) -> Decision:
        """
        Simulate how this company would respond to a given event.

        Args:
            event: Natural language event description
            horizon: Time horizon ("24h" | "7d" | "30d" | "90d")
            severity: Event severity 0-1
            world_state: Optional dict with pre-computed macro context
            model: LLM to use for orchestration

        Returns:
            Decision with structured response + financial impact estimates
        """
        from mimic.core.orchestrator import run_orchestrator
        from mimic.formulas import compute_formula_context

        formula_ctx = compute_formula_context(self.context, event, severity)

        decision = run_orchestrator(
            context=self.context,
            event=event,
            severity=severity,
            formula_context=formula_ctx,
            world_state=world_state or {},
            model=model,
        )

        return decision

    def benchmark(self, events: list[dict]) -> list[dict]:
        """
        Run this twin against a list of historical events
        and score against ground truth.

        Each event dict: {description, date, ground_truth_response}
        Returns list of {event, prediction, ground_truth, fidelity_score}
        """
        results = []
        for event in events:
            prediction = self.simulate(event["description"])
            results.append({
                "event": event["description"],
                "date": event.get("date"),
                "prediction": prediction.model_dump(),
                "ground_truth": event.get("ground_truth_response", ""),
                "fidelity_score": None,  # scored by benchmark.scoring module
            })
        return results

    def __repr__(self) -> str:
        return (
            f"Twin({self.context.ticker} | "
            f"{self.context.name} | "
            f"${self.context.market_cap:,.0f}M)"
        )
