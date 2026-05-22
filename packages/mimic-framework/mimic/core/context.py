"""
CompanyContext — the structured data backbone of every Twin.
Auto-populated from free public sources (SEC EDGAR, yfinance, FRED).
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class FinancialSnapshot(BaseModel):
    revenue_ttm: float = Field(description="Trailing 12-month revenue, $M")
    cogs_ttm: float = Field(description="Trailing 12-month cost of goods sold, $M")
    operating_margin: float = Field(description="Operating income / revenue, 0-1")
    ebitda: float = Field(description="EBITDA, $M")
    cash: float = Field(description="Cash + equivalents, $M")
    total_debt: float = Field(description="Total debt, $M")
    inventory_value: float = Field(description="Inventory on balance sheet, $M")
    inventory_turnover_days: float = Field(description="Days of inventory on hand")
    fx_exposure: dict[str, float] = Field(
        default_factory=dict,
        description="Currency -> % of revenue denominated in that currency"
    )
    capex_ttm: float = Field(default=0.0, description="Capital expenditures TTM, $M")

    @property
    def net_debt(self) -> float:
        return self.total_debt - self.cash

    @property
    def gross_margin(self) -> float:
        if self.revenue_ttm == 0:
            return 0.0
        return (self.revenue_ttm - self.cogs_ttm) / self.revenue_ttm


class SupplierGraph(BaseModel):
    tier1_suppliers: list[str] = Field(default_factory=list)
    geographic_concentration: dict[str, float] = Field(
        default_factory=dict,
        description="Country -> % of COGS sourced from there"
    )
    single_source_components: list[str] = Field(default_factory=list)
    top_customers: dict[str, float] = Field(
        default_factory=dict,
        description="Customer name -> % of revenue"
    )

    @property
    def is_geographically_concentrated(self) -> bool:
        """True if any single country > 40% of supply."""
        return any(v > 0.4 for v in self.geographic_concentration.values())


class StrategicProfile(BaseModel):
    stated_strategy: str = Field(
        default="",
        description="Pulled verbatim from 10-K Item 1 Business section"
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        description="Top risk factors from 10-K Item 1A"
    )
    competitive_moat: str = Field(default="")
    capital_allocation_priorities: list[str] = Field(
        default_factory=list,
        description="e.g. ['buybacks', 'R&D', 'debt reduction', 'M&A']"
    )
    recent_guidance: str = Field(
        default="",
        description="Latest earnings call forward guidance"
    )


class HistoricalBehavior(BaseModel):
    past_crisis_responses: list[dict] = Field(
        default_factory=list,
        description="List of {event, response, source, date} dicts"
    )
    decision_speed: str = Field(
        default="medium",
        description="'fast' | 'medium' | 'slow' — how quickly mgmt acts"
    )
    risk_appetite: float = Field(
        default=0.5,
        ge=0, le=1,
        description="0 = very conservative, 1 = aggressive"
    )
    typical_hedging_approach: str = Field(
        default="",
        description="e.g. 'hedges 80% of FX exposure 12mo forward'"
    )


class CompanyContext(BaseModel):
    """
    Complete structured representation of a company.
    Serves as the persona for an LLM twin agent.
    """
    ticker: str
    name: str
    sector: str
    industry: str
    as_of: date
    market_cap: float = Field(description="Market cap in $M")
    employees: int = Field(default=0)
    cik: str = Field(default="", description="SEC CIK number")

    financials: FinancialSnapshot
    suppliers: SupplierGraph
    strategy: StrategicProfile
    behavior: HistoricalBehavior

    def summary(self) -> str:
        """Human-readable one-paragraph summary for prompt injection."""
        return (
            f"{self.name} ({self.ticker}) is a {self.industry} company in the "
            f"{self.sector} sector with ${self.market_cap:,.0f}M market cap. "
            f"Revenue TTM: ${self.financials.revenue_ttm:,.0f}M. "
            f"Gross margin: {self.financials.gross_margin:.1%}. "
            f"Net debt: ${self.financials.net_debt:,.0f}M. "
            f"Inventory: {self.financials.inventory_turnover_days:.0f} days on hand. "
            f"Primary supply geography: "
            f"{max(self.suppliers.geographic_concentration, key=self.suppliers.geographic_concentration.get, default='unknown')}."
        )
