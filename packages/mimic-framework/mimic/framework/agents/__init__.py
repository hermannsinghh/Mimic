"""Agent reasoning layer.

Vendors a fork of Google DeepMind Concordia v2.0 (see mimic-concordia/)
and wraps it with LangGraph reasoning graphs. Domain prefabs live in
agents/prefabs/, BAML schemas in agents/baml/.

Prefabs (Plan §9.2):
    ReinsurerTreatyPricer, BankTreasuryALM, HedgeFundRiskOfficer,
    CentralBankLiquidityProvider, RatingAgencyAnalyst, BrokerCedentAdvisor.
"""
