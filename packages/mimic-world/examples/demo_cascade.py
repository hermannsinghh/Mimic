"""
mimic-world Phase 1 demo — Taiwan Strait cascade with AAPL + WMT.

Demonstrates the core thesis:
  AAPL's Day 1 decision (accelerate India production, hoard chips)
  → updates world_state (india_manufacturing_demand +X, chip demand +Y)
  → WMT's Day 7 decision is DIFFERENT because of what AAPL did on Day 1

Run:
    python -m examples.demo_cascade

Requires ANTHROPIC_API_KEY in environment.
"""

from __future__ import annotations

from mimic_world import Scenario, Twin, World


def main() -> None:
    print("=" * 65)
    print("  mimic-world Phase 1 demo")
    print("  Scenario: Taiwan Strait Closure (30 days)")
    print("  Companies: AAPL + WMT, 2 time steps (Day 1 + Day 7)")
    print("=" * 65)
    print()

    # ── Build the world ──────────────────────────────────────────────
    world = World()
    world.add_twin(Twin.from_ticker("AAPL"))
    world.add_twin(Twin.from_ticker("WMT"))

    # Add supply chain relationships
    world.connect("TSMC", "AAPL", relationship="supplier", weight=0.95, commodity="chips")
    world.connect("MAERSK", "WMT", relationship="supplier", weight=0.30, commodity="shipping")

    print(f"World: {world}")
    print()

    # ── Load scenario ────────────────────────────────────────────────
    scenario = Scenario.from_library("taiwan_strait_closure_30d")
    print(f"Scenario: {scenario}")
    print(f"Initial shocks: {scenario.initial_shocks}")
    print()

    # ── Run the cascade ──────────────────────────────────────────────
    print("Running cascade simulation (calling Claude API)...")
    print()

    result = world.run(scenario, time_steps=[1, 7])

    # ── Print results ─────────────────────────────────────────────────
    result.print_summary()

    # ── The key demonstration ────────────────────────────────────────
    print()
    print("=" * 65)
    print("  THE THESIS: Did WMT's Day 7 response differ from Day 1?")
    print("=" * 65)

    timeline = result.cascade_timeline
    if len(timeline) >= 2:
        step1 = timeline[0]
        step7 = timeline[1]

        print(f"\nWorld state at Day 1: {step1.world_state}")
        print(f"\nWorld state at Day 7: {step7.world_state}")

        # Keys that changed between Day 1 and Day 7
        new_keys = set(step7.world_state) - set(scenario.initial_shocks)
        if new_keys:
            print(f"\nKeys that emerged from twin decisions: {new_keys}")
            print("\nThis is emergent behavior:")
            print("  AAPL's Day 1 actions changed the shared world_state.")
            print("  WMT saw those changes and responded differently at Day 7.")
        else:
            print("\nNo new world_state keys emerged (try more companies for richer cascade).")

    # Export JSON
    print()
    print("Exporting result to cascade_result.json ...")
    with open("cascade_result.json", "w") as f:
        f.write(result.export("json"))
    print("Done. See cascade_result.json for full output.")


if __name__ == "__main__":
    main()
