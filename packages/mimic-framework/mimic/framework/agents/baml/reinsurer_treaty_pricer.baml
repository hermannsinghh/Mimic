// ReinsurerTreatyPricer output schema — Plan §9.2.
class TreatyDecision {
  action "reinsure" | "hold"
  premium_usd float
  retention_usd float
  confidence float @check(it >= 0 && it <= 1)
  rationale string
}
