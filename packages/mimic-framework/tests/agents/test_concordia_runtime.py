"""Tests for ``mimic.framework.agents.concordia_runtime`` — F-12 step 2.

The Concordia agent is exercised with a fake ``LLMProvider`` that returns
``{"text": "..."}`` so the whole act-component pipeline completes without a
live API call. The Mimic ``Prefab`` is exercised with the real
``RoutingCascade``/``PolicyDecisionPoint`` wiring and a second fake provider
returning the canonical reinsurer-treaty shape — same setup
``tests/agents/test_prefabs.py`` already uses, just inside the
``ConcordiaPersonaBuilder`` __call__.

These tests pin the contract surface F-12 step 2 promises:

  * ``is_deterministic = False`` (so the audit-grade refusal contract fires)
  * one ``Decision`` per entity
  * imports route through ``mimic_concordia.*`` (Plan §9.1 vendor boundary)
  * ``MimicProviderAsConcordiaLM.sample_text`` and ``sample_choice`` round-trip
    cleanly through the Mimic provider contract
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mimic.framework.agents.concordia_runtime import (
    DEFAULT_SYSTEM_PROMPT,
    ConcordiaPersonaBuilder,
    MimicProviderAsConcordiaLM,
    SHA256UnitEmbedder,
)
from mimic.framework.agents.prefabs import (
    PrefabRunError,
    ReinsurerTreatyPricer,
)
from mimic.framework.policy import PolicyDecisionPoint, load_bundle
from mimic.framework.routing import (
    RoutingCascade,
    StructuredResponse,
    compute_model_fingerprint,
)
from mimic.framework.scenario.runner import _is_deterministic

_BUNDLE = Path(__file__).resolve().parents[2] / "policy" / "opa"


# ── stub providers ──────────────────────────────────────────────────────────


class _FreeTextProvider:
    """Stub LLMProvider for the Concordia LM adapter — always returns text."""

    provider_name = "stub-free-text"
    model_name = "stub-free-text"
    model_version = "2026-01"

    def __init__(self, text: str = "I would proceed cautiously and protect capital.") -> None:
        self._text = text
        self.calls: list[dict] = []

    def estimate_cost_usd(self, i: int, o: int) -> float:
        return 0.0

    def complete(self, *, messages, schema, tools, temperature, seed, system_prompt=""):
        self.calls.append({"messages": messages, "schema": schema, "system_prompt": system_prompt})
        # Honor the schema=None → {"text": str} convention the adapter relies on.
        content: dict = {"text": self._text}
        if schema is not None and "properties" in schema and "index" in schema["properties"]:
            content = {"index": 0}
        return StructuredResponse(
            content=content,
            input_tokens=10, output_tokens=5, cost_usd=0.0,
            confidence=0.9,
            model_fingerprint=compute_model_fingerprint(
                provider=self.provider_name, model=self.model_name,
                version=self.model_version, system_prompt=system_prompt,
                temperature=temperature, tool_schema=schema,
            ),
        )


class _CannedShapeProvider:
    """Stub LLMProvider for the Mimic prefab cascade — returns a fixed content dict."""

    def __init__(self, name: str, content: dict) -> None:
        self.provider_name = name
        self.model_name = name
        self.model_version = "2026-01"
        self._content = content
        self.calls = 0

    def estimate_cost_usd(self, i: int, o: int) -> float:
        return 0.01

    def complete(self, *, messages, schema, tools, temperature, seed, system_prompt=""):
        self.calls += 1
        return StructuredResponse(
            content=self._content,
            input_tokens=10, output_tokens=5, cost_usd=0.01,
            confidence=float(self._content.get("confidence", 0.9)),
            model_fingerprint=compute_model_fingerprint(
                provider=self.provider_name, model=self.model_name,
                version=self.model_version, system_prompt=system_prompt,
                temperature=temperature, tool_schema=None,
            ),
        )


def _cascade_with(content: dict, tier: str) -> tuple[RoutingCascade, _CannedShapeProvider]:
    p = _CannedShapeProvider("fake", content)
    kwargs = {"t3": None, "t2_a": None, "t1": None, "max_cost_usd": 5.0}
    kwargs[{"T1": "t1", "T2": "t2_a", "T3": "t3"}[tier]] = p
    return RoutingCascade(**kwargs), p


@pytest.fixture
def pdp() -> PolicyDecisionPoint:
    return PolicyDecisionPoint(load_bundle(_BUNDLE))


# ── core contract ──────────────────────────────────────────────────────────


def test_is_deterministic_attribute_is_false() -> None:
    """The audit-grade refusal contract (ADR 2026-05-21-audit-grade-refusal)
    keys on this attribute. False forces ``ScenarioRunner`` to require
    frozen-run mode or an explicit ``audit_grade=False`` opt-out."""
    assert ConcordiaPersonaBuilder.is_deterministic is False


def test_is_deterministic_helper_treats_builder_as_nondeterministic(pdp) -> None:
    """The runner's ``_is_deterministic`` helper must agree."""
    cascade, _ = _cascade_with({"action": "hold", "premium_usd": 0.0,
                                "retention_usd": 0.0, "confidence": 0.9,
                                "rationale": "ok"}, tier="T1")
    builder = ConcordiaPersonaBuilder(
        prefab=ReinsurerTreatyPricer(cascade=cascade, pdp=pdp),
        llm_provider=_FreeTextProvider(),
    )
    assert _is_deterministic(builder) is False


def test_imports_route_through_mimic_concordia() -> None:
    """Plan §9.1 wrapper boundary: nothing inside the runtime imports raw concordia.

    We approximate "nothing imports raw concordia" by asserting that the
    builder module's own source has no top-level ``import concordia`` /
    ``from concordia`` line. This is a deliberately mechanical check —
    cheap regression signal.
    """
    import importlib.resources
    src = (importlib.resources.files(
        "mimic.framework.agents.concordia_runtime"
    ) / "builder.py").read_text(encoding="utf-8")
    for forbidden in ("\nimport concordia", "\nfrom concordia "):
        assert forbidden not in src, f"raw concordia import in builder.py: {forbidden!r}"
    src_lm = (importlib.resources.files(
        "mimic.framework.agents.concordia_runtime"
    ) / "language_model.py").read_text(encoding="utf-8")
    for forbidden in ("\nimport concordia", "\nfrom concordia "):
        assert forbidden not in src_lm, f"raw concordia import in language_model.py: {forbidden!r}"


# ── happy path ──────────────────────────────────────────────────────────────


def test_produces_one_decision_per_entity(pdp) -> None:
    cascade, prefab_provider = _cascade_with(
        {"action": "reinsure", "premium_usd": 1_000_000.0,
         "retention_usd": 5_000_000.0, "confidence": 0.85,
         "rationale": "tail-risk acceptable at this price"},
        tier="T1",
    )
    builder = ConcordiaPersonaBuilder(
        prefab=ReinsurerTreatyPricer(cascade=cascade, pdp=pdp),
        llm_provider=_FreeTextProvider(text="I would underwrite this treaty."),
    )
    scenario_ctx = {
        "event": {"name": "TaiwanStraitClosure", "description": "30-day blockade."},
        "entities": [
            {"iri": "https://example.com/cedent-a", "name": "CedentA"},
            {"iri": "https://example.com/cedent-b", "name": "CedentB"},
        ],
        "scope": {"name": "reinsurer"},
    }
    decisions = builder(scenario_ctx)
    assert len(decisions) == 2
    for d in decisions:
        assert d.action_type == "reinsure"
        assert d.unit == "USD"
        assert d.quantity == pytest.approx(1_000_000.0)
        assert d.agent_did.startswith("did:web:concordia.cedent-")
    assert prefab_provider.calls == 2  # one per entity


def test_agent_did_uses_iri_tail(pdp) -> None:
    cascade, _ = _cascade_with(
        {"action": "hold", "premium_usd": 0.0, "retention_usd": 0.0,
         "confidence": 0.9, "rationale": "wait"},
        tier="T1",
    )
    builder = ConcordiaPersonaBuilder(
        prefab=ReinsurerTreatyPricer(cascade=cascade, pdp=pdp),
        llm_provider=_FreeTextProvider(),
    )
    decisions = builder({
        "event": {"name": "X"},
        "entities": [{"iri": "https://mimic.ai/banks/svb", "name": "SVB"}],
        "scope": {},
    })
    assert decisions[0].agent_did == "did:web:concordia.svb"


def test_empty_entities_returns_empty_list(pdp) -> None:
    cascade, _ = _cascade_with(
        {"action": "hold", "premium_usd": 0.0, "retention_usd": 0.0,
         "confidence": 0.9, "rationale": "n/a"},
        tier="T1",
    )
    builder = ConcordiaPersonaBuilder(
        prefab=ReinsurerTreatyPricer(cascade=cascade, pdp=pdp),
        llm_provider=_FreeTextProvider(),
    )
    assert builder({"event": {}, "entities": [], "scope": {}}) == []


# ── failure propagation ────────────────────────────────────────────────────


def test_prefab_run_error_propagates(pdp) -> None:
    """Per contract, the builder returns ``list[Decision]`` — it must not
    swallow failures. A malformed model output should propagate so the
    scenario surfaces the failure instead of producing a partial run."""
    cascade, _ = _cascade_with(
        {"action": "bogus", "premium_usd": 0.0, "retention_usd": 0.0,
         "confidence": 0.5, "rationale": "garbage"},
        tier="T1",
    )
    builder = ConcordiaPersonaBuilder(
        prefab=ReinsurerTreatyPricer(cascade=cascade, pdp=pdp),
        llm_provider=_FreeTextProvider(),
    )
    with pytest.raises(PrefabRunError):
        builder({
            "event": {"name": "X"}, "scope": {},
            "entities": [{"iri": "https://e.x/e", "name": "E"}],
        })


# ── LM adapter ──────────────────────────────────────────────────────────────


def test_sample_text_extracts_text_key() -> None:
    provider = _FreeTextProvider(text="raise more capital")
    lm = MimicProviderAsConcordiaLM(provider)
    assert lm.sample_text("test prompt") == "raise more capital"


def test_sample_text_uses_default_system_prompt() -> None:
    """The pinned system prompt is part of model_fingerprint per Plan §4.2.
    If this string drifts, every cassette goes stale — that is intentional,
    and this test is the gate that surfaces an accidental drift."""
    provider = _FreeTextProvider()
    lm = MimicProviderAsConcordiaLM(provider)
    lm.sample_text("test prompt")
    assert provider.calls[-1]["system_prompt"] == DEFAULT_SYSTEM_PROMPT


def test_sample_text_fallback_when_no_text_key() -> None:
    class _WeirdProvider(_FreeTextProvider):
        def complete(self, *, messages, schema, tools, temperature, seed, system_prompt=""):
            self.calls.append({"messages": messages, "schema": schema, "system_prompt": system_prompt})
            return StructuredResponse(
                content={"unexpected": "shape"},
                input_tokens=1, output_tokens=1, cost_usd=0.0, confidence=0.5,
                model_fingerprint="x" * 64,
            )
    lm = MimicProviderAsConcordiaLM(_WeirdProvider())
    out = lm.sample_text("test")
    # Stable JSON fallback — sorted keys make this assertable.
    assert out == '{"unexpected": "shape"}'


def test_sample_choice_returns_index_and_response() -> None:
    provider = _FreeTextProvider()
    lm = MimicProviderAsConcordiaLM(provider)
    idx, resp, info = lm.sample_choice("which?", ["alpha", "beta", "gamma"])
    assert idx == 0
    assert resp == "alpha"
    assert "model_fingerprint" in info
    assert "confidence" in info


def test_sample_choice_rejects_empty_responses() -> None:
    lm = MimicProviderAsConcordiaLM(_FreeTextProvider())
    with pytest.raises(ValueError, match="non-empty"):
        lm.sample_choice("which?", [])


# ── embedder ───────────────────────────────────────────────────────────────


def test_embedder_is_deterministic_across_calls() -> None:
    e = SHA256UnitEmbedder()
    v1 = e("hello world")
    v2 = e("hello world")
    import numpy as np
    np.testing.assert_array_equal(v1, v2)


def test_embedder_distinguishes_different_text() -> None:
    e = SHA256UnitEmbedder()
    v1 = e("hello world")
    v2 = e("hello world!")
    import numpy as np
    assert not np.array_equal(v1, v2)


def test_embedder_returns_unit_vector() -> None:
    import numpy as np
    e = SHA256UnitEmbedder()
    v = e("anything")
    assert v.shape == (e.dim,)
    assert np.linalg.norm(v) == pytest.approx(1.0, rel=1e-9)


# ── ScenarioRunner integration: the audit-grade refusal contract ───────────


_SVB = Path(__file__).resolve().parents[4] / "scenarios" / "svb-replay-2023"


def _svb_spec():
    from mimic.framework.scenario import load_spec
    return load_spec(_SVB / "scenario.yaml")


def _svb_toy_network() -> dict:
    """Mirrors tests/scenario/test_audit_grade_refusal.py::_toy_network()."""
    return {
        "schema": "mimic.world.liability/v1",
        "entities": [
            {"iri": "https://example.com/svb", "name": "SVB",
             "equity": 16e9, "total_assets": 209e9},
            {"iri": "https://example.com/fhlb", "name": "FHLB",
             "equity": 50e9, "total_assets": 1e12},
        ],
        "exposures": [{"debtor_iri": "https://example.com/svb",
                       "creditor_iri": "https://example.com/fhlb",
                       "amount": 14e9}],
    }


def test_scenario_runner_refuses_concordia_outside_frozen_run(pdp, monkeypatch) -> None:
    """ADR 2026-05-21-audit-grade-refusal: with a non-deterministic builder and
    no frozen-run mode, the default audit-grade run must refuse. This is the
    forcing function — without it, a reinsurer running ``ScenarioRunner`` could
    get a hash they can't reproduce, and that breaks Plan §0.

    The existing ``tests/scenario/test_audit_grade_refusal.py`` proves the
    contract for a hand-rolled non-deterministic builder. This test pins it
    for the *real* ``ConcordiaPersonaBuilder`` so the contract can't drift
    if the builder ever forgets ``is_deterministic = False``."""
    from mimic.framework.scenario import FrozenRunRequired, ScenarioRunner

    monkeypatch.delenv("MIMIC_FROZEN_RUN", raising=False)
    cascade, _ = _cascade_with(
        {"action": "hold", "premium_usd": 0.0, "retention_usd": 0.0,
         "confidence": 0.5, "rationale": "n/a"},
        tier="T1",
    )
    builder = ConcordiaPersonaBuilder(
        prefab=ReinsurerTreatyPricer(cascade=cascade, pdp=pdp),
        llm_provider=_FreeTextProvider(),
    )
    runner = ScenarioRunner(pdp=pdp, persona_builder=builder)  # audit_grade=True default
    with pytest.raises(FrozenRunRequired, match="MIMIC_FROZEN_RUN"):
        runner.run(_svb_spec(), liability_network=_svb_toy_network())


def test_scenario_runner_runs_under_audit_grade_false(pdp, monkeypatch) -> None:
    """When the operator explicitly opts out of audit-grade, the run proceeds
    and the manifest carries None for both world_state_hash fields — no hash
    without earning it."""
    from mimic.framework.scenario import ScenarioRunner

    monkeypatch.delenv("MIMIC_FROZEN_RUN", raising=False)
    cascade, _ = _cascade_with(
        {"action": "reinsure", "premium_usd": 1_000.0, "retention_usd": 100.0,
         "confidence": 0.9, "rationale": "fine"},
        tier="T1",
    )
    builder = ConcordiaPersonaBuilder(
        prefab=ReinsurerTreatyPricer(cascade=cascade, pdp=pdp),
        llm_provider=_FreeTextProvider(),
    )
    runner = ScenarioRunner(pdp=pdp, persona_builder=builder, audit_grade=False)
    manifest = runner.run(_svb_spec(), liability_network=_svb_toy_network())
    assert manifest.audit_grade is False
    assert manifest.world_state_hash_initial is None
    assert manifest.world_state_hash_final is None
    assert manifest.decisions
    assert manifest.policy_version == pdp.policy_version
