"""FRED (St. Louis Fed) connector — Plan §4.1 Tier 0.

Macro time series. Requires a free API key (env: FRED_API_KEY).
Records are emitted as time-series observations bound to FRED series IDs.
"""
from .client import FREDConnector  # noqa: F401

__all__ = ["FREDConnector"]
