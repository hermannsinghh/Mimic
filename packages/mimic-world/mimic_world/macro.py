"""MacroEnvironment — interest rates, FX, commodity prices, credit spreads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MacroEnvironment:
    """
    Shared macroeconomic state for the world simulation.

    Updated at each cascade step based on:
    1. Scenario-defined shock trajectories
    2. Feedback from twin decisions (e.g. 40 companies cut capex → growth slows)
    3. BISTRO/TimesFM forecasts from mimic-forecast (Phase 3 integration)
    """

    interest_rates: dict[str, float] = field(
        default_factory=lambda: {
            "us": 0.053,
            "eu": 0.040,
            "cn": 0.035,
            "jp": 0.001,
            "uk": 0.052,
        }
    )
    fx_rates: dict[str, float] = field(
        default_factory=lambda: {
            "usd_eur": 0.920,
            "usd_cny": 7.240,
            "usd_twd": 31.50,
            "usd_jpy": 149.0,
            "usd_krw": 1320.0,
            "usd_inr": 83.10,
            "usd_brl": 4.970,
        }
    )
    commodity_prices: dict[str, float] = field(
        default_factory=lambda: {
            "crude_oil_bbl": 82.0,
            "natural_gas_mmbtu": 2.8,
            "copper_lb": 4.2,
            "lithium_kg": 14.0,
            "silicon_wafer": 12.0,
            "shipping_container_40ft": 1800.0,
            "jet_fuel_gal": 2.9,
            "wheat_bushel": 5.8,
            "corn_bushel": 4.6,
            "rare_earth_kg": 42.0,
        }
    )
    credit_spreads: dict[str, float] = field(
        default_factory=lambda: {
            "aaa": 0.005,
            "aa": 0.010,
            "a": 0.020,
            "bbb": 0.040,
            "bb": 0.120,
            "b": 0.250,
        }
    )

    def apply_shock(self, shock: dict[str, Any]) -> None:
        """Apply a shock dict. Rates shift additively; prices/FX shift multiplicatively."""
        for key, delta in shock.items():
            if not isinstance(delta, (int, float)):
                continue
            if key in self.interest_rates:
                self.interest_rates[key] = max(0.0, self.interest_rates[key] + delta)
            elif key in self.fx_rates:
                self.fx_rates[key] *= 1.0 + delta
            elif key in self.commodity_prices:
                self.commodity_prices[key] *= 1.0 + delta
            elif key in self.credit_spreads:
                self.credit_spreads[key] = max(0.0, self.credit_spreads[key] + delta)

    def get_state(self) -> dict[str, Any]:
        return {
            "interest_rates": dict(self.interest_rates),
            "fx_rates": dict(self.fx_rates),
            "commodity_prices": dict(self.commodity_prices),
            "credit_spreads": dict(self.credit_spreads),
        }

    def as_flat_dict(self) -> dict[str, float]:
        """Return a flat dict suitable for world_state context."""
        state: dict[str, float] = {}
        state.update(self.fx_rates)
        for k, v in self.commodity_prices.items():
            clean = k.replace("_bbl", "").replace("_mmbtu", "").replace("_lb", "").replace(
                "_kg", ""
            ).replace("_gal", "").replace("_bushel", "").replace("_40ft", "")
            state[clean] = v
        state["us_interest_rate"] = self.interest_rates["us"]
        return state

    def forecast_macro(self, horizon_days: int) -> dict[str, Any]:
        """Placeholder for BISTRO/TimesFM integration from mimic-forecast (Phase 3)."""
        return self.get_state()
