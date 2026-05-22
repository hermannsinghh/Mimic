"""Routing cascade — Plan §6.2.

T3 → T2 → T1 escalation with confidence threshold and budget guardrail.

    T3 response → confidence < 0.6           → escalate to T2
    T2 response → two-model cos < 0.7        → adjudicate with T1
    T1 response is final

Every call emits an OTEL span `mimic.route` with tier, provider, model, tokens,
cost, confidence, escalated_to (Plan §6.3) — wiring lives in `telemetry.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .provider import BudgetExceeded, LLMProvider, StructuredResponse
from .telemetry import build_attrs, route_span

Tier = Literal["T1", "T2", "T3"]

DEFAULT_T3_ESCALATE_BELOW = 0.6
DEFAULT_T2_AGREEMENT_BELOW = 0.7


@dataclass(frozen=True)
class RouteResult:
    response: StructuredResponse
    final_tier: Tier
    tiers_attempted: tuple[Tier, ...]
    total_cost_usd: float
    escalated: bool


class RoutingCascade:
    """Holds one LLMProvider per tier (and an optional T1 adjudicator)."""

    def __init__(
        self,
        *,
        t3: LLMProvider | None,
        t2_a: LLMProvider | None,
        t2_b: LLMProvider | None = None,
        t1: LLMProvider | None,
        max_cost_usd: float,
        t3_escalate_below: float = DEFAULT_T3_ESCALATE_BELOW,
        t2_agreement_below: float = DEFAULT_T2_AGREEMENT_BELOW,
    ) -> None:
        if max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be positive")
        self.t3 = t3
        self.t2_a = t2_a
        self.t2_b = t2_b
        self.t1 = t1
        self.max_cost_usd = max_cost_usd
        self.t3_escalate_below = t3_escalate_below
        self.t2_agreement_below = t2_agreement_below

    def _spend(self, spent: float, provider: LLMProvider, est_in: int, est_out: int) -> float:
        next_call_cost = provider.estimate_cost_usd(est_in, est_out)
        if spent + next_call_cost > self.max_cost_usd:
            raise BudgetExceeded(
                f"would exceed max_cost_usd={self.max_cost_usd}: "
                f"spent={spent:.4f}, next_call_est={next_call_cost:.4f}"
            )
        return next_call_cost

    def route(
        self,
        *,
        entry_tier: Tier,
        messages: list[dict],
        schema: dict | None = None,
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        system_prompt: str = "",
        estimated_input_tokens: int = 1000,
        estimated_output_tokens: int = 500,
    ) -> RouteResult:
        attempted: list[Tier] = []
        spent = 0.0
        per_call_spans: list[dict] = []  # captured for OTEL span attrs

        def _call(provider: LLMProvider | None, tier: Tier) -> StructuredResponse:
            nonlocal spent
            if provider is None:
                raise RuntimeError(f"no provider configured for tier {tier}")
            self._spend(spent, provider, estimated_input_tokens, estimated_output_tokens)
            resp = provider.complete(
                messages=messages,
                schema=schema,
                tools=tools,
                temperature=temperature,
                seed=seed,
                system_prompt=system_prompt,
            )
            spent += resp.cost_usd
            attempted.append(tier)
            per_call_spans.append({
                "tier": tier,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "cost_usd": resp.cost_usd,
                "confidence": resp.confidence,
            })
            return resp

        with route_span({"entry_tier": entry_tier}) as span:
            try:
                result = self._route_inner(entry_tier, attempted, spent, per_call_spans, _call)
            except BaseException:
                span.set_attribute("attempted_tiers", ",".join(attempted))
                raise
            # final span attrs reflect the *winning* call
            final = per_call_spans[-1] if per_call_spans else {}
            span.set_attributes(build_attrs(
                tier=result.final_tier,
                provider=final.get("provider", ""),
                model=final.get("model", ""),
                input_tokens=final.get("input_tokens", 0),
                output_tokens=final.get("output_tokens", 0),
                cost_usd=result.total_cost_usd,
                confidence=result.response.confidence,
                escalated_to=result.final_tier if result.escalated else None,
            ))
            span.set_attribute("attempted_tiers", ",".join(attempted))
        return result

    def _route_inner(
        self,
        entry_tier: Tier,
        attempted: list[Tier],
        spent: float,
        per_call_spans: list[dict],
        _call,
    ) -> "RouteResult":
        if entry_tier == "T3":
            resp = _call(self.t3, "T3")
            if resp.confidence >= self.t3_escalate_below:
                return RouteResult(resp, "T3", tuple(attempted), per_call_spans[-1]["cost_usd"] if per_call_spans else 0.0, escalated=False)
            entry_tier = "T2"

        spent_so_far = sum(s["cost_usd"] for s in per_call_spans)
        if entry_tier == "T2":
            resp_a = _call(self.t2_a, "T2")
            if self.t2_b is None:
                return RouteResult(
                    resp_a, "T2", tuple(attempted), sum(s["cost_usd"] for s in per_call_spans),
                    escalated=("T3" in attempted),
                )
            resp_b = _call(self.t2_b, "T2")
            agreement = _decision_cosine(resp_a, resp_b)
            if agreement >= self.t2_agreement_below:
                winner = resp_a if resp_a.confidence >= resp_b.confidence else resp_b
                return RouteResult(
                    winner, "T2", tuple(attempted), sum(s["cost_usd"] for s in per_call_spans),
                    escalated=("T3" in attempted),
                )
            # disagreement -> adjudicate
            entry_tier = "T1"

        resp_t1 = _call(self.t1, "T1")
        return RouteResult(
            resp_t1, "T1", tuple(attempted), sum(s["cost_usd"] for s in per_call_spans),
            escalated=(len(attempted) > 1),
        )


def _decision_cosine(a: StructuredResponse, b: StructuredResponse) -> float:
    """Crude agreement score: 1.0 if top-level keys equal & values match on primitives."""
    if not a.content or not b.content:
        return 0.0
    keys = set(a.content.keys()) | set(b.content.keys())
    if not keys:
        return 1.0
    matches = sum(1 for k in keys if a.content.get(k) == b.content.get(k))
    return matches / len(keys)
