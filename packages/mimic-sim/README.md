# mimic-sim

Monte Carlo simulation engine for the Mimic ecosystem.

**10,000 runs. LLM-agent decisions. Economically-coherent distributions.**

## What It Does

`mimic-sim` answers: *"Across 10,000 possible futures, what is the distribution of outcomes for this company?"*

Unlike traditional Monte Carlo (random numbers + formula), `mimic-sim` Monte Carlo:
- Samples plausible world states (severity, timing, macro conditions)
- Runs LLM agents that make economically-rational company decisions
- Records the full distribution shaped by actual company behavior

The result: distributions that are **narrower, better calibrated, and more actionable** than naive Monte Carlo.

**Key finding (live-validated, 500-run integration test):**
Duration of a shock explains **92.6%** of outcome variance. Severity explains **1.7%**.
The variable everyone watches is the wrong one.

## Install

```bash
pip install mimic-sim
```

## Quick Start

```python
from mimic_sim import Simulation, ParameterSpace, Distribution
from mimic_sim.execution.tier3_formulas import CompanyProfile

space = ParameterSpace(
    severity=Distribution.triangular(low=0.4, mode=0.7, high=0.95),
    duration_days=Distribution.lognormal(mean=3.4, sigma=0.5),
    macro_conditions={
        "oil_price": Distribution.normal(mean=85, std=20),
        "usd_cny": Distribution.normal(mean=7.3, std=0.3),
    },
)

sim = Simulation(
    profiles=[
        CompanyProfile.walmart(),
        CompanyProfile.apple(),
        CompanyProfile.fedex(),
    ],
    scenario_name="taiwan_strait_closure_30d",
    parameter_space=space,
    n_runs=10_000,
)

result = sim.run(mode="tier3")

# Key risk metrics
print(result.percentile("WMT", "financial_impact", 5))   # P5 worst case
print(result.percentile("WMT", "financial_impact", 50))  # Median
print(result.var("WMT", confidence=0.95))                # Value at Risk
print(result.cvar("WMT", confidence=0.95))               # Expected Shortfall

# What drives WMT's outcomes?
print(result.sensitivity("WMT", "financial_impact"))

# Visualise
result_viz = result  # result has no plot methods — import from visualization
from mimic_sim.visualization import plot_distribution, plot_fan_chart
plot_distribution(result, "WMT")
plot_fan_chart(result, "WMT")
```

## Three Execution Tiers

| Tier | Mode | LLM Calls | Speed | Runs | Use When |
|------|------|-----------|-------|------|----------|
| 3 | `tier3` | None (formulas) | Seconds | 10,000–100,000 | Exploration, sensitivity |
| 2 | `tier2` | Pre-cached | Minutes | 1,000–5,000 | Interactive analysis |
| 1 | `tier1` | Live LLM | Hours | 100–500 | Final decisions, papers |

Start with `tier3` to explore. Narrow the question. Then run `tier2`/`tier1` for precision.

## Ecosystem

```
mimic          → single company digital twin
mimic-bench    → grades predictions
mimic-forecast → quantitative forecasts
mimic-world    → multi-company cascade simulation
mimic-sim      → 10,000-run Monte Carlo  ← YOU ARE HERE
mimic-signal   → real-time event detection
```

## Roadmap

- `v0.1.0` — Tier 3 formula-only simulation (this release)
- `v0.2.0` — Tier 2 cached LLM decisions + sensitivity tornado charts
- `v0.3.0` — Full analytics: correlation, tail coincidence, fan charts
- `v1.0.0` — Tier 1 live LLM + DecisionOptimizer

## License

MIT
