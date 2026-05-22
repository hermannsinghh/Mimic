"""Tests for the model registry and event classification."""

import pytest

from mimic_forecast import registry


def test_detect_event_type_energy():
    assert registry.detect_event_type("oil spikes to $150 due to OPEC cuts") == "energy"


def test_detect_event_type_supply_chain():
    assert registry.detect_event_type("port strikes delay shipments") == "supply_chain"


def test_detect_event_type_macro():
    assert registry.detect_event_type("Fed raises interest rates by 100bps") == "macro"


def test_detect_event_type_geopolitical():
    assert registry.detect_event_type("US imposes tariffs on China imports") == "geopolitical"


def test_series_for_event_energy():
    series = registry.series_for_event("energy")
    assert "oil_price" in series
    assert "natural_gas_price" in series


def test_series_for_event_macro():
    series = registry.series_for_event("macro")
    assert "fed_funds_rate" in series
    assert "cpi" in series


def test_series_for_event_unknown_returns_empty():
    series = registry.series_for_event("unknown_event_xyz")
    assert series == []


def test_series_registry_has_best_model():
    for name, spec in registry.SERIES_REGISTRY.items():
        assert "best_model" in spec, f"'{name}' missing best_model"
        assert "ticker" in spec, f"'{name}' missing ticker"
        assert "source" in spec, f"'{name}' missing source"


def test_get_adapter_invalid_name():
    with pytest.raises(ValueError, match="Unknown model"):
        registry.get_adapter("nonexistent_model_xyz")
