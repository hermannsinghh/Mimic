"""Monte Carlo orchestration.

Per Plan §1.1, mimic-sim is absorbed into mimic-framework. During the
0.2.x transition, this module re-exports the legacy `mimic_sim` package
so existing code keeps working.

TODO (F-08+): consolidate the legacy module into this directory.
"""
try:
    from mimic_sim import *  # noqa: F401,F403
    from mimic_sim import __all__ as _legacy_all
    __all__ = list(_legacy_all)
except ImportError:  # legacy package not installed yet
    __all__: list[str] = []
