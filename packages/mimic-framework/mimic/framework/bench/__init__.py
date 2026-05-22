"""GIFT-Eval / Chronos-ZS / AgentDojo wrappers + historical-episode calibration.

Per Plan §1.1, mimic-bench is absorbed into mimic-framework. Re-exports
the legacy `mimic_bench` package during the 0.2.x transition.

TODO (F-11): consolidate harness implementations in this directory.
"""
try:
    from mimic_bench import *  # noqa: F401,F403
    from mimic_bench import __all__ as _legacy_all
    __all__ = list(_legacy_all)
except ImportError:
    __all__: list[str] = []
