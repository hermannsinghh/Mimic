"""Make mimic-framework + mimic-world importable for the equivalence harness."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
for sibling in ("packages/mimic-framework", "packages/mimic-world"):
    p = _REPO / sibling
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
# eval/harness lives at repo root
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
