#!/usr/bin/env python3
"""Record frozen-run cassettes for svb-replay-2023.

ONE-TIME recording session: runs ``ScenarioRunner`` against
``scenarios/svb-replay-2023/`` with ``ConcordiaPersonaBuilder`` driving a
``RecordingProvider`` wrapped around a live ``AnthropicProvider`` or
``DeepSeekProvider``. Every LLM response gets captured under
``tests/fixtures/frozen-run/svb-replay-2023[-<provider>]/`` so subsequent
CI runs replay deterministically via ``FrozenRunProvider``.

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
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "svb-replay-2023"

# Provider-specific default fixture dirs. The canonical Anthropic baseline
# lives at ``svb-replay-2023/`` and is the F-12 audit fixture set per
# ``decision-record/2026-05-22-anthropic-model-choice.md``. DeepSeek
# cassettes live alongside but at ``svb-replay-2023-deepseek/`` so the
# canonical dir stays empty until Anthropic is recorded.
_OUT_DIR_BY_PROVIDER = {
    "anthropic": REPO_ROOT / "tests" / "fixtures" / "frozen-run" / "svb-replay-2023",
    "deepseek":  REPO_ROOT / "tests" / "fixtures" / "frozen-run" / "svb-replay-2023-deepseek",
}


# ── liability network (matches tests/scenario/test_audit_grade_refusal.py) ──


def _svb_liability_network() -> dict:
    """The svb-replay-2023 toy network used by the runner e2e test.

    Kept inline rather than loaded from a YAML so the recording is fully
    reproducible from the script itself — if someone six months from now
    re-records cassettes, they re-record against the same network bytes.
    """
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
    if provider_name not in _OUT_DIR_BY_PROVIDER:
        _fail(f"unknown MIMIC_RECORD_PROVIDER={provider_name!r}. "
              f"Supported: {sorted(_OUT_DIR_BY_PROVIDER)}")
    if provider_name == "deepseek":
        _load_deepseek_env()

    default_out = _OUT_DIR_BY_PROVIDER[provider_name]
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

    spec = load_spec(SCENARIO_DIR / "scenario.yaml")
    # audit_grade=False during recording — cassettes don't exist yet,
    # so the runner would refuse otherwise. The hash fields stay None
    # on this run; once cassettes are committed, CI runs MIMIC_FROZEN_RUN=1
    # which lets audit_grade=True emit a hash from replayed responses.
    runner = ScenarioRunner(pdp=pdp, persona_builder=builder, audit_grade=False)

    print(f"[record] scenario:       {SCENARIO_DIR.name}")
    print(f"[record] cassette out:   {out_dir}")
    print(f"[record] inner provider: {inner_provider.provider_name}/"
          f"{inner_provider.model_name}/{inner_provider.model_version}")
    print(f"[record] dry-run:        {dry_run}")
    print(f"[record] starting run…")

    manifest = runner.run(spec, liability_network=_svb_liability_network())

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
