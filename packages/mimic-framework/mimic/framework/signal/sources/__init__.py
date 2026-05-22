"""Data source connectors — Plan §4.1.

Each connector lives in a subdirectory and exposes the Connector interface
from `_base.py`. Tests use VCR-style fixtures; no live calls in CI.

Tier 0 (MVP): sec_edgar, fred
Tier 1 (month 1-3): am_best, lseg, bloomberg, noaa, ais, news_gdelt, opensanctions
Tier 2 (month 3-6): lloyds_rds, naic_serff, acord_feeds
"""
from ._base import Connector, HealthResult, RateLimitPolicy  # noqa: F401

__all__ = ["Connector", "HealthResult", "RateLimitPolicy"]
