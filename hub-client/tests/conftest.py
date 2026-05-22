"""Ensure mimic-framework is importable for hub-client tests."""
from __future__ import annotations

import sys
from pathlib import Path

_FRAMEWORK = Path(__file__).resolve().parents[2] / "packages" / "mimic-framework"
if _FRAMEWORK.exists() and str(_FRAMEWORK) not in sys.path:
    sys.path.insert(0, str(_FRAMEWORK))
