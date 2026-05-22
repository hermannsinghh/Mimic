"""Tests for DecisionCache (Tier 2)."""

import json
import math
import tempfile
from pathlib import Path

import pytest

from mimic_sim.cache import DecisionCache, SEVERITY_GRID, DURATION_GRID
from mimic_sim.execution.tier3_formulas import CompanyProfile


@pytest.fixture
def profiles():
    return [CompanyProfile.walmart(), CompanyProfile.apple(), CompanyProfile.fedex()]


@pytest.fixture
def built_cache(profiles):
    cache = DecisionCache()
    cache.build(profiles, scenario_name="taiwan_strait_closure_30d")
    return cache


class TestDecisionCacheBuild:
    def test_grid_size(self, built_cache):
        expected = len(SEVERITY_GRID) * len(DURATION_GRID)
        assert len(built_cache) == expected

    def test_all_tickers_present(self, built_cache, profiles):
        for (s, d), entry in built_cache._grid.items():
            for p in profiles:
                assert p.ticker in entry

    def test_required_keys_in_entry(self, built_cache, profiles):
        for entry in built_cache._grid.values():
            for ticker, modifiers in entry.items():
                assert "risk_appetite_delta" in modifiers
                assert "decision_speed_delta" in modifiers

    def test_higher_severity_more_conservative(self, built_cache, profiles):
        low_risk  = built_cache._grid[(0.3, 30.0)]["WMT"]["risk_appetite_delta"]
        high_risk = built_cache._grid[(0.9, 30.0)]["WMT"]["risk_appetite_delta"]
        assert high_risk < low_risk  # higher severity → more conservative

    def test_longer_duration_faster_decisions(self, built_cache, profiles):
        short = built_cache._grid[(0.7,  7.0)]["WMT"]["decision_speed_delta"]
        long  = built_cache._grid[(0.7, 90.0)]["WMT"]["decision_speed_delta"]
        assert long > short  # longer shock → faster adaptation

    def test_scenario_name_stored(self, built_cache):
        assert built_cache._scenario_name == "taiwan_strait_closure_30d"

    def test_tickers_stored(self, built_cache, profiles):
        assert set(built_cache._tickers) == {p.ticker for p in profiles}

    def test_custom_llm_fn(self, profiles):
        def my_fn(ticker, severity, duration, scenario):
            return {"risk_appetite_delta": 0.99, "decision_speed_delta": 0.01}

        cache = DecisionCache()
        cache.build(profiles, "test", llm_fn=my_fn)
        for entry in cache._grid.values():
            for ticker, mods in entry.items():
                assert mods["risk_appetite_delta"] == pytest.approx(0.99)


class TestDecisionCacheLookup:
    def test_lookup_returns_all_tickers(self, built_cache, profiles):
        result = built_cache.lookup(0.6, 20.0)
        for p in profiles:
            assert p.ticker in result

    def test_lookup_exact_grid_point(self, built_cache):
        result = built_cache.lookup(0.5, 14.0)
        assert result is built_cache._grid[(0.5, 14.0)]

    def test_lookup_clamps_to_nearest(self, built_cache):
        # 0.01 severity, 1 day → nearest grid point is (0.3, 7)
        result = built_cache.lookup(0.01, 1.0)
        assert result is built_cache._grid[(0.3, 7.0)]

    def test_lookup_extreme_values(self, built_cache):
        result = built_cache.lookup(1.0, 365.0)
        assert "WMT" in result

    def test_lookup_empty_cache_raises(self, profiles):
        cache = DecisionCache()
        with pytest.raises(RuntimeError, match="empty"):
            cache.lookup(0.5, 30.0)


class TestDecisionCachePersistence:
    def test_save_load_roundtrip(self, built_cache, profiles):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        built_cache.save(path)
        loaded = DecisionCache.load(path)

        assert loaded._scenario_name == built_cache._scenario_name
        assert set(loaded._tickers) == set(built_cache._tickers)
        assert len(loaded) == len(built_cache)

        # Check a specific grid point survives the round-trip
        orig = built_cache._grid[(0.5, 30.0)]["WMT"]
        reloaded = loaded._grid[(0.5, 30.0)]["WMT"]
        assert reloaded["risk_appetite_delta"] == pytest.approx(orig["risk_appetite_delta"])

    def test_saved_file_is_valid_json(self, built_cache):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name

        built_cache.save(path)
        with open(path) as f:
            data = json.load(f)
        assert "grid" in data
        assert "scenario_name" in data
        assert "tickers" in data

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            DecisionCache.load("/tmp/this_file_does_not_exist_xyz.json")

    def test_repr(self, built_cache):
        r = repr(built_cache)
        assert "taiwan_strait_closure_30d" in r
        assert "20" in r  # 20 grid points
