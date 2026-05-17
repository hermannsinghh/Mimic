"""Shared fixtures for the test suite."""
from __future__ import annotations
import pytest
from datetime import date
from mimic.core.context import (
    CompanyContext, FinancialSnapshot, SupplierGraph,
    StrategicProfile, HistoricalBehavior,
)


@pytest.fixture
def financials():
    return FinancialSnapshot(
        revenue_ttm=648_125.0,
        cogs_ttm=487_988.0,
        operating_margin=0.042,
        ebitda=32_000.0,
        cash=8_885.0,
        total_debt=36_132.0,
        inventory_value=56_576.0,
        inventory_turnover_days=42.3,
        fx_exposure={"EUR": 0.08, "GBP": 0.05, "CAD": 0.06},
        capex_ttm=16_857.0,
    )


@pytest.fixture
def context(financials):
    return CompanyContext(
        ticker="WMT",
        name="Walmart Inc.",
        sector="Consumer Staples",
        industry="Discount Stores",
        as_of=date(2024, 1, 31),
        market_cap=450_000.0,
        employees=2_100_000,
        cik="0000104169",
        financials=financials,
        suppliers=SupplierGraph(
            tier1_suppliers=["P&G", "Unilever", "Kraft Heinz"],
            geographic_concentration={"China": 0.30, "USA": 0.50, "Vietnam": 0.20},
            single_source_components=[],
            top_customers={},
        ),
        strategy=StrategicProfile(
            stated_strategy="Everyday low prices through supply chain efficiency.",
            risk_factors=["Supply chain disruption", "FX headwinds", "Labor costs"],
            competitive_moat="Scale and logistics network",
            capital_allocation_priorities=["capex", "dividends", "buybacks"],
        ),
        behavior=HistoricalBehavior(
            decision_speed="fast",
            risk_appetite=0.35,
            typical_hedging_approach="Partial FX hedging via forwards",
        ),
    )
