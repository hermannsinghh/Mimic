#!/usr/bin/env python3
"""Record frozen-run cassettes for svb-replay-2023 against Claude Opus 4.5.

ONE-TIME recording session: runs ``ScenarioRunner`` against
``scenarios/svb-replay-2023/`` with ``ConcordiaPersonaBuilder`` driving a
``RecordingProvider`` wrapped around a live ``AnthropicProvider``. Every LLM
response gets captured to ``tests/fixtures/frozen-run/svb-replay-2023/`` so
subsequent CI runs replay deterministically via ``FrozenRunProvider``.

Usage:

    # canonical baseline (Anthropic Opus, audit-grade fixtures)
    ANTHROPIC_API_KEY=sk-ant-... python scripts/record_svb_cassettes.py

    # development-grade recording against DeepSeek (NOT the audit baseline —
    # cassettes land in svb-replay-2023-deepseek/, separate from the canonical
    # dir, so the canonical audit baseline stays empty until the Anthropic
    # recording session lands).
    MIMIC_RECORD_PROVIDER=deepseek python scripts/record_svb_cassettes.py
    # (DEEPSEEK_API_KEY is auto-loaded from packages/mimic-framework/deepseek.env)

Options (env vars):

    MIMIC_RECORD_PROVIDER       'anthropic' (default) or 'deepseek'
    MIMIC_RECORD_MODEL          override the model alias
                                (default: claude-opus-4-7 for anthropic,
                                 deepseek-chat for deepseek)
    MIMIC_RECORD_MODEL_VERSION  override the version string
                                (default: 2026-04 for anthropic, v3.2 for deepseek)
    MIMIC_RECORD_OUT            override the cassette output dir
    MIMIC_RECORD_DRY_RUN=1      use a stub provider (no network, no API spend)

The default canonical model is ``claude-opus-4-7`` per ADR
``decision-record/2026-05-22-anthropic-model-choice.md``. DeepSeek is the
forward-progress fallback while Anthropic key is unavailable — its cassettes
are committed for repeatability, but are clearly NOT the audit baseline.

The script refuses to run if ``MIMIC_FROZEN_RUN=1`` is set — that mode
expects cassettes to *exist*, and we're here to *create* them. The script
also refuses to run if the output directory already contains cassettes,
unless ``MIMIC_RECORD_OVERWRITE=1`` is set; this protects against
accidental re-recording (which would silently shift the audit baseline,
see ``tests/fixtures/frozen-run/README.md``).

For the audit trail, the script prints a summary at the end: count of
cassettes recorded, scenario name, model fingerprint, and the cassette
output directory. Commit the directory contents; do not commit secrets.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO_NAME = "svb-replay-2023"
SCENARIO_DIR = REPO_ROOT / "scenarios" / DEFAULT_SCENARIO_NAME

# Provider-specific suffix on the fixture dir name. Canonical (Anthropic)
# fixtures live at ``<scenario>/``; secondary providers live at
# ``<scenario>-<provider>/`` so the canonical dir stays empty until
# Anthropic is recorded.
_PROVIDER_SUFFIX = {"anthropic": "", "deepseek": "-deepseek"}


def _scenario_dir(name: str) -> Path:
    return REPO_ROOT / "scenarios" / name


def _cassette_dir(scenario_name: str, provider: str) -> Path:
    suffix = _PROVIDER_SUFFIX[provider]
    return REPO_ROOT / "tests" / "fixtures" / "frozen-run" / f"{scenario_name}{suffix}"


# ── liability networks (one per scenario; kept inline so recording is ──────
#    reproducible from this script alone) ──────────────────────────────────


def _svb_liability_network() -> dict:
    """svb-replay-2023 toy network (matches tests/scenario/test_audit_grade_refusal.py)."""
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


def _taiwan_strait_reinsurance_network() -> dict:
    """taiwan-strait-30d-closure toy network — cedents seeking reinsurance.

    MUST be byte-identical to
    ``tests/equivalence/test_equivalence.py::_toy_reinsurance_network``
    so the cassette cache_keys are stable: messages built from this
    network feed model_fingerprint → cache_key, and any drift here
    invalidates the recorded cassettes.
    """
    return {
        "schema": "mimic.world.liability/v1",
        "entities": [
            {
                "iri": "https://example.com/marine-mutual", "name": "MarineMutual",
                "industry": "marine_insurance", "equity": 3.2e9,
                "total_assets": 11e9, "loss_ratio": 0.72,
                "treaty_layer": "$500M xs $50M",
                "premium_offer_usd": 18e6,
                "expected_loss_usd": 12e6,
                "cat_model": {"scenario": "30d Taiwan strait closure",
                              "oep_1_in_50_usd": 320e6,
                              "oep_1_in_100_usd": 470e6,
                              "oep_1_in_200_usd": 580e6,
                              "aep_annual_usd": 14e6},
            },
            {
                "iri": "https://example.com/property-cat-co", "name": "PropertyCatCo",
                "industry": "property_cat", "equity": 5.5e9,
                "total_assets": 21e9, "loss_ratio": 0.65,
                "treaty_layer": "$1B xs $200M",
                "premium_offer_usd": 42e6,
                "expected_loss_usd": 35e6,
                "cat_model": {"scenario": "30d Taiwan strait closure",
                              "oep_1_in_50_usd": 680e6,
                              "oep_1_in_100_usd": 920e6,
                              "oep_1_in_200_usd": 1.05e9,
                              "aep_annual_usd": 38e6},
            },
            {
                "iri": "https://example.com/asia-property-trust",
                "name": "AsiaPropertyTrust",
                "industry": "property_cat", "equity": 2.1e9,
                "total_assets": 7.5e9, "loss_ratio": 0.68,
                "treaty_layer": "$300M xs $50M",
                "premium_offer_usd": 22e6,
                "expected_loss_usd": 15e6,
                "cat_model": {"scenario": "30d Taiwan strait closure",
                              "oep_1_in_50_usd": 240e6,
                              "oep_1_in_100_usd": 330e6,
                              "oep_1_in_200_usd": 410e6,
                              "aep_annual_usd": 16e6},
            },
            {
                "iri": "https://example.com/hong-kong-cargo",
                "name": "HongKongCargo",
                "industry": "marine_insurance", "equity": 1.8e9,
                "total_assets": 5.2e9, "loss_ratio": 0.75,
                "treaty_layer": "$100M xs $20M",
                "premium_offer_usd": 8e6,
                "expected_loss_usd": 6e6,
                "cat_model": {"scenario": "30d Taiwan strait closure",
                              "oep_1_in_50_usd": 95e6,
                              "oep_1_in_100_usd": 130e6,
                              "oep_1_in_200_usd": 160e6,
                              "aep_annual_usd": 6.5e6},
            },
            {
                "iri": "https://example.com/pacific-energy-mutual",
                "name": "PacificEnergyMutual",
                "industry": "energy", "equity": 4.5e9,
                "total_assets": 18e9, "loss_ratio": 0.60,
                "treaty_layer": "$800M xs $150M",
                "premium_offer_usd": 55e6,
                "expected_loss_usd": 40e6,
                "cat_model": {"scenario": "30d Taiwan strait closure",
                              "oep_1_in_50_usd": 540e6,
                              "oep_1_in_100_usd": 730e6,
                              "oep_1_in_200_usd": 870e6,
                              "aep_annual_usd": 42e6},
            },
            {
                "iri": "https://example.com/taiwan-life-insurance",
                "name": "TaiwanLifeInsurance",
                "industry": "life", "equity": 3.7e9,
                "total_assets": 28e9, "loss_ratio": 0.58,
                "treaty_layer": "$200M xs $40M",
                "premium_offer_usd": 15e6,
                "expected_loss_usd": 11e6,
                "cat_model": {"scenario": "30d Taiwan strait closure",
                              "oep_1_in_50_usd": 180e6,
                              "oep_1_in_100_usd": 240e6,
                              "oep_1_in_200_usd": 295e6,
                              "aep_annual_usd": 12e6},
            },
        ],
        "exposures": [
            {"debtor_iri": "https://example.com/marine-mutual",
             "creditor_iri": "https://example.com/property-cat-co",
             "amount": 200e6},
        ],
    }


_LIABILITY_NETWORKS: dict[str, Any] = {
    "svb-replay-2023": _svb_liability_network,
    "taiwan-strait-30d-closure": _taiwan_strait_reinsurance_network,
}


# ── stub provider used when MIMIC_RECORD_DRY_RUN=1 ─────────────────────────


class _DryRunProvider:
    """Imitates AnthropicProvider for rehearsal: returns canned JSON.

    Sufficient to walk the full ConcordiaPersonaBuilder → Prefab path and
    populate the cassette directory with fixture-shaped JSON files, but
    NOT with real Claude reasoning. Use to verify the recording machinery
    is wired correctly before spending API credits.
    """

    provider_name = "anthropic"
    model_name = "claude-opus-4-7"
    model_version = "2026-04-dry-run"

    def __init__(self) -> None:
        self._call_count = 0

    def estimate_cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0

    def complete(
        self, *, messages: list[dict], schema: dict | None, tools: list[dict] | None,
        temperature: float, seed: int | None, system_prompt: str = "",
    ):
        self._call_count += 1
        # Pick a response shape based on the schema/system_prompt the
        # caller asked for. Sufficient to satisfy the existing prefab and
        # the Concordia LM adapter without parsing the prompt.
        if "treaty" in system_prompt.lower() or "reinsurance" in system_prompt.lower():
            content: dict[str, Any] = {
                "action": "hold", "premium_usd": 0.0, "retention_usd": 0.0,
                "confidence": 0.7,
                "rationale": "[dry-run] no live model — placeholder rationale",
            }
        else:
            content = {
                "text": "[dry-run] I would proceed cautiously and protect capital.",
                "confidence": 0.7,
            }
        from mimic.framework.routing import StructuredResponse, compute_model_fingerprint
        return StructuredResponse(
            content=content, input_tokens=10, output_tokens=5, cost_usd=0.0,
            confidence=float(content.get("confidence", 0.7)),
            model_fingerprint=compute_model_fingerprint(
                provider=self.provider_name, model=self.model_name,
                version=self.model_version, system_prompt=system_prompt,
                temperature=temperature,
                tool_schema=tools[0] if tools else None,
            ),
        )


# ── recording entrypoint ───────────────────────────────────────────────────


def main() -> int:
    if os.environ.get("MIMIC_FROZEN_RUN") == "1":
        _fail(
            "MIMIC_FROZEN_RUN=1 is set. Recording expects to make live calls; "
            "unset MIMIC_FROZEN_RUN before running."
        )

    provider_name = os.environ.get("MIMIC_RECORD_PROVIDER", "anthropic").lower()
    if provider_name not in _PROVIDER_SUFFIX:
        _fail(f"unknown MIMIC_RECORD_PROVIDER={provider_name!r}. "
              f"Supported: {sorted(_PROVIDER_SUFFIX)}")
    if provider_name == "deepseek":
        _load_deepseek_env()

    scenario_name = os.environ.get("MIMIC_RECORD_SCENARIO", DEFAULT_SCENARIO_NAME)
    if scenario_name not in _LIABILITY_NETWORKS:
        _fail(f"unknown MIMIC_RECORD_SCENARIO={scenario_name!r}. "
              f"Supported: {sorted(_LIABILITY_NETWORKS)} "
              f"(or extend _LIABILITY_NETWORKS in this script).")
    scenario_dir = _scenario_dir(scenario_name)
    if not (scenario_dir / "scenario.yaml").is_file():
        _fail(f"no scenario.yaml at {scenario_dir}")

    default_out = _cassette_dir(scenario_name, provider_name)
    out_dir = Path(os.environ.get("MIMIC_RECORD_OUT", default_out))
    overwrite = os.environ.get("MIMIC_RECORD_OVERWRITE") == "1"
    if out_dir.exists() and any(out_dir.glob("*.json")) and not overwrite:
        _fail(
            f"refusing to overwrite cassettes in {out_dir} — set "
            "MIMIC_RECORD_OVERWRITE=1 to acknowledge the audit-baseline shift, "
            "and read tests/fixtures/frozen-run/README.md first."
        )
    out_dir.mkdir(parents=True, exist_ok=True)

    dry_run = os.environ.get("MIMIC_RECORD_DRY_RUN") == "1"
    inner_provider = _build_inner_provider(provider_name=provider_name, dry_run=dry_run)

    from mimic.framework.agents.concordia_runtime import ConcordiaPersonaBuilder
    from mimic.framework.agents.prefabs import ReinsurerTreatyPricer
    from mimic.framework.determinism import LocalFSBackend, RecordingProvider
    from mimic.framework.policy import PolicyDecisionPoint, load_bundle
    from mimic.framework.routing import RoutingCascade
    from mimic.framework.scenario import ScenarioRunner, load_spec

    recorder = RecordingProvider(inner_provider, LocalFSBackend(out_dir))

    # Mimic prefab + cascade also go through the recorder so both LLM paths
    # (Concordia agent reasoning AND prefab structured emission) end up in
    # the same fixture directory.
    cascade = RoutingCascade(t3=None, t2_a=None, t1=recorder, max_cost_usd=50.0)
    bundle_root = REPO_ROOT / "packages" / "mimic-framework" / "policy" / "opa"
    pdp = PolicyDecisionPoint(load_bundle(bundle_root))
    prefab = ReinsurerTreatyPricer(cascade=cascade, pdp=pdp)
    builder = ConcordiaPersonaBuilder(prefab=prefab, llm_provider=recorder)

    spec = load_spec(scenario_dir / "scenario.yaml")
    network = _LIABILITY_NETWORKS[scenario_name]()
    # audit_grade=False during recording — cassettes don't exist yet,
    # so the runner would refuse otherwise. The hash fields stay None
    # on this run; once cassettes are committed, CI runs MIMIC_FROZEN_RUN=1
    # which lets audit_grade=True emit a hash from replayed responses.
    runner = ScenarioRunner(pdp=pdp, persona_builder=builder, audit_grade=False)

    print(f"[record] scenario:       {scenario_name}")
    print(f"[record] cassette out:   {out_dir}")
    print(f"[record] inner provider: {inner_provider.provider_name}/"
          f"{inner_provider.model_name}/{inner_provider.model_version}")
    print(f"[record] dry-run:        {dry_run}")
    print(f"[record] starting run…")

    manifest = runner.run(spec, liability_network=network)

    print(f"[record] decisions:      {len(manifest.decisions)}")
    print(f"[record] cassettes:      {recorder.recorded_count}")
    print(f"[record] policy_version: {manifest.policy_version[:16]}…")
    print(f"[record] spec_hash:      {manifest.spec_hash[:16]}…")
    print(f"[record] audit_grade:    {manifest.audit_grade}  (hash fields stay None on record)")
    print(f"[record] DONE — commit the new files under {out_dir}")
    return 0


def _build_inner_provider(*, provider_name: str, dry_run: bool):
    if dry_run:
        print(f"[record] MIMIC_RECORD_DRY_RUN=1 → using _DryRunProvider "
              f"(target provider would have been {provider_name})")
        return _DryRunProvider()

    if provider_name == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            _fail(
                "ANTHROPIC_API_KEY not set. Either export the key, switch to "
                "MIMIC_RECORD_PROVIDER=deepseek for development, or set "
                "MIMIC_RECORD_DRY_RUN=1."
            )
        from mimic.framework.routing import AnthropicProvider
        model = os.environ.get("MIMIC_RECORD_MODEL", "claude-opus-4-7")
        version = os.environ.get("MIMIC_RECORD_MODEL_VERSION", "2026-04")
        print(f"[record] live Anthropic provider: model={model} version={version}")
        return AnthropicProvider(model=model, model_version=version)

    if provider_name == "deepseek":
        if not os.environ.get("DEEPSEEK_API_KEY"):
            _fail(
                "DEEPSEEK_API_KEY not set. Put it in packages/mimic-framework/"
                "deepseek.env or export it; or use MIMIC_RECORD_DRY_RUN=1 to "
                "rehearse without API spend."
            )
        from mimic.framework.routing import DeepSeekProvider
        model = os.environ.get("MIMIC_RECORD_MODEL", "deepseek-chat")
        version = os.environ.get("MIMIC_RECORD_MODEL_VERSION", "v3.2")
        print(f"[record] live DeepSeek provider: model={model} version={version}")
        return DeepSeekProvider(model=model, model_version=version)

    _fail(f"unknown provider {provider_name!r}")
    return None  # unreachable


def _load_deepseek_env() -> None:
    """Mirror the convention in ``packages/mimic-framework/mimic/llm.py``:
    if ``packages/mimic-framework/deepseek.env`` exists, populate env from it.
    Idempotent — existing env vars take precedence so an explicit
    ``DEEPSEEK_API_KEY=… python …`` invocation always wins.
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


def _fail(msg: str) -> None:
    sys.stderr.write(f"[record] ERROR: {msg}\n")
    sys.exit(2)


if __name__ == "__main__":
    raise SystemExit(main())
