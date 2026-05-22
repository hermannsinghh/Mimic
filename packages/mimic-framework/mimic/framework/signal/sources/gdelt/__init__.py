"""GDELT connector — Plan §4.1 Tier 1.

Global news event database. Free; rate-limited at the GDELT side. Feeds the
signal retriever (F-10) with candidate event mentions.
"""
from .client import GDELTConnector  # noqa: F401

__all__ = ["GDELTConnector"]
