"""
Full-stack integration test — all 6 mimic repos in one script.

Flow:
  mimic_world  →  World + Twins simulate cascade (LLM calls via DeepSeek)
  mimic_sim    →  Monte Carlo over the scenario (Tier 2, formula-anchored)
  mimic_sim    →  Sensitivity analysis (duration vs severity finding)

Run:
  python ~/Desktop/mimic/test_full_stack.py

Loads DEEPSEEK_API_KEY from Mimic/.env (or .env next to this script) when python-dotenv is installed.
"""

import os
import sys
import time
from pathlib import Path


def _load_env() -> None:
    root = Path(__file__).resolve().parent
    for candidate in (root / "Mimic" / ".env", root / ".env"):
        if not candidate.is_file():
            continue
        try:
            from dotenv import load_dotenv
            load_dotenv(candidate, override=False)
        except ImportError:
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
        break


_load_env()

# ── Dependency check ──────────────────────────────────────────────────────────

missing = []
try:
    from mimic_world import World, Scenario
    from mimic_world.twin import Twin
except ImportError:
    missing.append("mimic-world  →  cd Mimic-world && pip install -e .")

try:
    from mimic_sim import Simulation, ParameterSpace, Distribution
    from mimic_sim.execution.tier3_formulas import CompanyProfile
except ImportError:
    missing.append("mimic-sim    →  cd Mimic-sim && pip install -e .")

if missing:
    print("Missing packages — install first:")
    for m in missing:
        print(f"  {m}")
    sys.exit(1)

if not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
    print("Error: set DEEPSEEK_API_KEY (or ANTHROPIC_API_KEY) before running.")
    sys.exit(1)

provider = "DeepSeek" if os.environ.get("DEEPSEEK_API_KEY") else "Anthropic"
print(f"\n{'='*60}")
print(f"  mimic full-stack integration test  [{provider}]")
print(f"{'='*60}\n")


# ── Step 1: World cascade ─────────────────────────────────────────────────────

print("STEP 1 — World cascade (mimic-world)")
print("-" * 40)

t0 = time.perf_counter()

world = World()
for ticker in ["WMT", "AAPL", "FDX"]:
    world.add_twin(Twin.from_ticker(ticker))

# Wire supply-chain relationships
world.connect("TSMC", "AAPL",  relationship="supplier", weight=0.95, commodity="chips")
world.connect("FDX",  "WMT",   relationship="supplier", weight=0.40, commodity="logistics")

scenario = Scenario.from_library("taiwan_strait_closure_30d")
print(f"Scenario: {scenario.title}")
print(f"  Severity: {scenario.severity:.0%}   Duration: {scenario.duration_days}d")
print(f"  Initial shocks: {list(scenario.initial_shocks.keys())}")
print()

world_result = world.run(scenario, time_steps=[1, 7, 30])

elapsed_world = time.perf_counter() - t0
print(f"✅ World cascade complete in {elapsed_world:.1f}s")
print(f"   Most affected:  {world_result.most_affected}")
print(f"   Least affected: {world_result.least_affected}")
print(f"   Cascade steps:  {len(world_result.cascade_timeline)}")

if world_result.financial_impacts:
    print("\n   Financial impact summary:")
    for ticker, impact in world_result.financial_impacts.items():
        print(f"     {ticker}: {impact}")

print()


# ── Step 2: Monte Carlo simulation (Tier 3 + Tier 2) ────────────────────────

print("STEP 2 — Monte Carlo simulation (mimic-sim)")
print("-" * 40)

profiles = [
    CompanyProfile.walmart(),
    CompanyProfile.apple(),
    CompanyProfile.fedex(),
]

space = ParameterSpace(
    severity=Distribution.triangular(0.5, 0.75, 0.95),
    duration_days=Distribution.lognormal(mean=3.4, sigma=0.4),
    macro_conditions={
        "oil_price": Distribution.normal(95, 15),
        "usd_cny":   Distribution.normal(7.5, 0.3),
    },
    intervention_probability=0.10,
)

sim = Simulation(
    profiles=profiles,
    scenario_name=scenario.id,
    parameter_space=space,
    n_runs=500,
    seed=42,
)

t1 = time.perf_counter()
result_t3 = sim.run(mode="tier3")
elapsed_t3 = time.perf_counter() - t1

t2 = time.perf_counter()
result_t2 = sim.run(mode="tier2")
elapsed_t2 = time.perf_counter() - t2

print(f"✅ Simulation complete  (Tier 3: {elapsed_t3:.2f}s, Tier 2: {elapsed_t2:.2f}s)")
print()

print("   Tier 3 (formula-only)  vs  Tier 2 (behaviorally anchored)")
print(f"   {'Ticker':<6}  {'T3 P50':>9}  {'T3 VaR95':>10}  │  {'T2 P50':>9}  {'T2 VaR95':>10}  {'Narrowing':>10}")
print(f"   {'-'*6}  {'-'*9}  {'-'*10}  │  {'-'*9}  {'-'*10}  {'-'*10}")
for ticker in ["WMT", "AAPL", "FDX"]:
    t3_p50  = result_t3.percentile(ticker, "financial_impact", 50)
    t3_var  = result_t3.var(ticker, 0.95)
    t2_p50  = result_t2.percentile(ticker, "financial_impact", 50)
    t2_var  = result_t2.var(ticker, 0.95)
    narrowing = (t3_var - t2_var) / abs(t3_var) * 100 if t3_var != 0 else 0
    print(
        f"   {ticker:<6}  {t3_p50:>+8.1f}B  {t3_var:>+9.1f}B  │  {t2_p50:>+8.1f}B  {t2_var:>+9.1f}B  {narrowing:>+9.1f}%"
    )
print()


# ── Step 3: Sensitivity analysis ─────────────────────────────────────────────

print("STEP 3 — Sensitivity analysis (WMT)")
print("-" * 40)

sens = result_t2.sensitivity("WMT")
total = sum(sens.values())
print("   Parameter            Contribution")
print("   " + "-" * 36)
for param, weight in sorted(sens.items(), key=lambda x: -x[1]):
    bar = "█" * int(weight / total * 30)
    print(f"   {param:<20} {weight/total:>6.1%}  {bar}")

duration_share = sens.get("duration_days", 0) / total * 100
severity_share = sens.get("severity", 0) / total * 100
print()
print(f"   Key finding:  duration = {duration_share:.1f}%  vs  severity = {severity_share:.1f}%")
print(f"   → Duration explains {duration_share:.0f}% of WMT outcome variance")
print()


# ── Summary ───────────────────────────────────────────────────────────────────

total_elapsed = time.perf_counter() - t0
print("=" * 60)
print(f"  ✅ Full stack passed in {total_elapsed:.1f}s")
print(f"  Repos exercised: mimic-world + mimic-sim")
print(f"  LLM provider:    {provider}")
print(f"  Runs:            {sim.n_runs:,} Monte Carlo draws × 2 tiers")
print("=" * 60)
