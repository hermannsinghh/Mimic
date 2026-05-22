"""Domain prefabs — Plan §9.2.

Each prefab is a Concordia-compatible agent with a LangGraph-style reasoning
graph, BAML-enforced output schema (in ../baml/), and a calibration test under
tests/agents/prefabs/.

A prefab without a published calibration badge MUST NOT ship to Mimic Hub.

Available prefabs:
    ReinsurerTreatyPricer        — T1 — treaty bid/no-bid + price + retention
    BankTreasuryALM              — T1 — liquidity actions
    HedgeFundRiskOfficer         — T2 — position trims / hedges
    CentralBankLiquidityProvider — T1 — facility opening, rate decision
    RatingAgencyAnalyst          — T2 — watch / downgrade / no-action
    BrokerCedentAdvisor          — T2 — recommended placement
"""
from ._base import Prefab, PrefabRunError  # noqa: F401
from .bank_treasury_alm import BankTreasuryALM  # noqa: F401
from .broker_cedent_advisor import BrokerCedentAdvisor  # noqa: F401
from .central_bank_liquidity_provider import CentralBankLiquidityProvider  # noqa: F401
from .hedge_fund_risk_officer import HedgeFundRiskOfficer  # noqa: F401
from .rating_agency_analyst import RatingAgencyAnalyst  # noqa: F401
from .reinsurer_treaty_pricer import ReinsurerTreatyPricer  # noqa: F401

__all__ = [
    "Prefab",
    "PrefabRunError",
    "ReinsurerTreatyPricer",
    "BankTreasuryALM",
    "HedgeFundRiskOfficer",
    "CentralBankLiquidityProvider",
    "RatingAgencyAnalyst",
    "BrokerCedentAdvisor",
]
