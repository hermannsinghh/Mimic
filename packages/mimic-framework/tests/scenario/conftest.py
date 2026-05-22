"""Make sibling packages importable for e2e scenario tests."""
from __future__ import annotations

import sys
from pathlib import Path

_PACKAGES = Path(__file__).resolve().parents[3]
for sibling in ("mimic-world", "mimic-forecast"):
    p = _PACKAGES / sibling
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
