"""Agent reasoning layer.

Wraps DeepMind Concordia v2.0 (via ``mimic-concordia``; see ADR
``decision-record/2026-05-22-concordia-vendoring-strategy.md``) and the
Mimic ``Prefab`` cascade into the ``PersonaBuilder`` contract demanded by
``ScenarioRunner`` (ADR ``decision-record/2026-05-21-audit-grade-refusal.md``).

Submodules:
    prefabs/             — Mimic domain prefabs (Plan §9.2)
    concordia_runtime/   — F-12 glue: Concordia agent → Prefab → Decision.
                           Import requires the optional ``concordia`` extra
                           (``pip install mimic-framework[concordia]``).
    baml/                — BAML schemas for prefab output validation.
    telemetry.py         — ``mimic.decision`` OTEL span helpers.

Prefabs (Plan §9.2):
    ReinsurerTreatyPricer, BankTreasuryALM, HedgeFundRiskOfficer,
    CentralBankLiquidityProvider, RatingAgencyAnalyst, BrokerCedentAdvisor.
"""
