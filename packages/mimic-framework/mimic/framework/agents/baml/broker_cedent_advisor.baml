class CedentAdvisoryDecision {
  action "cede" | "retain"
  cession_pct float
  premium_target_usd float
  confidence float @check(it >= 0 && it <= 1)
  rationale string
}
