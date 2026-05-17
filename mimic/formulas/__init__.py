"""
mimic.formulas — Economic primitives library.

These are textbook economics encoded as composable Python functions.
All functions return plain dicts for easy prompt injection.
"""
from __future__ import annotations
import math
from typing import Optional
from mimic.core.context import CompanyContext


# ─────────────────────────────────────────────
# 1. DCF — Valuation impact of a cash flow shock
# ─────────────────────────────────────────────
def dcf_impact(
    base_fcf: float,
    shock_pct: float,
    growth_rate: float = 0.05,
    wacc: float = 0.09,
    years: int = 5,
) -> dict:
    """
    Estimate change in enterprise value from a % shock to free cash flow.
    Returns: {base_ev, shocked_ev, ev_delta, ev_delta_pct}
    All values in $M.
    """
    def terminal_value(fcf, g, r):
        return fcf * (1 + g) / (r - g) if r > g else 0

    def pv_fcfs(fcf0, g, r, n):
        return sum(fcf0 * (1 + g)**t / (1 + r)**t for t in range(1, n + 1))

    base_ev = pv_fcfs(base_fcf, growth_rate, wacc, years) + \
              terminal_value(base_fcf * (1 + growth_rate)**years, growth_rate, wacc) / (1 + wacc)**years

    shocked_fcf = base_fcf * (1 + shock_pct)
    shocked_ev = pv_fcfs(shocked_fcf, growth_rate, wacc, years) + \
                 terminal_value(shocked_fcf * (1 + growth_rate)**years, growth_rate, wacc) / (1 + wacc)**years

    return {
        "formula": "DCF",
        "base_ev_usdM": round(base_ev, 1),
        "shocked_ev_usdM": round(shocked_ev, 1),
        "ev_delta_usdM": round(shocked_ev - base_ev, 1),
        "ev_delta_pct": round((shocked_ev - base_ev) / base_ev, 4) if base_ev else 0,
    }


# ─────────────────────────────────────────────
# 2. Altman Z-Score — Bankruptcy risk indicator
# ─────────────────────────────────────────────
def altman_z(
    working_capital: float,
    retained_earnings: float,
    ebit: float,
    market_cap: float,
    sales: float,
    total_assets: float,
    total_liabilities: float,
) -> dict:
    """
    Original Altman Z-Score (1968).
    Z > 2.99 = safe, 1.81-2.99 = grey zone, < 1.81 = distress.
    """
    if total_assets == 0:
        return {"formula": "Altman-Z", "z_score": None, "zone": "unknown"}

    x1 = working_capital / total_assets
    x2 = retained_earnings / total_assets
    x3 = ebit / total_assets
    x4 = market_cap / total_liabilities if total_liabilities else 0
    x5 = sales / total_assets

    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + x5

    zone = "safe" if z > 2.99 else ("grey" if z > 1.81 else "distress")

    return {
        "formula": "Altman-Z",
        "z_score": round(z, 2),
        "zone": zone,
        "components": {"x1": round(x1, 3), "x2": round(x2, 3),
                       "x3": round(x3, 3), "x4": round(x4, 3), "x5": round(x5, 3)},
    }


# ─────────────────────────────────────────────
# 3. COGS Sensitivity — Input shock → margin impact
# ─────────────────────────────────────────────
def cogs_sensitivity(
    revenue: float,
    cogs: float,
    input_shock_pct: float,
    passthrough_rate: float = 0.4,
) -> dict:
    """
    How does an X% shock to input costs affect operating margin?
    passthrough_rate: % of cost increase the company can pass to customers.
    """
    shocked_cogs = cogs * (1 + input_shock_pct)
    absorbed_cost = (shocked_cogs - cogs) * (1 - passthrough_rate)
    base_gross_margin = (revenue - cogs) / revenue if revenue else 0
    new_gross_margin = (revenue - cogs - absorbed_cost) / revenue if revenue else 0
    margin_compression = base_gross_margin - new_gross_margin

    return {
        "formula": "COGS_Sensitivity",
        "base_gross_margin": round(base_gross_margin, 4),
        "new_gross_margin": round(new_gross_margin, 4),
        "margin_compression": round(margin_compression, 4),
        "annual_ebitda_impact_usdM": round(-absorbed_cost, 1),
        "passthrough_rate_assumed": passthrough_rate,
    }


# ─────────────────────────────────────────────
# 4. FX Passthrough — Currency move → P&L impact
# ─────────────────────────────────────────────
def fx_passthrough(
    revenue: float,
    fx_exposure: dict[str, float],
    fx_moves: dict[str, float],
    cost_currency_mix: Optional[dict[str, float]] = None,
) -> dict:
    """
    Net FX impact on revenue.
    fx_exposure: {currency: % of revenue}
    fx_moves: {currency: % change in that currency vs USD}
    """
    total_fx_revenue_impact = 0.0
    breakdown = {}

    for currency, revenue_share in fx_exposure.items():
        move = fx_moves.get(currency, 0.0)
        impact = revenue * revenue_share * move
        total_fx_revenue_impact += impact
        breakdown[currency] = round(impact, 1)

    return {
        "formula": "FX_Passthrough",
        "total_revenue_impact_usdM": round(total_fx_revenue_impact, 1),
        "breakdown_by_currency": breakdown,
        "pct_of_revenue": round(total_fx_revenue_impact / revenue, 4) if revenue else 0,
    }


# ─────────────────────────────────────────────
# 5. Inventory Burn — Days remaining under demand shock
# ─────────────────────────────────────────────
def inventory_burn(
    inventory_days: float,
    demand_multiplier: float,
) -> dict:
    """
    How long does inventory last if demand spikes by demand_multiplier?
    demand_multiplier > 1 = demand increase (faster burn).
    demand_multiplier < 1 = demand drop (slower burn).
    """
    effective_days = inventory_days / demand_multiplier if demand_multiplier > 0 else inventory_days
    risk_level = "critical" if effective_days < 7 else ("high" if effective_days < 21 else "normal")

    return {
        "formula": "Inventory_Burn",
        "base_days_of_inventory": inventory_days,
        "demand_multiplier": demand_multiplier,
        "effective_days_remaining": round(effective_days, 1),
        "risk_level": risk_level,
        "restocking_urgency": demand_multiplier > 1 and effective_days < 30,
    }


# ─────────────────────────────────────────────
# 6. Bayesian Update — P(outcome | evidence)
# ─────────────────────────────────────────────
def bayes_update(
    prior: float,
    likelihood_given_true: float,
    likelihood_given_false: float,
) -> dict:
    """
    Update probability estimate given new evidence.
    prior: P(event) before evidence
    likelihood_given_true: P(evidence | event is true)
    likelihood_given_false: P(evidence | event is false)
    Returns updated posterior probability.
    """
    p_evidence = likelihood_given_true * prior + likelihood_given_false * (1 - prior)
    if p_evidence == 0:
        return {"formula": "Bayesian_Update", "posterior": prior, "update": 0}

    posterior = (likelihood_given_true * prior) / p_evidence

    return {
        "formula": "Bayesian_Update",
        "prior": round(prior, 4),
        "posterior": round(posterior, 4),
        "update": round(posterior - prior, 4),
        "direction": "up" if posterior > prior else "down",
    }


# ─────────────────────────────────────────────
# 7. Operating Leverage — Margin elasticity to revenue
# ─────────────────────────────────────────────
def operating_leverage(
    revenue: float,
    variable_costs: float,
    fixed_costs: float,
    revenue_change_pct: float,
) -> dict:
    """
    How does a % change in revenue affect operating income?
    """
    contribution_margin = (revenue - variable_costs) / revenue if revenue else 0
    dol = contribution_margin * revenue / (contribution_margin * revenue - fixed_costs) \
          if (contribution_margin * revenue - fixed_costs) != 0 else 0

    base_op_income = contribution_margin * revenue - fixed_costs
    new_revenue = revenue * (1 + revenue_change_pct)
    new_op_income = contribution_margin * new_revenue - fixed_costs
    op_income_change_pct = (new_op_income - base_op_income) / abs(base_op_income) \
                           if base_op_income != 0 else 0

    return {
        "formula": "Operating_Leverage",
        "degree_of_operating_leverage": round(dol, 2),
        "revenue_change_pct": revenue_change_pct,
        "op_income_change_pct": round(op_income_change_pct, 4),
        "base_op_income_usdM": round(base_op_income, 1),
        "new_op_income_usdM": round(new_op_income, 1),
    }


# ─────────────────────────────────────────────
# 8. Supplier Concentration Risk (HHI)
# ─────────────────────────────────────────────
def supplier_hhi(supplier_shares: dict[str, float]) -> dict:
    """
    Herfindahl-Hirschman Index for supplier concentration.
    HHI > 2500 = highly concentrated (risky).
    HHI 1500-2500 = moderate.
    HHI < 1500 = diversified.
    """
    total = sum(supplier_shares.values())
    if total == 0:
        return {"formula": "HHI", "hhi": 0, "risk_level": "unknown"}

    normalized = {k: v / total for k, v in supplier_shares.items()}
    hhi = sum((share * 100) ** 2 for share in normalized.values())

    risk = "high" if hhi > 2500 else ("moderate" if hhi > 1500 else "diversified")

    return {
        "formula": "HHI",
        "hhi": round(hhi, 0),
        "risk_level": risk,
        "most_concentrated": max(normalized, key=normalized.get),
        "largest_share": round(max(normalized.values()), 3),
    }


# ─────────────────────────────────────────────
# 9. Cascade Propagation — Supply chain shock spread
# ─────────────────────────────────────────────
def cascade_propagate(
    initial_shock: float,
    n_tiers: int = 3,
    decay: float = 0.6,
    amplification_risk: float = 0.2,
) -> dict:
    """
    Estimate how a supply shock propagates through tiers.
    decay: % of shock that passes to next tier (0-1).
    amplification_risk: probability that shock amplifies at any tier.
    """
    tiers = {}
    current = initial_shock

    for tier in range(1, n_tiers + 1):
        amplified = current * (1 + 0.5) if (tier == 2 and amplification_risk > 0.15) else current
        tiers[f"tier_{tier}"] = round(amplified, 4)
        current = amplified * decay

    return {
        "formula": "Cascade_Propagation",
        "initial_shock": initial_shock,
        "tier_impacts": tiers,
        "total_system_shock": round(sum(tiers.values()), 4),
        "amplification_triggered": amplification_risk > 0.15,
    }


# ─────────────────────────────────────────────
# 10. Beta Response — Stock reaction to market move
# ─────────────────────────────────────────────
def capm_response(
    beta: float,
    market_return: float,
    risk_free_rate: float = 0.045,
    alpha: float = 0.0,
) -> dict:
    """
    Expected stock return from market move using CAPM.
    """
    expected = risk_free_rate + beta * (market_return - risk_free_rate) + alpha
    return {
        "formula": "CAPM",
        "expected_return": round(expected, 4),
        "beta": beta,
        "market_return": market_return,
        "excess_return_vs_market": round(expected - market_return, 4),
    }


# ─────────────────────────────────────────────
# MAIN COMBINATOR — called by Twin.simulate()
# ─────────────────────────────────────────────
def compute_formula_context(
    context: CompanyContext,
    event: str,
    severity: float,
) -> dict:
    """
    Run all relevant formulas for a given company + event.
    Returns a dict of formula outputs for prompt injection.
    """
    f = context.financials
    s = context.suppliers

    results = {}

    # DCF impact (assume severity maps to FCF shock)
    fcf_estimate = f.ebitda - f.capex_ttm
    if fcf_estimate != 0:
        results["dcf"] = dcf_impact(
            base_fcf=fcf_estimate,
            shock_pct=-severity * 0.3,  # rough heuristic
        )

    # COGS sensitivity
    if f.cogs_ttm > 0:
        results["cogs_sensitivity"] = cogs_sensitivity(
            revenue=f.revenue_ttm,
            cogs=f.cogs_ttm,
            input_shock_pct=severity * 0.2,
        )

    # Inventory burn
    if f.inventory_turnover_days > 0:
        results["inventory_burn"] = inventory_burn(
            inventory_days=f.inventory_turnover_days,
            demand_multiplier=1 + severity * 0.5,
        )

    # FX passthrough (if exposure exists)
    if f.fx_exposure:
        results["fx_passthrough"] = fx_passthrough(
            revenue=f.revenue_ttm,
            fx_exposure=f.fx_exposure,
            fx_moves={k: -severity * 0.05 for k in f.fx_exposure},
        )

    # Supplier HHI
    if s.geographic_concentration:
        results["supplier_hhi"] = supplier_hhi(s.geographic_concentration)

    # Cascade propagation
    results["cascade"] = cascade_propagate(
        initial_shock=severity,
        n_tiers=3,
        amplification_risk=severity * 0.3,
    )

    # Bayesian update for crisis escalation
    results["bayes_escalation"] = bayes_update(
        prior=0.3,
        likelihood_given_true=0.7 + severity * 0.2,
        likelihood_given_false=0.15,
    )

    return results
