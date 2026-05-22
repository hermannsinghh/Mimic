# mimic-world

**Multi-company scenario engine for supply chain cascade simulation.**

> What happens to an entire system when a shock hits?

`mimic-world` simulates **many companies** responding to **one event**, watching them react to each other, and tracking the cascade. This is where supply chains come alive. This is where second-order effects emerge. This is where a port closure becomes an inflation event.

```python
from mimic_world import World, Scenario, Twin

world = World()
world.add_twin(Twin.from_ticker("AAPL"))
world.add_twin(Twin.from_ticker("WMT"))
world.add_twin(Twin.from_ticker("FDX"))
world.add_twin(Twin.from_ticker("TSMC"))

world.connect("TSMC", "AAPL", relationship="supplier", weight=0.95, commodity="chips")
world.connect("XOM",  "FDX",  relationship="supplier", weight=0.40, commodity="jet_fuel")

scenario = Scenario.from_library("taiwan_strait_closure_30d")
result   = world.run(scenario)

result.print_summary()
print(result.cascade_timeline)
print(result.second_order_effects)
print(result.system_stability)   # "stabilizing" | "escalating" | "bifurcating"
```

## How It Works

1. A **Scenario** defines initial shocks (`semiconductor_supply: -0.65`) and cascade rules
2. A **World** holds company **Twins** connected by a **RelationshipGraph**
3. The **CascadeEngine** runs time steps: each twin's LLM-powered decisions update a shared `world_state`
4. Connected twins see those updates and react — creating emergent second-order behavior

## The 50-Scenario Library

Pre-built scenarios across 6 categories:

| Category | Count | Examples |
|---|---|---|
| Geopolitical | 10 | Taiwan Strait closure, Russia energy cutoff |
| Supply Chain | 10 | Suez Canal closure, Shanghai lockdown |
| Macro/Financial | 10 | Fed hikes 200bps, Credit crunch 2008-style |
| Climate/Natural | 10 | Gulf Coast Cat 5 hurricane, Japan earthquake 9.0 |
| Pandemic/Health | 5 | COVID-severity pandemic, Antibiotic resistance |
| Technology/Cyber | 5 | Global cloud outage, Critical infrastructure attack |

```python
# List all 50 scenarios
for s in Scenario.list_library():
    print(f"{s['id']:<45} severity={s['severity']:.0%}")
```

## Install

```bash
pip install mimic-world
```

## Ecosystem

```
mimic          → single company twin
mimic-bench    → grades predictions
mimic-forecast → real quantitative forecasts
mimic-world    → multi-company system + scenarios  ← HERE
mimic-sim      → 10,000-run Monte Carlo over worlds
mimic-signal   → real-time event detection
```

## License

MIT
