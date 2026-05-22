"""WorldResult, TimeStepResult, Decision — the output types of a cascade simulation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Decision:
    """One company's response at one time step."""

    ticker: str
    step: int
    actions: list[str]
    reasoning: str
    world_state_updates: dict[str, float]
    financial_impact: dict[str, Any]


@dataclass
class ImpactRange:
    """P10 / P50 / P90 financial impact in $M."""

    low: float
    mid: float
    high: float

    def __str__(self) -> str:
        if self.low == 0.0 and self.mid == 0.0 and self.high == 0.0:
            return "not directly impacted"
        def _b(v: float) -> str:
            return f"${v / 1_000:+.1f}B"
        # high=P10 (mildest loss), mid=P50, low=P90 (worst) — VaR convention
        return f"P10: {_b(self.high)} / P50: {_b(self.mid)} / P90: {_b(self.low)}"


@dataclass
class WorldState:
    """Snapshot of the world at a point in time."""

    macro: dict[str, Any] = field(default_factory=dict)
    twins: dict[str, dict] = field(default_factory=dict)

    def copy(self) -> WorldState:
        return WorldState(
            macro={k: dict(v) if isinstance(v, dict) else v for k, v in self.macro.items()},
            twins={k: dict(v) for k, v in self.twins.items()},
        )


@dataclass
class TimeStepResult:
    """Everything that happened during one time step of the cascade."""

    step: int
    decisions: dict[str, Decision] = field(default_factory=dict)
    world_state: dict[str, float] = field(default_factory=dict)
    new_affected: list[str] = field(default_factory=list)


@dataclass
class WorldResult:
    """Full output of World.run(scenario)."""

    scenario: Any
    world_snapshot_initial: WorldState
    world_snapshot_final: WorldState
    cascade_timeline: list[TimeStepResult] = field(default_factory=list)
    financial_impacts: dict[str, ImpactRange] = field(default_factory=dict)
    most_affected: list[str] = field(default_factory=list)
    least_affected: list[str] = field(default_factory=list)
    who_acted_first: list[str] = field(default_factory=list)
    second_order_effects: list[str] = field(default_factory=list)
    system_stability: str = "unknown"

    def compare(self, other: WorldResult) -> dict:
        return {
            "scenario_a": self.scenario.id,
            "scenario_b": other.scenario.id,
            "stability_a": self.system_stability,
            "stability_b": other.system_stability,
            "most_affected_a": self.most_affected[:3],
            "most_affected_b": other.most_affected[:3],
            "second_order_a": self.second_order_effects,
            "second_order_b": other.second_order_effects,
        }

    def export(self, format: str = "json") -> str:
        if format != "json":
            raise ValueError(f"Unsupported export format: {format!r}")

        data = {
            "scenario": self.scenario.id if hasattr(self.scenario, "id") else str(self.scenario),
            "system_stability": self.system_stability,
            "most_affected": self.most_affected,
            "least_affected": self.least_affected,
            "who_acted_first": self.who_acted_first,
            "second_order_effects": self.second_order_effects,
            "financial_impacts": {
                ticker: {"low": r.low, "mid": r.mid, "high": r.high}
                for ticker, r in self.financial_impacts.items()
            },
            "cascade_timeline": [
                {
                    "step": step.step,
                    "new_affected": step.new_affected,
                    "world_state": {
                        k: v
                        for k, v in step.world_state.items()
                        if not k.startswith("_")
                    },
                    "decisions": {
                        ticker: {
                            "actions": d.actions,
                            "reasoning": d.reasoning,
                            "financial_impact": d.financial_impact,
                            "world_state_updates": d.world_state_updates,
                        }
                        for ticker, d in step.decisions.items()
                    },
                }
                for step in self.cascade_timeline
            ],
        }
        return json.dumps(data, indent=2)

    def print_summary(self) -> None:
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            console = Console()
        except ImportError:
            self._print_summary_plain()
            return

        console.print(
            Panel(
                f"[bold]{self.scenario.title}[/bold]\n"
                f"Severity: {self.scenario.severity:.0%}  |  "
                f"Duration: {self.scenario.duration_days}d  |  "
                f"Steps: {len(self.cascade_timeline)}  |  "
                f"Stability: [yellow]{self.system_stability}[/yellow]",
                title="[cyan]mimic-world[/cyan]",
            )
        )

        if self.financial_impacts:
            table = Table(title="Financial Impacts (P10 / P50 / P90)")
            table.add_column("Ticker", style="cyan")
            table.add_column("Low", justify="right")
            table.add_column("Mid", justify="right", style="yellow")
            table.add_column("High", justify="right")

            for ticker in self.most_affected:
                impact = self.financial_impacts.get(ticker)
                if impact:
                    table.add_row(
                        ticker,
                        f"${impact.low:,.0f}M",
                        f"${impact.mid:,.0f}M",
                        f"${impact.high:,.0f}M",
                    )
            console.print(table)

        if self.second_order_effects:
            console.print("\n[bold]Second-order effects:[/bold]")
            for effect in self.second_order_effects:
                console.print(f"  • {effect}")

        for step_result in self.cascade_timeline:
            console.print(f"\n[bold cyan]── Day {step_result.step} ──[/bold cyan]")
            for ticker, decision in step_result.decisions.items():
                console.print(f"  [yellow]{ticker}[/yellow]: {decision.reasoning}")
                for action in decision.actions:
                    console.print(f"    → {action}")

    def _print_summary_plain(self) -> None:
        print(f"\n{'='*60}")
        print(f"mimic-world: {self.scenario.title}")
        print(f"Stability: {self.system_stability}")
        print(f"Most affected: {', '.join(self.most_affected[:5])}")
        if self.second_order_effects:
            print("\nSecond-order effects:")
            for e in self.second_order_effects:
                print(f"  • {e}")
        for step_result in self.cascade_timeline:
            print(f"\n── Day {step_result.step} ──")
            for ticker, decision in step_result.decisions.items():
                print(f"  {ticker}: {decision.reasoning}")
                for action in decision.actions:
                    print(f"    → {action}")
