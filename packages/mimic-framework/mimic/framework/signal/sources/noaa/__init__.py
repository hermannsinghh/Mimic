"""NOAA connector — Plan §4.1 Tier 1.

Weather + cat-risk parametric scenarios. Free, no API key required.
"""
from .client import NOAAConnector  # noqa: F401

__all__ = ["NOAAConnector"]
