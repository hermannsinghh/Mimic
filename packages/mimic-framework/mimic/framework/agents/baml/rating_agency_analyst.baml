class RatingDecision {
  action "cut_exposure" | "hold"
  notches int
  confidence float @check(it >= 0 && it <= 1)
  rationale string
}
