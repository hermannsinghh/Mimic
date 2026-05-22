"""Tests for the Temporal workflow skeleton — Plan §8.

Verifies that the workflow module is importable, classes are discoverable,
and the contract surface is present — without requiring a running Temporal
server. End-to-end workflow execution is tested separately (requires
`temporalio` installed and a Temporal dev-server running).
"""
from __future__ import annotations

import inspect

import pytest

from mimic.framework.workflow import (
    RunResult,
    ScenarioRunWorkflow,
    has_temporalio,
    pull_signed_scenario,
    propagate_contagion,
    sign_run_manifest,
)
from mimic.framework.workflow.scenario_run import (
    DecisionPhaseWorkflow,
    MCWorkflow,
    SeedPersonasWorkflow,
)


def test_scenario_run_workflow_class_is_importable():
    assert inspect.isclass(ScenarioRunWorkflow)
    assert hasattr(ScenarioRunWorkflow, "run")
    assert inspect.iscoroutinefunction(ScenarioRunWorkflow.run)


def test_child_workflows_exist():
    for cls in (SeedPersonasWorkflow, DecisionPhaseWorkflow, MCWorkflow):
        assert inspect.isclass(cls)
        assert hasattr(cls, "run")
        assert inspect.iscoroutinefunction(cls.run)


def test_activities_are_async():
    for fn in (pull_signed_scenario, propagate_contagion, sign_run_manifest):
        assert inspect.iscoroutinefunction(fn)


def test_run_result_shape():
    rr = RunResult(
        manifest_digest="sha256:abc",
        world_state_hash_final="deadbeef",
        decisions_emitted=10, outcomes_emitted=100, cost_usd=12.5,
    )
    assert rr.manifest_digest == "sha256:abc"
    assert rr.metadata == {}


def test_workflow_body_raises_until_wired():
    """ScenarioRunWorkflow.run intentionally raises until F-02/F-05/etc. land."""
    wf = ScenarioRunWorkflow()
    import asyncio
    with pytest.raises(NotImplementedError):
        asyncio.run(wf.run("https://hub/scenarios/svb-replay-2023:0.1.0", "2023-03-08"))


def test_module_works_without_temporalio():
    """The skeleton must import even when temporalio isn't installed."""
    assert isinstance(has_temporalio, bool)
