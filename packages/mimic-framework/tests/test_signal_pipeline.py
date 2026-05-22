"""Tests for the two-stage signal pipeline — Plan §3.1 F-10."""
from __future__ import annotations

import pytest

from mimic.framework.routing import StructuredResponse, compute_model_fingerprint
from mimic.framework.signal import (
    AdjudicatedSignal,
    CandidateEvent,
    LLMAdjudicator,
    LLMReranker,
    Retriever,
    SignalPipeline,
)


class _StubRetriever(Retriever):
    def __init__(self, candidates):
        self._candidates = candidates

    def retrieve(self, query, *, max_candidates=50):
        return self._candidates[:max_candidates]


class _StubProvider:
    def __init__(self, response_content):
        self.provider_name = "stub"
        self.model_name = "stub-v1"
        self.model_version = "2026-01"
        self._content = response_content

    def estimate_cost_usd(self, i, o):
        return 0.01

    def complete(self, *, messages, schema, tools, temperature, seed, system_prompt=""):
        return StructuredResponse(
            content=self._content, input_tokens=10, output_tokens=5,
            cost_usd=0.01, confidence=0.92,
            model_fingerprint=compute_model_fingerprint(
                provider=self.provider_name, model=self.model_name,
                version=self.model_version, system_prompt=system_prompt,
                temperature=temperature, tool_schema=None,
            ),
        )


def _candidates():
    return [
        CandidateEvent(source="sec_edgar", event_iri="x:a", snippet="capital ratio fell to 4%", score=0.3),
        CandidateEvent(source="news", event_iri="x:b", snippet="bond losses materialise", score=0.5),
        CandidateEvent(source="news", event_iri="x:c", snippet="weather forecast", score=0.2),
    ]


def test_llm_reranker_orders_by_score_and_truncates():
    rerank_provider = _StubProvider({"scores": [
        {"candidate_index": 0, "score": 0.7, "rationale": "balance-sheet stress"},
        {"candidate_index": 1, "score": 0.9, "rationale": "direct evidence"},
        {"candidate_index": 2, "score": 0.05, "rationale": "irrelevant"},
    ]})
    rr = LLMReranker(rerank_provider)
    out = rr.rerank("bank run risk", _candidates(), top_k=2)
    assert len(out) == 2
    assert out[0].rerank_score == 0.9
    assert out[1].rerank_score == 0.7
    assert out[0].candidate.event_iri == "x:b"


def test_llm_reranker_ignores_out_of_range_indices():
    rerank_provider = _StubProvider({"scores": [
        {"candidate_index": 99, "score": 0.99, "rationale": "ghost"},
        {"candidate_index": 0, "score": 0.5, "rationale": "real"},
    ]})
    rr = LLMReranker(rerank_provider)
    out = rr.rerank("q", _candidates(), top_k=10)
    assert len(out) == 1
    assert out[0].rerank_score == 0.5


def test_llm_reranker_handles_empty_candidates():
    rr = LLMReranker(_StubProvider({"scores": []}))
    assert rr.rerank("q", []) == []


def test_llm_adjudicator_emits_structured_signal():
    adj_provider = _StubProvider({
        "event_iri": "https://mimic.ai/events/bank-run/svb-2023-03",
        "affirmed": True,
        "confidence": 0.94,
        "rationale": "deposit outflow exceeds capital cushion",
    })
    adj = LLMAdjudicator(adj_provider)
    from mimic.framework.signal import RerankedCandidate
    top = [
        RerankedCandidate(
            candidate=_candidates()[0], rerank_score=0.9, rerank_rationale="x",
        ),
    ]
    sig = adj.adjudicate("bank run", top)
    assert isinstance(sig, AdjudicatedSignal)
    assert sig.affirmed is True
    assert sig.confidence == 0.94
    assert sig.event_iri.endswith("svb-2023-03")


def test_signal_pipeline_end_to_end():
    rerank_provider = _StubProvider({"scores": [
        {"candidate_index": 1, "score": 0.95, "rationale": "direct"},
        {"candidate_index": 0, "score": 0.6, "rationale": "supporting"},
    ]})
    adj_provider = _StubProvider({
        "event_iri": "x:b", "affirmed": True, "confidence": 0.97,
        "rationale": "two corroborating sources",
    })
    pipeline = SignalPipeline(
        retriever=_StubRetriever(_candidates()),
        reranker=LLMReranker(rerank_provider),
        adjudicator=LLMAdjudicator(adj_provider),
        top_k=2,
    )
    result = pipeline.run("bank run risk")
    assert len(result.candidates) == 3
    assert len(result.reranked) == 2
    assert result.signal.affirmed is True
    assert result.signal.event_iri == "x:b"
    assert len(result.signal.supporting_candidates) == 2


def test_reranker_rejects_non_list_response():
    bad = _StubProvider({"scores": "not a list"})
    rr = LLMReranker(bad)
    with pytest.raises(ValueError, match="non-list"):
        rr.rerank("q", _candidates())
