"""Two-stage signal pipeline — Plan §3.1 F-10.

    raw events ── Retriever ─→ candidates ── Reranker ─→ top-k ── Adjudicator ─→ Signal

Retriever:   cheap, recall-focused; pulls candidate records from connector sources.
Reranker:    precision-focused; an LLM (typically T2) scores candidates against the
             scenario's evidence schema.
Adjudicator: final yes/no with rationale; a T1 LLM that emits a structured Signal.

Reranker and Adjudicator share the routing.LLMProvider interface (F-06) — that's
where cost, fingerprint, and frozen-run semantics come from.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from ..routing.provider import LLMProvider


@dataclass(frozen=True)
class CandidateEvent:
    """Raw event surfaced by a Retriever."""
    source: str
    event_iri: str
    snippet: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RerankedCandidate:
    candidate: CandidateEvent
    rerank_score: float
    rerank_rationale: str


@dataclass(frozen=True)
class AdjudicatedSignal:
    """Final structured output emitted by the Adjudicator."""
    event_iri: str
    affirmed: bool
    confidence: float
    rationale: str
    supporting_candidates: tuple[RerankedCandidate, ...]
    cost_usd: float


class Retriever(ABC):
    """Stage 1: pull candidate records from one or more connectors."""

    @abstractmethod
    def retrieve(self, query: str, *, max_candidates: int = 50) -> list[CandidateEvent]: ...


class Reranker(ABC):
    """Stage 2a: re-score candidates with an LLM."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: Sequence[CandidateEvent],
        *,
        top_k: int = 10,
    ) -> list[RerankedCandidate]: ...


class Adjudicator(ABC):
    """Stage 2b: emit a final structured Signal."""

    @abstractmethod
    def adjudicate(
        self,
        query: str,
        top_k: Sequence[RerankedCandidate],
    ) -> AdjudicatedSignal: ...


# ── default LLM-backed implementations ──────────────────────────────────────

class LLMReranker(Reranker):
    """Reranker backed by an LLMProvider (typically a T2 model)."""

    def __init__(self, provider: LLMProvider, *, system_prompt: str = "") -> None:
        self.provider = provider
        self.system_prompt = system_prompt or (
            "Re-score each candidate's relevance to the query on a 0-1 scale. "
            "Return strict JSON: {scores: [{candidate_index, score, rationale}]}."
        )

    def rerank(
        self,
        query: str,
        candidates: Sequence[CandidateEvent],
        *,
        top_k: int = 10,
    ) -> list[RerankedCandidate]:
        if not candidates:
            return []
        messages = [
            {"role": "user", "content": _format_rerank_prompt(query, candidates)},
        ]
        resp = self.provider.complete(
            messages=messages,
            schema=None,
            tools=None,
            temperature=0.0,
            seed=None,
            system_prompt=self.system_prompt,
        )
        # tolerate the LLM returning either {scores: [...]} or a list directly
        raw_scores = resp.content.get("scores", resp.content) if isinstance(resp.content, dict) else resp.content
        if not isinstance(raw_scores, list):
            raise ValueError(f"reranker provider returned non-list scores: {resp.content!r}")
        reranked: list[RerankedCandidate] = []
        for entry in raw_scores:
            idx = entry["candidate_index"]
            if not 0 <= idx < len(candidates):
                continue
            reranked.append(RerankedCandidate(
                candidate=candidates[idx],
                rerank_score=float(entry["score"]),
                rerank_rationale=entry.get("rationale", ""),
            ))
        reranked.sort(key=lambda r: r.rerank_score, reverse=True)
        return reranked[:top_k]


class LLMAdjudicator(Adjudicator):
    """Adjudicator backed by an LLMProvider (typically a T1 model)."""

    def __init__(self, provider: LLMProvider, *, system_prompt: str = "") -> None:
        self.provider = provider
        self.system_prompt = system_prompt or (
            "Given the query and top-k reranked candidates, return strict JSON: "
            "{event_iri, affirmed: bool, confidence: float, rationale: str}."
        )

    def adjudicate(
        self,
        query: str,
        top_k: Sequence[RerankedCandidate],
    ) -> AdjudicatedSignal:
        messages = [
            {"role": "user", "content": _format_adjudicate_prompt(query, top_k)},
        ]
        resp = self.provider.complete(
            messages=messages, schema=None, tools=None,
            temperature=0.0, seed=None, system_prompt=self.system_prompt,
        )
        c = resp.content
        return AdjudicatedSignal(
            event_iri=c["event_iri"],
            affirmed=bool(c["affirmed"]),
            confidence=float(c.get("confidence", resp.confidence)),
            rationale=c.get("rationale", ""),
            supporting_candidates=tuple(top_k),
            cost_usd=resp.cost_usd,
        )


@dataclass(frozen=True)
class PipelineResult:
    candidates: tuple[CandidateEvent, ...]
    reranked: tuple[RerankedCandidate, ...]
    signal: AdjudicatedSignal


class SignalPipeline:
    """Compose a Retriever + Reranker + Adjudicator into one call."""

    def __init__(
        self,
        retriever: Retriever,
        reranker: Reranker,
        adjudicator: Adjudicator,
        *,
        max_candidates: int = 50,
        top_k: int = 10,
    ) -> None:
        self.retriever = retriever
        self.reranker = reranker
        self.adjudicator = adjudicator
        self.max_candidates = max_candidates
        self.top_k = top_k

    def run(self, query: str) -> PipelineResult:
        candidates = self.retriever.retrieve(query, max_candidates=self.max_candidates)
        reranked = self.reranker.rerank(query, candidates, top_k=self.top_k)
        signal = self.adjudicator.adjudicate(query, reranked)
        return PipelineResult(
            candidates=tuple(candidates),
            reranked=tuple(reranked),
            signal=signal,
        )


def _format_rerank_prompt(query: str, candidates: Sequence[CandidateEvent]) -> str:
    lines = [f"Query: {query}", "Candidates:"]
    for i, c in enumerate(candidates):
        lines.append(f"[{i}] ({c.source}) {c.event_iri}: {c.snippet}")
    return "\n".join(lines)


def _format_adjudicate_prompt(query: str, top_k: Sequence[RerankedCandidate]) -> str:
    lines = [f"Query: {query}", "Top reranked candidates:"]
    for i, r in enumerate(top_k):
        lines.append(
            f"[{i}] score={r.rerank_score:.3f} {r.candidate.event_iri}: {r.candidate.snippet}"
        )
    return "\n".join(lines)
