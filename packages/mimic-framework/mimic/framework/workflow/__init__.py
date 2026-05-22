"""Temporal workflow definitions — Plan §8.

The spine is `ScenarioRunWorkflow`. Child workflows: `SeedPersonasWorkflow`,
`DecisionPhaseWorkflow`, `MCWorkflow`. Activities are pure functions in
`activities.py` and are called via Temporal's `execute_activity`.

Versioning uses `workflow.patched()` — never edit a deployed workflow's
deterministic path; add a patch branch.

`temporalio` is an optional import; the module is usable without it for
schema inspection and offline testing. Live execution requires `pip install
temporalio` and a Temporal server.
"""
from .activities import (  # noqa: F401
    propagate_contagion,
    pull_signed_scenario,
    sign_run_manifest,
)
from .scenario_run import (  # noqa: F401
    RunResult,
    ScenarioRunWorkflow,
    has_temporalio,
)

__all__ = [
    "ScenarioRunWorkflow",
    "RunResult",
    "has_temporalio",
    "pull_signed_scenario",
    "propagate_contagion",
    "sign_run_manifest",
]
