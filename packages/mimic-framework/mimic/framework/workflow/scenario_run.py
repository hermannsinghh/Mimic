"""ScenarioRunWorkflow — Plan §8.1.

The orchestration spine. Phases:
    1. Resolve & verify scenario artifact
    2. Ingest data (parallel fan-out)
    3. Persona seeding (T1 & T2 only; T3 sector-sampled)
    4. Strategic decision phase (agent reasoning)
    5. Monte Carlo over uncertainty (sharded)
    6. Contagion propagation (EN + DebtRank)
    7. Optional re-loop
    8. Emit signed run manifest

Importable without a running Temporal server; the decorators activate when
`temporalio` is installed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:  # pragma: no cover - import-time branch
    from temporalio import workflow  # type: ignore[import-not-found]
    has_temporalio = True
    _WORKFLOW_DEFN = workflow.defn
    _WORKFLOW_RUN = workflow.run
except ImportError:
    has_temporalio = False

    def _WORKFLOW_DEFN(cls=None, **kwargs):
        if cls is None:
            return lambda c: c
        return cls

    def _WORKFLOW_RUN(fn):
        return fn


@dataclass(frozen=True)
class RunResult:
    manifest_digest: str
    world_state_hash_final: str
    decisions_emitted: int
    outcomes_emitted: int
    cost_usd: float
    metadata: dict[str, Any] = field(default_factory=dict)


@_WORKFLOW_DEFN(name="ScenarioRunWorkflow")
class ScenarioRunWorkflow:
    """The Mimic orchestration spine. Plan §8.1.

    The body documents the phase sequence. Each `execute_activity` call is
    deterministic from Temporal's perspective — the activity is what does I/O.
    """

    @_WORKFLOW_RUN
    async def run(self, scenario_uri: str, as_of: str) -> RunResult:
        # 1. Resolve & verify scenario artifact (F-02 + F-03)
        # scenario = await workflow.execute_activity(pull_signed_scenario, scenario_uri, ...)
        # 2. Ingest data (parallel fan-out, one activity per source)
        # data_refs = await asyncio.gather(*[
        #     workflow.execute_activity(fetch_source, src, as_of) for src in scenario.sources
        # ])
        # 3. Persona seeding (child workflow; T1 & T2 only)
        # personas = await workflow.execute_child_workflow(SeedPersonasWorkflow.run, data_refs)
        # 4. Strategic decision phase (child workflow)
        # decisions = await workflow.execute_child_workflow(DecisionPhaseWorkflow.run, personas, scenario.event)
        # 5. Monte Carlo over uncertainty (sharded)
        # outcomes = await workflow.execute_child_workflow(MCWorkflow.run, decisions, scenario.mc)
        # 6. Contagion propagation
        # cascade = await workflow.execute_activity(propagate_contagion, outcomes)
        # 7. Optional re-loop
        # if scenario.reloop:
        #     ...
        # 8. Emit signed run manifest
        # manifest = await workflow.execute_activity(sign_run_manifest, cascade)
        raise NotImplementedError(
            "ScenarioRunWorkflow body is the skeleton. Requires Temporal worker "
            "+ F-02/F-03 (scenario pull), F-05 child workflows, F-06 routing, "
            "F-07 hashing wired through, and W-04 contagion network."
        )


@_WORKFLOW_DEFN(name="SeedPersonasWorkflow")
class SeedPersonasWorkflow:
    """Fans out one Concordia persona-builder per Tier-1/2 entity."""

    @_WORKFLOW_RUN
    async def run(self, data_refs: list) -> list[dict]:
        raise NotImplementedError("requires F-12 Concordia integration")


@_WORKFLOW_DEFN(name="DecisionPhaseWorkflow")
class DecisionPhaseWorkflow:
    """LangGraph reasoning graph per entity; routing layer picks tier."""

    @_WORKFLOW_RUN
    async def run(self, personas: list, event: dict) -> list[dict]:
        raise NotImplementedError("requires F-06 + F-12 wiring")


@_WORKFLOW_DEFN(name="MCWorkflow")
class MCWorkflow:
    """Fans out MC shards to Modal; each shard is an activity with its own seed."""

    @_WORKFLOW_RUN
    async def run(self, decisions: list, mc_config: dict) -> list[dict]:
        raise NotImplementedError("requires Modal worker bring-up")
