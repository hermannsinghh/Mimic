#!/usr/bin/env python3
"""Measure within-runner noise floor of ConcordiaPersonaBuilder.

F-12 step 4. Runs ``tests.equivalence.measure_noise_floor`` against the real
``ConcordiaPersonaBuilder`` driving a live ``AnthropicProvider``, across N
seeds. Reports the max W1 per action_type and the max TV across the global
action-type histogram, so the F-12 equivalence ADR
(``decision-record/2026-05-21-runner-equivalence-criterion.md``) can be
checked: every threshold in its table must strictly exceed the measured
floor.

Why this needs a live LLM:

  * The harness mutates ``spec.spec.mc.seed_global`` per run. Most LLM
    APIs (Anthropic included) have no public seed parameter — variance
    between runs is the *model's* internal stochasticity at the requested
    temperature, not a function of the harness's seed.
  * Frozen-run cassettes turn the builder into a deterministic
    cache-replayer, which would trivially yield noise floor = 0 and tell
    us nothing about the real variance.
  * Stub providers are deterministic by construction; running the harness
    against a stub validates the harness mechanics (already covered by
    ``tests/equivalence/test_noise_floor.py``) but cannot measure the
    real ConcordiaPersonaBuilder's variance.

Usage:

    # canonical baseline
    ANTHROPIC_API_KEY=sk-ant-... python scripts/measure_concordia_noise_floor.py

    # forward-progress fallback against DeepSeek (DeepSeek HONORS seed, so this
    # is a meaningful within-runner-variance measurement even at temperature=0)
    MIMIC_NOISE_PROVIDER=deepseek python scripts/measure_concordia_noise_floor.py

Options (env vars):

    MIMIC_NOISE_PROVIDER       'anthropic' (default) or 'deepseek'
    MIMIC_NOISE_MODEL          override the model alias
                               (default: claude-opus-4-7 / deepseek-chat)
    MIMIC_NOISE_MODEL_VERSION  override the version string
                               (default: 2026-04 / v3.2)
    MIMIC_NOISE_SEEDS          comma-sep ints (default: four scenario seeds)
    MIMIC_NOISE_TEMPERATURE    LLM temperature for the measurement (default: 0.0,
                               matches the production cascade default)
    MIMIC_NOISE_DRY_RUN=1      use a deterministic stub (sanity-only;
                               will report 0.0 across the board)

Output:

  - Prints a per-group W1/TV summary to stdout.
  - Writes a JSON report to ``docs/status/<date>-concordia-noise-floor.json``
    so the ADR's threshold table can be audited against the recorded numbers.

The script refuses to run if ``MIMIC_FROZEN_RUN=1`` — measuring against the
cache defeats the purpose.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "svb-replay-2023"
STATUS_DIR = REPO_ROOT / "docs" / "status"
DEFAULT_SEEDS = (0x57AB1107, 0xCAFEF00D, 0x20080915, 0x6BD7BEEF)


def _svb_liability_network() -> dict:
    return {
        "schema": "mimic.world.liability/v1",
        "entities": [
            {"iri": "https://example.com/svb", "name": "SVB",
             "equity": 16e9, "total_assets": 209e9},
            {"iri": "https://example.com/fhlb", "name": "FHLB",
             "equity": 50e9, "total_assets": 1e12},
        ],
        "exposures": [
            {"debtor_iri": "https://example.com/svb",
             "creditor_iri": "https://example.com/fhlb",
             "amount": 14e9},
        ],
    }


class _DryRunProvider:
    """Stub provider for sanity rehearsal — always returns identical content.

    Running the noise-floor harness against this should yield W1 = 0 across
    every group. If it doesn't, the harness mechanics have drifted from
    ``tests/equivalence/test_noise_floor.py``'s assumptions.
    """

    provider_name = "anthropic"
    model_name = "claude-opus-4-7"
    model_version = "2026-04-dry-run"

    def estimate_cost_usd(self, i: int, o: int) -> float:
        return 0.0

    def complete(
        self, *, messages, schema, tools, temperature, seed, system_prompt="",
    ):
        sp = (system_prompt or "").lower()
        if "treaty" in sp or "reinsur" in sp:
            content: dict[str, Any] = {
                "action": "hold", "premium_usd": 0.0, "retention_usd": 0.0,
                "confidence": 0.7, "rationale": "[dry-run stub]",
            }
        else:
            content = {"text": "[dry-run stub] cautious response.", "confidence": 0.7}
        from mimic.framework.routing import StructuredResponse, compute_model_fingerprint
        return StructuredResponse(
            content=content, input_tokens=10, output_tokens=5, cost_usd=0.0,
            confidence=float(content.get("confidence", 0.7)),
            model_fingerprint=compute_model_fingerprint(
                provider=self.provider_name, model=self.model_name,
                version=self.model_version, system_prompt=system_prompt,
                temperature=temperature, tool_schema=tools[0] if tools else None,
            ),
        )


def main() -> int:
    if os.environ.get("MIMIC_FROZEN_RUN") == "1":
        _fail("MIMIC_FROZEN_RUN=1 turns the builder into a cache-replayer — "
              "noise floor would trivially be 0. Unset MIMIC_FROZEN_RUN.")

    dry_run = os.environ.get("MIMIC_NOISE_DRY_RUN") == "1"
    provider = _build_provider(dry_run=dry_run)
    seeds = _parse_seeds(os.environ.get("MIMIC_NOISE_SEEDS"))

    from mimic.framework.agents.concordia_runtime import ConcordiaPersonaBuilder
    from mimic.framework.agents.prefabs import ReinsurerTreatyPricer
    from mimic.framework.policy import PolicyDecisionPoint, load_bundle
    from mimic.framework.routing import RoutingCascade
    from mimic.framework.scenario import ScenarioRunner, load_spec

    bundle = REPO_ROOT / "packages" / "mimic-framework" / "policy" / "opa"
    pdp = PolicyDecisionPoint(load_bundle(bundle))

    def runner_factory():
        cascade = RoutingCascade(t3=None, t2_a=None, t1=provider, max_cost_usd=50.0)
        prefab = ReinsurerTreatyPricer(cascade=cascade, pdp=pdp)
        builder = ConcordiaPersonaBuilder(prefab=prefab, llm_provider=provider)
        # audit_grade=False: noise-floor measurement is by design not
        # audit-grade — we're measuring variance, not emitting a hash.
        return ScenarioRunner(pdp=pdp, persona_builder=builder, audit_grade=False)

    sys.path.insert(0, str(REPO_ROOT))  # so tests.equivalence resolves
    from tests.equivalence import measure_noise_floor

    spec = load_spec(SCENARIO_DIR / "scenario.yaml")
    print(f"[noise-floor] scenario:    {SCENARIO_DIR.name}")
    print(f"[noise-floor] provider:    {provider.provider_name}/"
          f"{provider.model_name}/{provider.model_version}")
    print(f"[noise-floor] seeds:       {[hex(s) for s in seeds]}")
    print(f"[noise-floor] dry-run:     {dry_run}")
    print(f"[noise-floor] running {len(seeds)} scenario passes…")

    result = measure_noise_floor(
        runner_factory=runner_factory,
        spec=spec,
        liability_network=_svb_liability_network(),
        seeds=seeds,
    )

    print("[noise-floor] pairs:       ", result.n_pairs)
    print("[noise-floor] max W1 / group:")
    for g, v in sorted(result.max_w1_per_group.items()):
        print(f"  {g:>20}  {v:>14,.4f}")
    print("[noise-floor] mean W1 / group:")
    for g, v in sorted(result.mean_w1_per_group.items()):
        print(f"  {g:>20}  {v:>14,.4f}")
    print(f"[noise-floor] max TV (global action-type): "
          f"{result.max_tv_per_group['__global_action_type__']:.4f}")
    print(f"[noise-floor] mean TV (global action-type): "
          f"{result.mean_tv_per_group['__global_action_type__']:.4f}")

    out_path = _write_status_report(provider, seeds, result, dry_run=dry_run)
    print(f"[noise-floor] report → {out_path}")
    _check_thresholds_against_floor(result)
    return 0


def _check_thresholds_against_floor(result) -> None:
    """Compare the equivalence ADR's threshold table against the measured floor.

    Per ``decision-record/2026-05-21-runner-equivalence-criterion.md``, a
    threshold below the measured floor is a tightening-the-prefab signal
    (do not loosen the threshold; tighten the prefab — that ADR rejects
    empirical fits).
    """
    # ReinsurerTreatyPricer is the only F-12 step-5 prefab. The action_type
    # the runner records for it is either 'reinsure' or 'hold' per
    # ReinsurerTreatyPricer._response_to_decision.
    proposed_w1 = {
        "reinsure": 50_000_000.0,  # $50M, ADR's initial placeholder
        "hold": 50_000_000.0,
    }
    violated = result.floor_violated(proposed_w1)
    if violated:
        print(f"[noise-floor] WARNING: threshold(s) {violated} are at or below the "
              f"measured noise floor. Tighten the prefab (or revise the ADR's "
              f"threshold with new provenance) before F-12 step 5.")
    else:
        print(f"[noise-floor] thresholds vs floor: clean (all proposed thresholds "
              f"strictly above the measured noise floor).")


def _write_status_report(provider, seeds, result, *, dry_run: bool) -> Path:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = STATUS_DIR / f"{date.today().isoformat()}-concordia-noise-floor.json"
    payload = {
        "schema": "mimic.f12.noise_floor/v1",
        "scenario": "svb-replay-2023",
        "provider": provider.provider_name,
        "model": provider.model_name,
        "model_version": provider.model_version,
        "seeds": [int(s) for s in seeds],
        "dry_run": dry_run,
        "n_pairs": result.n_pairs,
        "max_w1_per_group": {k: float(v) for k, v in result.max_w1_per_group.items()},
        "mean_w1_per_group": {k: float(v) for k, v in result.mean_w1_per_group.items()},
        "max_tv_per_group": {k: float(v) for k, v in result.max_tv_per_group.items()},
        "mean_tv_per_group": {k: float(v) for k, v in result.mean_tv_per_group.items()},
        "per_group_sample_counts": dict(result.per_group_sample_counts),
        "adr_ref": "decision-record/2026-05-21-runner-equivalence-criterion.md",
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return out_path


def _build_provider(*, dry_run: bool):
    provider_name = os.environ.get("MIMIC_NOISE_PROVIDER", "anthropic").lower()
    if dry_run:
        print(f"[noise-floor] MIMIC_NOISE_DRY_RUN=1 → _DryRunProvider "
              f"(target provider would have been {provider_name})")
        return _DryRunProvider()

    if provider_name == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            _fail("ANTHROPIC_API_KEY not set. Try MIMIC_NOISE_PROVIDER=deepseek "
                  "for a forward-progress measurement, or MIMIC_NOISE_DRY_RUN=1 "
                  "for a sanity rehearsal.")
        from mimic.framework.routing import AnthropicProvider
        model = os.environ.get("MIMIC_NOISE_MODEL", "claude-opus-4-7")
        version = os.environ.get("MIMIC_NOISE_MODEL_VERSION", "2026-04")
        print(f"[noise-floor] live Anthropic provider: model={model} version={version}")
        return AnthropicProvider(model=model, model_version=version)

    if provider_name == "deepseek":
        _load_deepseek_env()
        if not os.environ.get("DEEPSEEK_API_KEY"):
            _fail("DEEPSEEK_API_KEY not set. Put it in packages/mimic-framework/"
                  "deepseek.env or export it.")
        from mimic.framework.routing import DeepSeekProvider
        model = os.environ.get("MIMIC_NOISE_MODEL", "deepseek-chat")
        version = os.environ.get("MIMIC_NOISE_MODEL_VERSION", "v3.2")
        print(f"[noise-floor] live DeepSeek provider: model={model} version={version}")
        return DeepSeekProvider(model=model, model_version=version)

    _fail(f"unknown MIMIC_NOISE_PROVIDER={provider_name!r}. "
          f"Supported: anthropic, deepseek")
    return None  # unreachable


def _load_deepseek_env() -> None:
    """Auto-load ``packages/mimic-framework/deepseek.env`` if present.
    Mirrors the convention in ``mimic/llm.py``. Existing env vars take
    precedence so an explicit ``DEEPSEEK_API_KEY=… python …`` invocation wins.
    """
    env_path = REPO_ROOT / "packages" / "mimic-framework" / "deepseek.env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
        return
    except ImportError:
        pass
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def _parse_seeds(raw: str | None) -> tuple[int, ...]:
    if not raw:
        return DEFAULT_SEEDS
    try:
        return tuple(int(s, 0) for s in raw.split(","))
    except ValueError as exc:
        _fail(f"could not parse MIMIC_NOISE_SEEDS={raw!r}: {exc}")
        return ()  # unreachable


def _fail(msg: str) -> None:
    sys.stderr.write(f"[noise-floor] ERROR: {msg}\n")
    sys.exit(2)


if __name__ == "__main__":
    raise SystemExit(main())
