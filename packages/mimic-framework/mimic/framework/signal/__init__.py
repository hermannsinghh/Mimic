"""Event extraction pipeline: retriever -> reranker -> adjudicator.

Plan §3.1 F-10. The pipeline interfaces live in `pipeline.py`; legacy
`mimic_signal` package is re-exported here for backwards compatibility
during the 0.2.x transition.
"""
from .pipeline import (  # noqa: F401
    AdjudicatedSignal,
    Adjudicator,
    CandidateEvent,
    LLMAdjudicator,
    LLMReranker,
    PipelineResult,
    RerankedCandidate,
    Reranker,
    Retriever,
    SignalPipeline,
)

try:  # legacy compatibility
    from mimic_signal import *  # noqa: F401,F403
    from mimic_signal import __all__ as _legacy_all  # type: ignore[attr-defined]
    _legacy_exports = list(_legacy_all)
except ImportError:
    _legacy_exports: list[str] = []

__all__ = [
    "CandidateEvent",
    "RerankedCandidate",
    "AdjudicatedSignal",
    "Retriever",
    "Reranker",
    "Adjudicator",
    "LLMReranker",
    "LLMAdjudicator",
    "SignalPipeline",
    "PipelineResult",
] + _legacy_exports
