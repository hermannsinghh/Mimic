"""SEC EDGAR connector — Plan §4.1 Tier 0.

10-K, 10-Q, 8-K, proxy filings. No auth required; UA-rate-limited at the SEC
side, so we self-throttle to 10 req/sec per the SEC fair-access policy.

Records are emitted as canonical Entity / Event dicts ready for the
fibo_to_internal / iso20022_to_internal translators.
"""
from .client import SECEdgarConnector  # noqa: F401

__all__ = ["SECEdgarConnector"]
