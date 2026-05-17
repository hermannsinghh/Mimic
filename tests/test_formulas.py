"""Tests for the economic formulas library."""
from __future__ import annotations
import pytest
from mimic.formulas import (
    dcf_impact,
    altman_z,
    cogs_sensitivity,
    fx_passthrough,
    inventory_burn,
    bayes_update,
    capm_response,
    operating_leverage,
    supplier_hhi,
    cascade_propagate,
    compute_formula_context,
)


def test_dcf_impact_negative_shock():
    result = dcf_impact(base_fcf=1_000, shock_pct=-0.20)
    assert result["formula"] == "DCF"
    assert result["ev_delta_usdM"] < 0
    assert result["base_ev_usdM"] > result["shocked_ev_usdM"]
    assert result["ev_delta_pct"] == pytest.approx(-0.20, abs=0.01)


def test_dcf_impact_positive_shock():
    result = dcf_impact(base_fcf=500, shock_pct=0.10)
    assert result["ev_delta_usdM"] > 0


def test_altman_z_safe_zone():
    result = altman_z(
        working_capital=5_000,
        retained_earnings=20_000,
        ebit=3_000,
        market_cap=50_000,
        sales=40_000,
        total_assets=30_000,
        total_liabilities=10_000,
    )
    assert result["formula"] == "Altman-Z"
    assert result["zone"] == "safe"
    assert result["z_score"] > 2.99


def test_altman_z_zero_assets():
    result = altman_z(0, 0, 0, 0, 0, 0, 0)
    assert result["z_score"] is None
    assert result["zone"] == "unknown"


def test_cogs_sensitivity():
    result = cogs_sensitivity(
        revenue=650_000,
        cogs=490_000,
        input_shock_pct=0.15,
        passthrough_rate=0.40,
    )
    assert result["formula"] == "COGS_Sensitivity"
    assert result["margin_compression"] > 0
    assert result["annual_ebitda_impact_usdM"] < 0
    assert result["base_gross_margin"] > result["new_gross_margin"]


def test_fx_passthrough():
    result = fx_passthrough(
        revenue=100_000,
        fx_exposure={"EUR": 0.20, "GBP": 0.10},
        fx_moves={"EUR": -0.05, "GBP": -0.03},
    )
    assert result["formula"] == "FX_Passthrough"
    assert result["total_revenue_impact_usdM"] < 0
    assert "EUR" in result["breakdown_by_currency"]
    assert "GBP" in result["breakdown_by_currency"]


def test_inventory_burn_high_demand():
    result = inventory_burn(inventory_days=30, demand_multiplier=2.0)
    assert result["formula"] == "Inventory_Burn"
    assert result["effective_days_remaining"] == 15.0
    assert result["restocking_urgency"] is True


def test_inventory_burn_low_demand():
    result = inventory_burn(inventory_days=30, demand_multiplier=0.5)
    assert result["effective_days_remaining"] == 60.0
    assert result["restocking_urgency"] is False


def test_bayes_update_increases_probability():
    result = bayes_update(prior=0.3, likelihood_given_true=0.8, likelihood_given_false=0.2)
    assert result["formula"] == "Bayesian_Update"
    assert result["posterior"] > result["prior"]
    assert result["direction"] == "up"


def test_bayes_update_decreases_probability():
    result = bayes_update(prior=0.8, likelihood_given_true=0.1, likelihood_given_false=0.9)
    assert result["posterior"] < result["prior"]
    assert result["direction"] == "down"


def test_capm_response():
    result = capm_response(beta=1.5, market_return=0.10, risk_free_rate=0.05)
    assert result["formula"] == "CAPM"
    # CAPM: rf + beta*(rm - rf) = 0.05 + 1.5*(0.10-0.05) = 0.125
    assert result["expected_return"] == pytest.approx(0.125, abs=0.001)


def test_operating_leverage():
    result = operating_leverage(
        revenue=100_000,
        variable_costs=60_000,
        fixed_costs=20_000,
        revenue_change_pct=0.10,
    )
    assert result["formula"] == "Operating_Leverage"
    assert result["degree_of_operating_leverage"] > 1
    assert result["new_op_income_usdM"] > result["base_op_income_usdM"]


def test_supplier_hhi_high_concentration():
    result = supplier_hhi({"China": 80, "USA": 20})
    assert result["formula"] == "HHI"
    assert result["risk_level"] == "high"
    assert result["most_concentrated"] == "China"


def test_supplier_hhi_diversified():
    shares = {f"Country{i}": 1 for i in range(20)}
    result = supplier_hhi(shares)
    assert result["risk_level"] == "diversified"


def test_supplier_hhi_zero():
    result = supplier_hhi({})
    assert result["hhi"] == 0
    assert result["risk_level"] == "unknown"


def test_cascade_propagate():
    result = cascade_propagate(initial_shock=0.8, n_tiers=3, amplification_risk=0.3)
    assert result["formula"] == "Cascade_Propagation"
    assert "tier_1" in result["tier_impacts"]
    assert "tier_2" in result["tier_impacts"]
    assert "tier_3" in result["tier_impacts"]
    assert result["amplification_triggered"] is True
    assert result["total_system_shock"] > result["initial_shock"]


def test_compute_formula_context(context):
    results = compute_formula_context(context, "Tariff shock", severity=0.6)
    assert "dcf" in results
    assert "cogs_sensitivity" in results
    assert "cascade" in results
    assert "bayes_escalation" in results
