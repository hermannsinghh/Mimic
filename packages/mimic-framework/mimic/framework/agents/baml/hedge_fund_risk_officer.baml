class RiskOfficerDecision {
  action "hedge" | "sell" | "hold"
  notional_usd float
  confidence float @check(it >= 0 && it <= 1)
  rationale string
}
