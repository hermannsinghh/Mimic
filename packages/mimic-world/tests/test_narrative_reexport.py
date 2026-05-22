"""W-03: CascadeEngine reachable from mimic_world.narrative."""
from __future__ import annotations


def test_narrative_reexports_cascade_engine():
    from mimic_world.cascade import CascadeEngine as Legacy
    from mimic_world.narrative import CascadeEngine as Canonical
    assert Legacy is Canonical


def test_narrative_module_docstring_calls_out_descriptive_layer():
    import mimic_world.narrative as n
    assert n.__doc__ is not None
    assert "descriptive" in n.__doc__.lower() or "narrative" in n.__doc__.lower()
