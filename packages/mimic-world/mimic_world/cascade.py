"""CascadeEngine — the core simulation loop that propagates shocks through the world."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from .result import Decision, ImpactRange, TimeStepResult, WorldResult, WorldState

if TYPE_CHECKING:
    from .scenario import Scenario
    from .world import World

# Annual revenue estimates ($M) for computing financial impact ranges.
# Overridden automatically if twin.profile["annual_revenue_bn"] is present.
_REVENUE_FALLBACK: dict[str, float] = {
    "WMT": 650_000,
    "AAPL": 380_000,
    "AMZN": 590_000,
    "XOM": 400_000,
    "TSMC": 90_000,
    "FDX": 90_000,
    "NVDA": 60_000,
    "AMD": 23_000,
    "MAERSK": 55_000,
    "DAL": 58_000,
}

# Sector → world-state keyword affinity for indirect impact estimation.
# Used when a company was not directly simulated but still has exposure
# to the shocked world-state via its sector or supply chain position.
_SECTOR_SHOCK_AFFINITY: dict[str, list[str]] = {
    "logistics":    ["shipping", "freight", "trade", "transport", "port"],
    "retail":       ["retail", "inventory", "consumer", "shipping", "trade"],
    "energy":       ["oil", "fuel", "energy", "gas", "petroleum"],
    "automotive":   ["auto", "vehicle", "production", "semiconductor"],
    "aviation":     ["fuel", "travel", "demand", "trade"],
    "airline":      ["fuel", "travel", "demand"],
    "banking":      ["rate", "credit", "financial", "liquidity"],
}


class CascadeEngine:
    """
    Runs a multi-company, multi-step cascade simulation.

    Algorithm (per time step):
      1. Identify which twins are affected (directly by scenario, or via graph propagation)
      2. Build each twin's context dict from the shared world_state
      3. Call twin.simulate(world_state, step) for each affected twin
      4. Merge each twin's world_state_updates into the shared world_state
      5. Apply scenario cascade_rules to propagate derived effects
      6. Discover newly affected twins (neighbors of affected set with large enough shocks)
      7. Repeat for next time step
    """

    def run(
        self,
        world: World,
        scenario: Scenario,
        time_steps: list[int] = [1, 7, 30, 90],
    ) -> WorldResult:
        world_state: dict[str, Any] = dict(scenario.initial_shocks)
        macro = copy.deepcopy(world.macro)
        macro.apply_shock(scenario.initial_shocks)

        initial_snapshot = WorldState(
            macro=macro.get_state(),
            twins={t: {} for t in world.twins},
        )

        cascade_timeline: list[TimeStepResult] = []
        all_decisions: dict[str, list[Decision]] = {t: [] for t in world.twins}

        affected_tickers = self._get_initially_affected(world, scenario)

        for step in time_steps:
            step_decisions: dict[str, Decision] = {}
            new_affected: list[str] = []

            for ticker in sorted(affected_tickers):  # deterministic ordering
                if ticker not in world.twins:
                    continue
                twin = world.twins[ticker]
                context = self._build_context(ticker, world_state, world, scenario, step)
                decision = twin.simulate(world_state=context, step=step)
                step_decisions[ticker] = decision
                all_decisions[ticker].append(decision)

                # Twin's decisions update the shared world_state immediately,
                # so subsequent twins in this step see the updated state.
                for key, delta in decision.world_state_updates.items():
                    world_state[key] = world_state.get(key, 0.0) + delta

            # Apply scenario-defined cascade rules: derived propagations.
            for rule in scenario.cascade_rules:
                if rule.from_key in world_state:
                    world_state[rule.to_key] = (
                        world_state.get(rule.to_key, 0.0)
                        + world_state[rule.from_key] * rule.multiplier
                    )

            cascade_timeline.append(
                TimeStepResult(
                    step=step,
                    decisions=step_decisions,
                    world_state=dict(world_state),
                    new_affected=new_affected,
                )
            )

            # Discover newly affected companies via the graph.
            newly = self._find_newly_affected(world, affected_tickers, world_state)
            if newly:
                new_affected.extend(newly)
                affected_tickers.update(newly)

        final_macro = copy.deepcopy(macro)
        final_macro.apply_shock(
            {k: v for k, v in world_state.items() if isinstance(v, float)}
        )

        final_snapshot = WorldState(
            macro=final_macro.get_state(),
            twins={
                ticker: {
                    "n_decisions": len(decisions),
                    "max_severity": max(
                        (
                            _impact_severity(d.financial_impact.get("severity", "low"))
                            for d in decisions
                        ),
                        default=0,
                    ),
                }
                for ticker, decisions in all_decisions.items()
            },
        )

        financial_impacts = self._compute_financial_impacts(
            world, all_decisions, initial_shocks=dict(scenario.initial_shocks)
        )
        most_affected = sorted(
            financial_impacts,
            key=lambda t: abs(financial_impacts[t].mid),
            reverse=True,
        )

        who_acted_first = [t for t in world.twins if all_decisions[t]]

        second_order = self._detect_second_order(cascade_timeline, scenario)
        stability = self._assess_stability(cascade_timeline)

        return WorldResult(
            scenario=scenario,
            world_snapshot_initial=initial_snapshot,
            world_snapshot_final=final_snapshot,
            cascade_timeline=cascade_timeline,
            financial_impacts=financial_impacts,
            most_affected=most_affected,
            least_affected=list(reversed(most_affected)),
            who_acted_first=who_acted_first,
            second_order_effects=second_order,
            system_stability=stability,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_initially_affected(self, world: World, scenario: Scenario) -> set[str]:
        """Identify twins directly affected by the scenario's initial shocks."""
        affected: set[str] = set()

        for ticker, twin in world.twins.items():
            profile = getattr(twin, "profile", {})
            twin_sector = profile.get("sector", "").lower()
            twin_inputs = [i.lower() for i in profile.get("key_inputs", [])]

            # Match by sector
            for sector in scenario.affected_sectors:
                if sector.lower() in twin_sector:
                    affected.add(ticker)
                    break

            # Match by input overlap with shock keys
            for shock_key in scenario.initial_shocks:
                shock_words = set(shock_key.lower().split("_"))
                for inp in twin_inputs:
                    inp_words = set(inp.lower().split("_"))
                    if shock_words & inp_words:
                        affected.add(ticker)
                        break

        # Ensure at least the first two twins are seeded so the demo works.
        if not affected:
            affected = set(list(world.twins.keys())[:2])

        return affected

    def _build_context(
        self,
        ticker: str,
        world_state: dict,
        world: World,
        scenario: Scenario,
        step: int,
    ) -> dict:
        """Build per-twin context by augmenting world_state with metadata."""
        context = dict(world_state)
        context["_scenario_title"] = scenario.title
        context["_scenario_severity"] = scenario.severity
        neighbors = world.graph.get_neighbors(ticker)
        if neighbors:
            context["_affected_partners"] = ", ".join(neighbors[:5])
        return context

    def _find_newly_affected(
        self,
        world: World,
        already_affected: set[str],
        world_state: dict,
    ) -> set[str]:
        """Pull in graph neighbors of currently affected tickers when shocks are large enough."""
        newly: set[str] = set()
        shock_total = sum(
            abs(v) for v in world_state.values() if isinstance(v, (int, float))
        )

        if shock_total > 0.3:
            for ticker in world.twins:
                if ticker not in already_affected:
                    neighbors = world.graph.get_neighbors(ticker)
                    if any(n in already_affected for n in neighbors):
                        newly.add(ticker)

        return newly

    def _compute_financial_impacts(
        self,
        world: World,
        all_decisions: dict[str, list[Decision]],
        initial_shocks: dict | None = None,
    ) -> dict[str, ImpactRange]:
        impacts: dict[str, ImpactRange] = {}

        for ticker, decisions in all_decisions.items():
            profile = getattr(world.twins[ticker], "profile", {})
            revenue = profile.get("annual_revenue_bn", _REVENUE_FALLBACK.get(ticker, 10)) * 1_000

            if decisions:
                avg_impact = sum(
                    d.financial_impact.get("revenue_impact_pct", 0.0) for d in decisions
                ) / len(decisions)
                spread_factor = 0.5
            else:
                # Not directly simulated — estimate indirect exposure from initial shocks.
                # Use initial_shocks (not final world_state) so LLM-driven mitigation
                # decisions don't erase the scenario's canonical severity for bystanders.
                avg_impact = self._estimate_indirect_impact(profile, initial_shocks or {})
                spread_factor = 0.8  # wider uncertainty for indirect estimates

            mid = revenue * avg_impact
            spread = abs(mid) * spread_factor
            impacts[ticker] = ImpactRange(
                low=mid - spread,
                mid=mid,
                high=mid + spread,
            )

        return impacts

    def _estimate_indirect_impact(self, profile: dict, shocks: dict) -> float:
        """
        Estimate fractional revenue impact for a company not directly simulated.

        Matches scenario initial_shocks to the company's key_inputs, key_risks,
        and sector affinity. Indirect exposure is dampened vs direct simulation:
        3% revenue sensitivity per matched shock unit.
        """
        sector = profile.get("sector", "").lower()

        # Build match terms from profile fields (skip short stop-words)
        terms: set[str] = set()
        for item in profile.get("key_inputs", []) + profile.get("key_risks", []):
            for word in item.lower().replace("-", "_").split("_"):
                if len(word) >= 4:
                    terms.add(word)
        # Augment with sector-level affinity keywords
        for sector_kw, affinity_terms in _SECTOR_SHOCK_AFFINITY.items():
            if sector_kw in sector:
                terms.update(affinity_terms)

        # Sum shocks whose key contains any matching term
        exposure = 0.0
        seen_keys: set[str] = set()
        for shock_key, shock_val in shocks.items():
            if not isinstance(shock_val, float) or shock_key in seen_keys:
                continue
            key_lower = shock_key.lower()
            if any(term in key_lower for term in terms):
                exposure += shock_val
                seen_keys.add(shock_key)

        # 3% revenue sensitivity per shock unit (indirect dampening)
        return exposure * 0.03

    def _detect_second_order(
        self,
        timeline: list[TimeStepResult],
        scenario: Scenario,
    ) -> list[str]:
        """Flag world-state keys that emerged beyond the initial shock set."""
        effects: list[str] = []
        initial_keys = set(scenario.initial_shocks.keys())

        for step_result in timeline[1:]:
            for key, val in step_result.world_state.items():
                if key.startswith("_") or key in initial_keys:
                    continue
                if isinstance(val, float) and abs(val) >= 0.05:
                    effects.append(
                        f"Day {step_result.step}: {key} moved to {val:+.1%}"
                    )

        return effects[:6]

    def _assess_stability(self, timeline: list[TimeStepResult]) -> str:
        """Characterize whether the cascade is converging, growing, or bifurcating."""
        if len(timeline) < 2:
            return "unknown"

        magnitudes = []
        for step_result in timeline:
            numeric = [
                abs(v)
                for v in step_result.world_state.values()
                if isinstance(v, (int, float))
            ]
            if numeric:
                magnitudes.append(sum(numeric))

        if len(magnitudes) < 2:
            return "unknown"

        trend = magnitudes[-1] - magnitudes[0]
        if trend < -0.1 * magnitudes[0]:
            return "stabilizing"
        elif trend > 0.5 * magnitudes[0]:
            return "escalating"
        else:
            return "bifurcating"


def _impact_severity(label: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(label, 0)
