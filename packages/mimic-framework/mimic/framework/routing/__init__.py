"""RouteLLM-style tier cascade — Plan §6.

Tier criteria are deterministic; no LLM in the routing decision itself.
Every call emits OTEL span `mimic.route` with cost, tokens, confidence.
"""
from .anthropic import (  # noqa: F401
    AnthropicJSONParseError,
    AnthropicProvider,
)
from .cascade import RouteResult, RoutingCascade  # noqa: F401
from .deepseek import (  # noqa: F401
    DeepSeekJSONParseError,
    DeepSeekProvider,
)
from .provider import (  # noqa: F401
    BudgetExceeded,
    FrozenRunCacheMiss,
    LLMProvider,
    StructuredResponse,
    compute_model_fingerprint,
)
from .tiers import Tier, assign_tier  # noqa: F401

__all__ = [
    "Tier",
    "assign_tier",
    "LLMProvider",
    "StructuredResponse",
    "compute_model_fingerprint",
    "BudgetExceeded",
    "FrozenRunCacheMiss",
    "RoutingCascade",
    "RouteResult",
    "AnthropicProvider",
    "AnthropicJSONParseError",
    "DeepSeekProvider",
    "DeepSeekJSONParseError",
]
