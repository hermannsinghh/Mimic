"""Tests for MacroEnvironment."""

from __future__ import annotations

import pytest

from mimic_world.macro import MacroEnvironment


class TestMacroEnvironment:
    def test_default_state(self) -> None:
        macro = MacroEnvironment()
        state = macro.get_state()
        assert "interest_rates" in state
        assert "fx_rates" in state
        assert "commodity_prices" in state
        assert "credit_spreads" in state

    def test_apply_shock_interest_rate(self) -> None:
        macro = MacroEnvironment()
        original = macro.interest_rates["us"]
        macro.apply_shock({"us": 0.02})
        assert macro.interest_rates["us"] == pytest.approx(original + 0.02)

    def test_apply_shock_fx_rate(self) -> None:
        macro = MacroEnvironment()
        original = macro.fx_rates["usd_eur"]
        macro.apply_shock({"usd_eur": 0.05})
        assert macro.fx_rates["usd_eur"] == pytest.approx(original * 1.05)

    def test_apply_shock_commodity(self) -> None:
        macro = MacroEnvironment()
        original = macro.commodity_prices["crude_oil_bbl"]
        macro.apply_shock({"crude_oil_bbl": 0.40})
        assert macro.commodity_prices["crude_oil_bbl"] == pytest.approx(original * 1.40)

    def test_interest_rate_cannot_go_negative(self) -> None:
        macro = MacroEnvironment()
        macro.apply_shock({"us": -1.0})
        assert macro.interest_rates["us"] >= 0.0

    def test_unknown_shock_key_is_ignored(self) -> None:
        macro = MacroEnvironment()
        macro.apply_shock({"nonexistent_key": 0.5})  # should not raise

    def test_flat_dict_has_fx_rates(self) -> None:
        macro = MacroEnvironment()
        flat = macro.as_flat_dict()
        assert "usd_eur" in flat
        assert "usd_cny" in flat
        assert "us_interest_rate" in flat

    def test_forecast_macro_returns_state(self) -> None:
        macro = MacroEnvironment()
        forecast = macro.forecast_macro(horizon_days=90)
        assert "interest_rates" in forecast
