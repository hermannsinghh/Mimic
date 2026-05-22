"""Prefab interface tests — Plan §9.2.

Live LLM calls are forbidden in CI. We use a stub provider plus a real PDP
loaded from policy/opa/ to exercise the full prefab contract: routing → policy
→ Decision emission.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mimic.framework.agents.prefabs import (
    BankTreasuryALM,
    BrokerCedentAdvisor,
    CentralBankLiquidityProvider,
    HedgeFundRiskOfficer,
    PrefabRunError,
    RatingAgencyAnalyst,
    ReinsurerTreatyPricer,
)
from mimic.framework.policy import PolicyDecisionPoint, load_bundle
from mimic.framework.routing import (
    RoutingCascade,
    StructuredResponse,
    compute_model_fingerprint,
)
from mimic.framework.schema.decision import Decision

_BUNDLE = Path(__file__).resolve().parents[2] / "policy" / "opa"


class _FakeProvider:
    def __init__(self, name, content):
        self.provider_name = name
        self.model_name = name
        self.model_version = "2026-01"
        self._content = content
        self.calls = 0

    def estimate_cost_usd(self, i, o):
        return 0.01

    def complete(self, *, messages, schema, tools, temperature, seed, system_prompt=""):
        self.calls += 1
        return StructuredResponse(
            content=self._content, input_tokens=10, output_tokens=5,
            cost_usd=0.01, confidence=float(self._content.get("confidence", 0.9)),
            model_fingerprint=compute_model_fingerprint(
                provider=self.provider_name, model=self.model_name,
                version=self.model_version, system_prompt=system_prompt,
                temperature=temperature, tool_schema=None,
            ),
        )


def _cascade_with(content, tier):
    p = _FakeProvider("fake", content)
    kwargs = {"t3": None, "t2_a": None, "t1": None, "max_cost_usd": 5.0}
    kwargs[{"T1": "t1", "T2": "t2_a", "T3": "t3"}[tier]] = p
    return RoutingCascade(**kwargs), p


@pytest.fixture
def pdp():
    return PolicyDecisionPoint(load_bundle(_BUNDLE))


# ── one happy-path test per prefab ──────────────────────────────────────────

def test_reinsurer_treaty_pricer_emits_reinsure(pdp):
    cascade, _ = _cascade_with(
        {"action": "reinsure", "premium_usd": 1_000_000.0,
         "retention_usd": 5_000_000.0, "confidence": 0.85, "rationale": "ok"},
        tier="T1",
    )
    prefab = ReinsurerTreatyPricer(cascade=cascade, pdp=pdp)
    entity = {"iri": "https://example.com/munich-re", "name": "MunichRe",
              "price": 1.0, "position_limit": 1e12}
    d = prefab.run(entity=entity, inputs={"treaty_summary": "x"}, agent_did="did:web:test")
    assert isinstance(d, Decision)
    assert d.action_type == "reinsure"
    assert d.policy_version == pdp.policy_version


def test_bank_treasury_alm_emits_hedge(pdp):
    cascade, _ = _cascade_with(
        {"action": "hedge", "quantity_usd": 500_000.0, "confidence": 0.8, "rationale": "rate risk"},
        tier="T1",
    )
    prefab = BankTreasuryALM(cascade=cascade, pdp=pdp)
    entity = {"iri": "https://example.com/svb", "name": "SVB",
              "price": 1.0, "position_limit": 1e12}
    d = prefab.run(entity=entity, inputs={"lcr": 100, "nsfr": 110}, agent_did="did:web:svb")
    assert d.action_type == "hedge"


def test_hedge_fund_risk_officer_emits_sell(pdp):
    cascade, _ = _cascade_with(
        {"action": "sell", "notional_usd": 250_000.0, "confidence": 0.7, "rationale": "x"},
        tier="T2",
    )
    prefab = HedgeFundRiskOfficer(cascade=cascade, pdp=pdp)
    entity = {"iri": "https://example.com/cit", "name": "Citadel",
              "price": 1.0, "position_limit": 1e12}
    d = prefab.run(entity=entity, inputs={"gross_leverage": 4.5}, agent_did="did:web:cit")
    assert d.action_type == "sell"


def test_central_bank_emits_facility(pdp):
    cascade, _ = _cascade_with(
        {"action": "raise_capital", "facility_size_usd": 50_000_000_000.0,
         "rate_change_bp": 0.0, "confidence": 0.92,
         "rationale": "treasury market dysfunction"},
        tier="T1",
    )
    prefab = CentralBankLiquidityProvider(cascade=cascade, pdp=pdp)
    entity = {"iri": "https://example.com/frb", "name": "FRB",
              "price": 1.0, "position_limit": 1e15}
    d = prefab.run(entity=entity, inputs={"fra_ois_bp": 80}, agent_did="did:web:frb")
    assert d.action_type == "raise_capital"


def test_rating_agency_analyst_emits_cut(pdp):
    cascade, _ = _cascade_with(
        {"action": "cut_exposure", "notches": 1, "confidence": 0.78,
         "rationale": "ICR breached"},
        tier="T2",
    )
    prefab = RatingAgencyAnalyst(cascade=cascade, pdp=pdp)
    entity = {"iri": "https://example.com/svb", "name": "SVB",
              "price": 1.0, "position_limit": 1e12}
    d = prefab.run(entity=entity, inputs={"current_rating": "A-"}, agent_did="did:web:moodys")
    assert d.action_type == "cut_exposure"


def test_broker_cedent_advisor_emits_cede(pdp):
    cascade, _ = _cascade_with(
        {"action": "cede", "cession_pct": 40.0, "premium_target_usd": 12_000_000.0,
         "confidence": 0.81, "rationale": "soft market window"},
        tier="T2",
    )
    prefab = BrokerCedentAdvisor(cascade=cascade, pdp=pdp)
    entity = {"iri": "https://example.com/cedent", "name": "Acme Insure",
              "price": 1.0, "position_limit": 1e12}
    d = prefab.run(entity=entity, inputs={"gpv_usd": 200_000_000}, agent_did="did:web:aon")
    assert d.action_type == "cede"


# ── contract tests ──────────────────────────────────────────────────────────

def test_unexpected_action_raises_prefab_run_error(pdp):
    cascade, _ = _cascade_with({"action": "teleport"}, tier="T1")
    prefab = ReinsurerTreatyPricer(cascade=cascade, pdp=pdp)
    with pytest.raises(PrefabRunError, match="unexpected action"):
        prefab.run(entity={"iri": "x", "name": "x"}, inputs={}, agent_did="did:web:x")


def test_policy_block_surfaces_as_prefab_run_error(pdp):
    cascade, _ = _cascade_with(
        {"action": "buy", "quantity_usd": 1e12, "confidence": 0.9, "rationale": "x"},
        tier="T1",
    )
    # BankTreasuryALM doesn't support "buy" — will fail earlier. Use a permissive
    # action that violates the position_limit instead.
    cascade2, _ = _cascade_with(
        {"action": "hedge", "quantity_usd": -1, "confidence": 0.9, "rationale": "x"},
        tier="T1",
    )
    prefab = BankTreasuryALM(cascade=cascade2, pdp=pdp)
    entity = {"iri": "https://example.com/x", "name": "x",
              "price": 1.0, "position_limit": 100.0}
    with pytest.raises(PrefabRunError, match="policy"):
        prefab.run(entity=entity, inputs={}, agent_did="did:web:x")


def test_every_prefab_records_policy_version(pdp):
    cascade, _ = _cascade_with(
        {"action": "hold", "quantity_usd": 0.0, "confidence": 0.9, "rationale": "wait"},
        tier="T1",
    )
    prefab = BankTreasuryALM(cascade=cascade, pdp=pdp)
    entity = {"iri": "x:e", "name": "e", "price": 1.0, "position_limit": 1.0}
    d = prefab.run(entity=entity, inputs={}, agent_did="did:web:x")
    assert d.policy_version == pdp.policy_version
    assert len(d.policy_version) == 64  # sha256 hex
