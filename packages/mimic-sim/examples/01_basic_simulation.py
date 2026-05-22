"""
Example 01: Basic Simulation — Taiwan Strait Closure, 3 Companies, 10,000 Runs

Demonstrates:
  - Defining a ParameterSpace with multiple distributions
  - Running a Tier 3 (formula-only) simulation
  - Reading P5 / P50 / P95, VaR, CVaR
  - Plotting the financial impact distribution
  - Reading sensitivity decomposition

Run:
    python examples/01_basic_simulation.py
"""

import matplotlib
matplotlib.use("Agg")  # headless — saves to file instead of displaying

from mimic_sim import Simulation, ParameterSpace, Distribution
from mimic_sim.execution.tier3_formulas import CompanyProfile
from mimic_sim.visualization import (
    plot_distribution,
    plot_fan_chart,
    plot_sensitivity_tornado,
    plot_correlation_heatmap,
    plot_multi_ticker_distributions,
)
import matplotlib.pyplot as plt

# ── 1. Define the parameter space ─────────────────────────────────────────────
space = ParameterSpace(
    severity=Distribution.triangular(low=0.4, mode=0.7, high=0.95),
    duration_days=Distribution.lognormal(mean=3.4, sigma=0.5),  # ~30d median
    macro_conditions={
        "oil_price": Distribution.normal(mean=85, std=20),
        "usd_cny": Distribution.normal(mean=7.3, std=0.3),
    },
    company_behavior={
        "WMT": {"risk_appetite_delta": Distribution.normal(0, 0.05)},
        "AAPL": {"risk_appetite_delta": Distribution.normal(0, 0.08)},
        "FDX":  {"risk_appetite_delta": Distribution.normal(0, 0.06)},
    },
    intervention_probability=0.15,
)

# ── 2. Build and run the simulation ───────────────────────────────────────────
sim = Simulation(
    profiles=[
        CompanyProfile.walmart(),
        CompanyProfile.apple(),
        CompanyProfile.fedex(),
    ],
    scenario_name="taiwan_strait_closure_30d",
    parameter_space=space,
    n_runs=10_000,
    seed=42,
)

result = sim.run(mode="tier3")

# ── 3. Print risk metrics ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Taiwan Strait Closure — 30-Day Scenario")
print("Tier 3 Formula Simulation  |  10,000 runs")
print("=" * 60)
print("\nFinancial Impact Distribution (USD Billions):")
print(result.summary().to_string())

print("\nKey risk metrics per company:")
for ticker in result.tickers:
    p5  = result.percentile(ticker, "financial_impact", 5)
    p50 = result.percentile(ticker, "financial_impact", 50)
    p95 = result.percentile(ticker, "financial_impact", 95)
    var = result.var(ticker, 0.95)
    cvar = result.cvar(ticker, 0.95)
    print(f"\n  {ticker}:")
    print(f"    P5  (worst 5%):  ${p5:>8.2f}B")
    print(f"    P50 (median):    ${p50:>8.2f}B")
    print(f"    P95 (best 5%):   ${p95:>8.2f}B")
    print(f"    VaR  @ 95%:      ${var:>8.2f}B")
    print(f"    CVaR @ 95%:      ${cvar:>8.2f}B")

# ── 4. Sensitivity analysis ────────────────────────────────────────────────────
print("\nWMT outcome sensitivity:")
for k, v in result.sensitivity("WMT").items():
    print(f"  {k:<22} {v:.1%}")

# ── 5. Systemic risk ──────────────────────────────────────────────────────────
print("\nTail coincidence (P10):")
for a, b in [("WMT", "AAPL"), ("WMT", "FDX"), ("AAPL", "FDX")]:
    tc = result.tail_coincidence(a, b, percentile_threshold=10)
    print(f"  {a} + {b}: {tc:.1%}  (1% if independent, 10% if perfectly correlated)")

# ── 6. Save plots ──────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

plot_distribution(result, "WMT", ax=axes[0, 0], show=False)
plot_distribution(result, "AAPL", ax=axes[0, 1], show=False)
plot_fan_chart(result, "WMT", ax=axes[1, 0], show=False)
plot_sensitivity_tornado(result, "WMT", ax=axes[1, 1], show=False)

plt.tight_layout()
plt.savefig("examples/01_output.png", dpi=150, bbox_inches="tight")
print("\nSaved: examples/01_output.png")

# Correlation heatmap
fig2, ax2 = plt.subplots(figsize=(6, 5))
plot_correlation_heatmap(result, ax=ax2, show=False)
plt.tight_layout()
plt.savefig("examples/01_correlation.png", dpi=150, bbox_inches="tight")
print("Saved: examples/01_correlation.png")
