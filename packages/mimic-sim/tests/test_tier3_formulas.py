"""Tests for the Tier 3 formula engine."""

import numpy as np
import pytest

from mimic_sim.execution.tier3_formulas import (
    CompanyProfile,
    RunOutcome,
    _base_revenue_impact,
    _intervention_dampening,
    _macro_impact,
    simulate_company,
    run_tier3,
)
from mimic_sim.parameter_space import ParameterSpace, Distribution


def _make_params(
    severity=0.7,
    duration_days=30.0,
    oil=85.0,
    fx=7.3,
    intervention=False,
    seed=0,
):
    space = ParameterSpace(
        severity=Distribution.constant(severity),
        duration_days=Distribution.constant(duration_days),
        macro_conditions={
            "oil_price": Distribution.constant(oil),
            "usd_cny": Distribution.constant(fx),
        },
    )
    space.intervention_probability = 1.0 if intervention else 0.0
    batch = space.sample_batch(1, seed=seed)
    return batch[0]


class TestBaseRevenueImpact:
    def test_higher_severity_higher_impact(self):
        profile = CompanyProfile.walmart()
        low = _base_revenue_impact(profile, _make_params(severity=0.3))
        high = _base_revenue_impact(profile, _make_params(severity=0.9))
        assert high > low

    def test_longer_duration_higher_impact(self):
        profile = CompanyProfile.apple()
        short = _base_revenue_impact(profile, _make_params(duration_days=7))
        long_ = _base_revenue_impact(profile, _make_params(duration_days=90))
        assert long_ > short

    def test_impact_bounded(self):
        profile = CompanyProfile.walmart()
        impact = _base_revenue_impact(profile, _make_params(severity=1.0, duration_days=365))
        assert 0.0 <= impact <= 0.85


class TestMacroImpact:
    def test_high_oil_increases_fedex_impact(self):
        profile = CompanyProfile.fedex()
        low_oil = _macro_impact(profile, _make_params(oil=60))
        high_oil = _macro_impact(profile, _make_params(oil=120))
        assert high_oil > low_oil

    def test_baseline_macro_near_zero(self):
        profile = CompanyProfile.walmart()
        impact = _macro_impact(profile, _make_params(oil=85.0, fx=7.3))
        assert abs(impact) < 1e-9


class TestInterventionDampening:
    def test_intervention_reduces_impact(self):
        params_no_int = _make_params(intervention=False)
        params_int = _make_params(intervention=True)
        assert _intervention_dampening(params_int) < _intervention_dampening(params_no_int)

    def test_no_intervention_is_one(self):
        assert _intervention_dampening(_make_params(intervention=False)) == 1.0


class TestSimulateCompany:
    def test_financial_impact_negative(self):
        profile = CompanyProfile.walmart()
        params = _make_params()
        outcome = simulate_company(profile, params)
        assert outcome.financial_impact < 0

    def test_outcome_has_action(self):
        profile = CompanyProfile.apple()
        outcome = simulate_company(profile, _make_params())
        assert isinstance(outcome.action_taken, str)
        assert len(outcome.action_taken) > 0

    def test_recovery_time_positive(self):
        profile = CompanyProfile.fedex()
        outcome = simulate_company(profile, _make_params())
        assert outcome.recovery_time_days > 0

    def test_higher_severity_larger_loss(self):
        profile = CompanyProfile.walmart()
        low = simulate_company(profile, _make_params(severity=0.4))
        high = simulate_company(profile, _make_params(severity=0.9))
        assert high.financial_impact < low.financial_impact


class TestRunTier3:
    def test_run_tier3_returns_outcome(self):
        profiles = [CompanyProfile.walmart(), CompanyProfile.apple()]
        params = _make_params()
        outcome = run_tier3(profiles, params, run_id=0)
        assert isinstance(outcome, RunOutcome)
        assert "WMT" in outcome.company_outcomes
        assert "AAPL" in outcome.company_outcomes

    def test_time_steps_present(self):
        profiles = [CompanyProfile.fedex()]
        params = _make_params()
        outcome = run_tier3(profiles, params, run_id=1)
        assert "FDX" in outcome.time_step_impacts
        assert len(outcome.time_step_impacts["FDX"]) == 4

    def test_from_ticker_fallback(self):
        profile = CompanyProfile.from_ticker("MSFT")
        assert profile.ticker == "MSFT"
        assert profile.annual_revenue > 0
