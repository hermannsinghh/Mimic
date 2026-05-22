class LiquidityDecision {
  action "raise_capital" | "hold"
  facility_size_usd float
  rate_change_bp float
  confidence float @check(it >= 0 && it <= 1)
  rationale string
}
