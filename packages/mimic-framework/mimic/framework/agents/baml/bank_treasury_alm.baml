class TreasuryDecision {
  action "hedge" | "raise_capital" | "cut_exposure" | "hold"
  quantity_usd float
  confidence float @check(it >= 0 && it <= 1)
  rationale string
}
