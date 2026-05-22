"""Model registry and auto-selection logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mimic_forecast.base import ForecasterAdapter

logger = logging.getLogger(__name__)

# Series metadata: which model is best for each named series
SERIES_REGISTRY: dict[str, dict] = {
    "shipping_rates": {
        "source": "quandl",
        "ticker": "CHRIS/CME_BDI",
        "best_model": "timesfm",
        "event_types": ["supply_chain", "geopolitical"],
    },
    "oil_price": {
        "source": "fred",
        "ticker": "DCOILWTICO",
        "best_model": "kronos",
        "event_types": ["energy", "macro", "geopolitical"],
    },
    "natural_gas_price": {
        "source": "fred",
        "ticker": "DHHNGSP",
        "best_model": "timesfm",
        "event_types": ["energy"],
    },
    "fed_funds_rate": {
        "source": "fred",
        "ticker": "FEDFUNDS",
        "best_model": "bistro",
        "event_types": ["macro"],
    },
    "cpi": {
        "source": "fred",
        "ticker": "CPIAUCSL",
        "best_model": "bistro",
        "event_types": ["macro"],
    },
    "gdp": {
        "source": "fred",
        "ticker": "GDP",
        "best_model": "bistro",
        "event_types": ["macro"],
    },
    "unemployment": {
        "source": "fred",
        "ticker": "UNRATE",
        "best_model": "bistro",
        "event_types": ["macro"],
    },
    "usd_cny": {
        "source": "fred",
        "ticker": "DEXCHUS",
        "best_model": "chronos",
        "event_types": ["geopolitical", "supply_chain"],
    },
    "usd_eur": {
        "source": "fred",
        "ticker": "DEXUSEU",
        "best_model": "chronos",
        "event_types": ["macro", "geopolitical"],
    },
    "sp500": {
        "source": "yfinance",
        "ticker": "^GSPC",
        "best_model": "kronos",
        "event_types": ["macro", "geopolitical"],
    },
    "vix": {
        "source": "yfinance",
        "ticker": "^VIX",
        "best_model": "timesfm",
        "event_types": ["macro", "geopolitical", "energy"],
    },
    "credit_spreads": {
        "source": "fred",
        "ticker": "BAMLH0A0HYM2",
        "best_model": "bistro",
        "event_types": ["macro"],
    },
    "retail_sales": {
        "source": "fred",
        "ticker": "RSXFS",
        "best_model": "timesfm",
        "event_types": ["supply_chain", "macro"],
    },
    "industrial_production": {
        "source": "fred",
        "ticker": "INDPRO",
        "best_model": "bistro",
        "event_types": ["macro", "supply_chain"],
    },
    "copper_price": {
        "source": "fred",
        "ticker": "PCOPPUSDM",
        "best_model": "timesfm",
        "event_types": ["supply_chain", "geopolitical"],
    },
    "consumer_confidence": {
        "source": "fred",
        "ticker": "UMCSENT",
        "best_model": "bistro",
        "event_types": ["macro"],
    },
}

# Event → list of relevant series names
EVENT_SERIES_MAP: dict[str, list[str]] = {
    "supply_chain": ["shipping_rates", "copper_price", "retail_sales", "usd_cny"],
    "energy": ["oil_price", "natural_gas_price", "vix"],
    "macro": [
        "fed_funds_rate", "cpi", "gdp", "unemployment",
        "credit_spreads", "consumer_confidence", "sp500",
    ],
    "geopolitical": ["oil_price", "shipping_rates", "usd_cny", "usd_eur", "vix", "sp500"],
}

# Model name → lazy-importable class path
_MODEL_CLASSES: dict[str, str] = {
    "timesfm": "mimic_forecast.adapters.timesfm.TimesFMAdapter",
    "chronos": "mimic_forecast.adapters.chronos.ChronosAdapter",
    "finbert": "mimic_forecast.adapters.finbert.FinBERT2Adapter",
    "kronos": "mimic_forecast.adapters.kronos.KronosAdapter",
    "moirai": "mimic_forecast.adapters.moirai.MoiraiAdapter",
    "bistro": "mimic_forecast.adapters.bistro.BISTROAdapter",
}

# Cached adapter instances
_adapter_cache: dict[str, "ForecasterAdapter"] = {}


def get_adapter(model_name: str) -> "ForecasterAdapter":
    """Return a cached adapter instance by model name."""
    if model_name in _adapter_cache:
        return _adapter_cache[model_name]

    class_path = _MODEL_CLASSES.get(model_name)
    if not class_path:
        raise ValueError(
            f"Unknown model '{model_name}'. Available: {list(_MODEL_CLASSES)}"
        )

    module_path, class_name = class_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    adapter_cls = getattr(module, class_name)
    adapter = adapter_cls()
    _adapter_cache[model_name] = adapter
    return adapter


def best_model_for(series_name: str) -> "ForecasterAdapter":
    """Return the best adapter for a named series."""
    spec = SERIES_REGISTRY.get(series_name)
    if spec is None:
        logger.warning("Series '%s' not in registry, defaulting to TimesFM.", series_name)
        return get_adapter("timesfm")
    return get_adapter(spec["best_model"])


def series_for_event(event_type: str) -> list[str]:
    """Return the list of series names relevant to an event type."""
    return EVENT_SERIES_MAP.get(event_type, [])


def detect_event_type(event_description: str) -> str:
    """Heuristic: classify a free-text event description into an event type."""
    import re

    text = event_description.lower()

    def _matches(keywords: list[str]) -> bool:
        return any(re.search(rf"\b{re.escape(w)}\b", text) for w in keywords)

    if _matches(["oil", "gas", "energy", "opec", "refinery", "fuel"]):
        return "energy"
    if _matches(["tariff", "sanction", "war", "geopolitical", "china", "russia"]):
        return "geopolitical"
    if _matches(["port", "ship", "supply", "inventory", "logistics", "freight", "container"]):
        return "supply_chain"
    if _matches(["fed", "rate", "inflation", "gdp", "recession", "cpi", "macro"]):
        return "macro"

    logger.warning("Could not classify event '%s', defaulting to macro.", event_description)
    return "macro"
