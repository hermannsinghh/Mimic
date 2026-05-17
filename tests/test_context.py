"""Tests for CompanyContext and its component models."""
from __future__ import annotations
import pytest
from datetime import date
from mimic.core.context import (
    CompanyContext, FinancialSnapshot, SupplierGraph,
    StrategicProfile, HistoricalBehavior,
)


def test_financial_snapshot_gross_margin(financials):
    gm = financials.gross_margin
    expected = (648_125.0 - 487_988.0) / 648_125.0
    assert gm == pytest.approx(expected, abs=1e-6)


def test_financial_snapshot_net_debt(financials):
    assert financials.net_debt == pytest.approx(36_132.0 - 8_885.0, abs=0.1)


def test_financial_snapshot_zero_revenue():
    snap = FinancialSnapshot(
        revenue_ttm=0, cogs_ttm=0, operating_margin=0,
        ebitda=0, cash=100, total_debt=200,
        inventory_value=0, inventory_turnover_days=0,
    )
    assert snap.gross_margin == 0.0


def test_supplier_concentration_flag():
    sg = SupplierGraph(geographic_concentration={"China": 0.55, "USA": 0.45})
    assert sg.is_geographically_concentrated is True


def test_supplier_not_concentrated():
    sg = SupplierGraph(geographic_concentration={"China": 0.30, "USA": 0.35, "Mexico": 0.35})
    assert sg.is_geographically_concentrated is False


def test_context_summary_contains_ticker(context):
    summary = context.summary()
    assert "WMT" in summary
    assert "Walmart" in summary


def test_context_summary_contains_key_metrics(context):
    summary = context.summary()
    assert "market cap" in summary.lower() or "$" in summary
    assert "days on hand" in summary


def test_context_model_dump_roundtrip(context):
    dumped = context.model_dump()
    restored = CompanyContext.model_validate(dumped)
    assert restored.ticker == context.ticker
    assert restored.financials.revenue_ttm == context.financials.revenue_ttm


def test_context_fx_exposure_default():
    snap = FinancialSnapshot(
        revenue_ttm=1000, cogs_ttm=600, operating_margin=0.1,
        ebitda=150, cash=50, total_debt=100,
        inventory_value=80, inventory_turnover_days=30,
    )
    assert snap.fx_exposure == {}


def test_historical_behavior_risk_appetite_bounds():
    with pytest.raises(Exception):
        HistoricalBehavior(risk_appetite=1.5)
    with pytest.raises(Exception):
        HistoricalBehavior(risk_appetite=-0.1)
