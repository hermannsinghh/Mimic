"""
Tier 3 execution: pure formula-based simulation. No LLM calls.

Each company's financial impact is estimated from economic relationships:
  - Revenue exposure to the shocked sector
  - Supply chain vulnerability
  - Macro sensitivity (oil, FX, rates)
  - Government intervention dampening
  - Time-decay as companies adapt

This produces fat-tailed, economically-coherent distributions without
spending a single token on an LLM — ideal for 10,000+ run sweeps and
rapid sensitivity analysis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from mimic_sim.parameter_space import SampledParams


# ── Company profile ────────────────────────────────────────────────────────────

@dataclass
class CompanyProfile:
    """
    Lightweight description of a company used by the formula engine.
    In full Tier 1/2 this comes from mimic.Twin; here it is self-contained.
    """

    ticker: str
    annual_revenue: float           # USD billions
    supply_chain_exposure: float    # 0–1: fraction of COGS exposed to scenario
    macro_oil_sensitivity: float    # revenue change per $10 oil move (fraction)
    macro_fx_sensitivity: float     # revenue change per 0.1 USD/CNY move (fraction)
    operating_margin: float         # EBIT / Revenue
    inventory_days: float           # days of inventory buffer
    risk_appetite: float = 0.5      # 0=very conservative, 1=very aggressive
    decision_speed: float = 0.5     # 0=slow, 1=fast adapter

    # Pre-built profiles for common tickers
    @staticmethod
    def walmart() -> CompanyProfile:
        return CompanyProfile(
            ticker="WMT",
            annual_revenue=648.0,
            supply_chain_exposure=0.38,
            macro_oil_sensitivity=0.012,
            macro_fx_sensitivity=0.008,
            operating_margin=0.043,
            inventory_days=42,
            risk_appetite=0.35,
            decision_speed=0.55,
        )

    @staticmethod
    def apple() -> CompanyProfile:
        return CompanyProfile(
            ticker="AAPL",
            annual_revenue=383.0,
            supply_chain_exposure=0.72,
            macro_oil_sensitivity=0.004,
            macro_fx_sensitivity=0.031,
            operating_margin=0.298,
            inventory_days=9,
            risk_appetite=0.60,
            decision_speed=0.70,
        )

    @staticmethod
    def fedex() -> CompanyProfile:
        return CompanyProfile(
            ticker="FDX",
            annual_revenue=90.0,
            supply_chain_exposure=0.20,
            macro_oil_sensitivity=0.045,
            macro_fx_sensitivity=0.015,
            operating_margin=0.062,
            inventory_days=0,
            risk_appetite=0.50,
            decision_speed=0.65,
        )

    @staticmethod
    def from_ticker(ticker: str) -> CompanyProfile:
        registry = {
            "WMT": CompanyProfile.walmart,
            "AAPL": CompanyProfile.apple,
            "FDX": CompanyProfile.fedex,
        }
        if ticker in registry:
            return registry[ticker]()
        # Generic fallback: mid-size company, moderate exposure
        return CompanyProfile(
            ticker=ticker,
            annual_revenue=50.0,
            supply_chain_exposure=0.30,
            macro_oil_sensitivity=0.010,
            macro_fx_sensitivity=0.015,
            operating_margin=0.08,
            inventory_days=30,
        )


# ── Run outcome ────────────────────────────────────────────────────────────────

@dataclass
class CompanyOutcome:
    ticker: str
    financial_impact: float        # USD billions, negative = loss
    revenue_impact_pct: float      # % revenue change
    operating_income_impact: float # USD billions
    recovery_time_days: float      # days to return to baseline
    action_taken: str              # qualitative description


@dataclass
class RunOutcome:
    run_id: int
    params: SampledParams
    company_outcomes: dict[str, CompanyOutcome]
    time_step_impacts: dict[str, list[float]] = field(default_factory=dict)


# ── Core formula engine ────────────────────────────────────────────────────────

def _base_revenue_impact(profile: CompanyProfile, params: SampledParams) -> float:
    """
    Fraction of annual revenue lost due to supply chain disruption.

    Model:
      impact = exposure × severity × duration_weight × (1 − inventory_buffer)

    duration_weight: scales log-linearly — short shocks hit harder per day,
    long shocks plateau as companies adapt.
    """
    inv_buffer = min(1.0, profile.inventory_days / max(params.duration_days, 1))
    # Protection fades after inventory is exhausted
    buffer_effect = inv_buffer ** 0.7

    duration_weight = math.log1p(params.duration_days / 30) / math.log1p(1)
    duration_weight = min(duration_weight, 2.5)

    raw = profile.supply_chain_exposure * params.severity * duration_weight
    net = raw * (1 - buffer_effect * 0.6)

    return float(np.clip(net, 0.0, 0.85))  # cap at 85% of exposed revenue


def _macro_impact(profile: CompanyProfile, params: SampledParams) -> float:
    """Additional revenue fraction impact from macro conditions."""
    oil_baseline = 85.0
    fx_baseline = 7.3

    oil_delta = params.macro_conditions.get("oil_price", oil_baseline) - oil_baseline
    fx_delta = params.macro_conditions.get("usd_cny", fx_baseline) - fx_baseline

    oil_impact = profile.macro_oil_sensitivity * (oil_delta / 10)
    fx_impact = profile.macro_fx_sensitivity * (fx_delta / 0.1)

    return float(oil_impact + fx_impact)


def _behavioral_modifier(
    profile: CompanyProfile,
    params: SampledParams,
    base_impact: float,
) -> tuple[float, str]:
    """
    Adjust impact based on company behavior and risk appetite.
    Returns (modified_impact_fraction, action_description).
    """
    effective_risk = profile.risk_appetite
    if profile.ticker in params.company_behavior:
        delta = params.company_behavior[profile.ticker].get("risk_appetite_delta", 0.0)
        effective_risk = float(np.clip(effective_risk + delta, 0.0, 1.0))

    effective_speed = profile.decision_speed
    if profile.ticker in params.company_behavior:
        delta = params.company_behavior[profile.ticker].get("decision_speed_delta", 0.0)
        effective_speed = float(np.clip(effective_speed + delta, 0.0, 1.0))

    # Conservative companies hedge → lower impact but miss upside
    hedge_reduction = (1 - effective_risk) * 0.25
    # Fast deciders adapt sooner → reduce duration-driven impact
    speed_reduction = effective_speed * 0.15

    modifier = 1.0 - hedge_reduction - speed_reduction

    if effective_risk < 0.3:
        action = "pre-hedged, activated contingency suppliers"
    elif effective_risk > 0.7:
        action = "held position, deferred response"
    else:
        action = "partial hedge, monitored and adjusted"

    return float(modifier), action


def _intervention_dampening(params: SampledParams) -> float:
    """If government/Fed intervenes, dampen the macro shock by 20-40%."""
    if params.intervention_triggered:
        return 0.70  # 30% reduction in macro impact
    return 1.0


def _recovery_time(
    profile: CompanyProfile, params: SampledParams, net_impact: float
) -> float:
    """
    Estimate days to recover to baseline post-event.
    Based on: impact depth, inventory, decision speed, and event duration.
    """
    base_recovery = params.duration_days * 1.5
    impact_multiplier = 1 + net_impact * 2
    speed_factor = 1 - profile.decision_speed * 0.3
    return float(base_recovery * impact_multiplier * speed_factor)


def simulate_company(
    profile: CompanyProfile,
    params: SampledParams,
    scenario_annual_revenue_fraction: float = 1.0,
) -> CompanyOutcome:
    """
    Single-company formula simulation for one parameter draw.
    Returns financial impact in USD billions.
    """
    base_rev_impact = _base_revenue_impact(profile, params)
    macro_adj = _macro_impact(profile, params) * _intervention_dampening(params)

    total_rev_impact_fraction = base_rev_impact + macro_adj
    behavior_mod, action = _behavioral_modifier(profile, params, total_rev_impact_fraction)
    net_rev_impact_fraction = float(np.clip(total_rev_impact_fraction * behavior_mod, -0.5, 0.95))

    # Annualise: multiply by (duration / 365) to get the period impact,
    # then scale to full-year equivalent for comparability
    period_fraction = params.duration_days / 365
    financial_impact_bn = -(
        profile.annual_revenue * net_rev_impact_fraction * period_fraction * scenario_annual_revenue_fraction
    )
    operating_income_impact = financial_impact_bn * profile.operating_margin / (1 - profile.operating_margin + 1e-9)

    return CompanyOutcome(
        ticker=profile.ticker,
        financial_impact=financial_impact_bn,
        revenue_impact_pct=net_rev_impact_fraction * 100,
        operating_income_impact=operating_income_impact,
        recovery_time_days=_recovery_time(profile, params, net_rev_impact_fraction),
        action_taken=action,
    )


def _time_step_impacts(
    profile: CompanyProfile,
    params: SampledParams,
    n_steps: int = 4,
) -> list[float]:
    """
    Generate per-time-step impact trajectory for fan chart visualisation.
    Models the S-curve of disruption then recovery.
    """
    outcome = simulate_company(profile, params)
    total = outcome.financial_impact
    # Disruption peaks at step 2, then decays
    weights = np.array([0.10, 0.35, 0.35, 0.20])[:n_steps]
    weights = weights / weights.sum()
    return [float(total * w) for w in weights]


def run_tier3(
    profiles: list[CompanyProfile],
    params: SampledParams,
    run_id: int,
) -> RunOutcome:
    """Execute one Tier 3 formula run across all company profiles."""
    outcomes: dict[str, CompanyOutcome] = {}
    time_steps: dict[str, list[float]] = {}

    for profile in profiles:
        outcomes[profile.ticker] = simulate_company(profile, params)
        time_steps[profile.ticker] = _time_step_impacts(profile, params)

    return RunOutcome(run_id=run_id, params=params, company_outcomes=outcomes, time_step_impacts=time_steps)
