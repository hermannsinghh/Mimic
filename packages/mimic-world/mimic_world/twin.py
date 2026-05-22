"""
Twin — LLM-backed company simulation stub for mimic-world.

This module provides a self-contained Twin that uses Claude to simulate
executive decision-making. It is designed to be drop-in compatible with
mimic.Twin (the single-company twin package); when mimic is published,
users can pass mimic.Twin objects directly to World.add_twin().

Interface contract (duck-typed):
  twin.ticker: str
  twin.simulate(world_state: dict, step: int) -> Decision
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from .result import Decision

# ---------------------------------------------------------------------------
# Company knowledge base — used by the LLM as grounding context.
# Extend or override by passing `profile=` to Twin().
# ---------------------------------------------------------------------------

COMPANY_PROFILES: dict[str, dict] = {
    "WMT": {
        "name": "Walmart",
        "sector": "retail",
        "annual_revenue_bn": 650,
        "business": (
            "World's largest retailer. Operates 10,500+ stores globally. "
            "~70% of general merchandise sourced from China. "
            "Thin operating margins (~3%). Scale and everyday-low-price strategy. "
            "Massive private-label import business. "
            "Sam's Club warehouse division. Walmart+ subscription service."
        ),
        "key_inputs": ["consumer_goods", "food", "electronics", "logistics", "fuel"],
        "key_risks": ["supply_chain_disruption", "consumer_spending", "fuel_costs", "tariffs"],
    },
    "AAPL": {
        "name": "Apple",
        "sector": "technology",
        "annual_revenue_bn": 380,
        "business": (
            "Consumer electronics, software, services. "
            "iPhone assemblers: Foxconn & Pegatron (Taiwan/China, ~90% of volume). "
            "Critical chip supplier: TSMC (100% of advanced nodes: 3nm, 5nm). "
            "Services (~$85B/yr) growing as % of revenue. "
            "High margins (~25%). $200B+ in annual buybacks."
        ),
        "key_inputs": ["semiconductors", "display_panels", "rare_earths", "contract_manufacturing"],
        "key_risks": [
            "semiconductor_supply",
            "china_operations",
            "tariffs",
            "regulatory_antitrust",
        ],
    },
    "FDX": {
        "name": "FedEx",
        "sector": "logistics",
        "annual_revenue_bn": 90,
        "business": (
            "Global express delivery. Air freight + ground network. "
            "Jet fuel is #1 variable cost (10–15% of revenue). "
            "Highly exposed to global trade volumes and e-commerce cycles. "
            "Union-free workforce. Shifting to asset-light model."
        ),
        "key_inputs": ["jet_fuel", "labor", "aircraft", "ground_vehicles", "package_volume"],
        "key_risks": ["fuel_prices", "trade_volumes", "labor_costs", "e-commerce_slowdown"],
    },
    "TSMC": {
        "name": "Taiwan Semiconductor Manufacturing Company",
        "sector": "semiconductors",
        "annual_revenue_bn": 90,
        "business": (
            "World's dominant chip foundry. Makes 90%+ of the world's advanced chips. "
            "Customers: AAPL, NVDA, AMD, QCOM, MSFT (Azure chips). "
            "Located in Taiwan — geopolitical risk is existential. "
            "Expanding to Arizona (N4 node), Kumamoto Japan (N12), Dresden Germany. "
            "Gross margins ~55%. R&D moat is 5+ years ahead of Samsung/Intel Foundry."
        ),
        "key_inputs": ["silicon_wafers", "chemicals", "ultra-pure_water", "ASML_equipment"],
        "key_risks": [
            "taiwan_geopolitics",
            "equipment_export_controls",
            "water_supply",
            "talent",
        ],
    },
    "XOM": {
        "name": "ExxonMobil",
        "sector": "energy",
        "annual_revenue_bn": 400,
        "business": (
            "Integrated oil & gas supermajor. Upstream E&P, downstream refining, chemicals. "
            "Revenue highly correlated with Brent crude price. "
            "Largest US refining capacity. Pioneer acquisition added Permian scale. "
            "Dividend commitment drives capital allocation."
        ),
        "key_inputs": ["crude_oil", "natural_gas", "refining_capacity", "capital"],
        "key_risks": [
            "oil_price_volatility",
            "energy_transition_regulation",
            "geopolitical_access",
        ],
    },
    "NVDA": {
        "name": "NVIDIA",
        "sector": "semiconductors",
        "annual_revenue_bn": 60,
        "business": (
            "GPU designer. Dominant in AI/ML training (H100, B200 series). "
            "All chips fabbed by TSMC. CUDA software ecosystem = primary moat. "
            "Data center revenue is 85%+ of total. Hyper-scalers (MSFT, GOOG, AMZN) "
            "are top customers. Very high gross margins (~75%)."
        ),
        "key_inputs": ["tsmc_fab_capacity", "hbm_memory", "substrates", "networking_ics"],
        "key_risks": [
            "tsmc_dependence",
            "export_controls_china",
            "hbm_supply",
            "custom_chip_competition",
        ],
    },
    "AMD": {
        "name": "Advanced Micro Devices",
        "sector": "semiconductors",
        "annual_revenue_bn": 23,
        "business": (
            "CPU and GPU designer. Competing Intel in data center CPUs (EPYC). "
            "AI GPU: MI300X competing with NVIDIA H100 at lower price. "
            "All manufacturing outsourced to TSMC. "
            "Acquired Xilinx (FPGAs) in 2022."
        ),
        "key_inputs": ["tsmc_fab_capacity", "hbm_memory", "packaging"],
        "key_risks": ["tsmc_dependence", "nvidia_dominance", "inventory_cycles"],
    },
    "AMZN": {
        "name": "Amazon",
        "sector": "e-commerce_cloud",
        "annual_revenue_bn": 590,
        "business": (
            "E-commerce, AWS cloud (#1 globally at 31% share), advertising, logistics. "
            "AWS is primary profit driver (~70% of operating income). "
            "Built the world's largest private logistics network (AMZL). "
            "Alexa, Ring, Prime Video ecosystem."
        ),
        "key_inputs": [
            "logistics_capacity",
            "cloud_hardware_chips",
            "labor",
            "consumer_goods_inventory",
        ],
        "key_risks": [
            "logistics_disruption",
            "chip_supply_for_aws",
            "labor_costs",
            "antitrust",
        ],
    },
    "MAERSK": {
        "name": "A.P. Møller-Mærsk",
        "sector": "logistics",
        "annual_revenue_bn": 55,
        "business": (
            "World's largest container shipping company (~17% of global capacity). "
            "Owns 700+ vessels. Pivoting to integrated logistics (warehousing, air freight). "
            "Revenue extremely cyclical with container rate cycles."
        ),
        "key_inputs": ["bunker_fuel", "port_access", "vessel_capacity", "crew"],
        "key_risks": [
            "freight_rate_cycles",
            "canal_disruptions",
            "fuel_price",
            "port_congestion",
        ],
    },
    "DAL": {
        "name": "Delta Air Lines",
        "sector": "aviation",
        "annual_revenue_bn": 58,
        "business": (
            "US major carrier. Premium positioning (Sky Club, Amex partnership). "
            "Jet fuel is 20–25% of operating costs. "
            "Transatlantic and transpacific routes depend on overflight rights."
        ),
        "key_inputs": ["jet_fuel", "aircraft", "labor_pilots_crew", "airport_gates"],
        "key_risks": ["fuel_prices", "recession_travel_demand", "labor_strikes"],
    },
}


def _build_client(requested_model: str) -> Any:
    """
    Build an LLM client based on available API keys.

    Priority:
      1. DEEPSEEK_API_KEY → OpenAI client pointed at api.deepseek.com
      2. ANTHROPIC_API_KEY → Anthropic client

    The returned client has two extra attributes:
      ._mimic_provider  : "deepseek" | "anthropic"
      ._mimic_model     : the resolved model name to use
    """
    import os

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if deepseek_key:
        try:
            import openai
        except ImportError as e:
            raise ImportError(
                "openai package is required for DeepSeek: pip install openai"
            ) from e
        client = openai.OpenAI(
            api_key=deepseek_key,
            base_url="https://api.deepseek.com",
        )
        client._mimic_provider = "deepseek"  # type: ignore[attr-defined]
        client._mimic_model = "deepseek-chat"  # type: ignore[attr-defined]
        return client

    if anthropic_key:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "anthropic package is required: pip install anthropic"
            ) from e
        client = anthropic.Anthropic()
        client._mimic_provider = "anthropic"  # type: ignore[attr-defined]
        client._mimic_model = requested_model  # type: ignore[attr-defined]
        return client

    raise EnvironmentError(
        "No LLM API key found. Set DEEPSEEK_API_KEY or ANTHROPIC_API_KEY."
    )


def _get_profile(ticker: str, override: Optional[dict] = None) -> dict:
    if override:
        return override
    return COMPANY_PROFILES.get(
        ticker,
        {
            "name": ticker,
            "sector": "unknown",
            "annual_revenue_bn": 10,
            "business": f"Company with ticker {ticker}. No detailed profile available.",
            "key_inputs": [],
            "key_risks": [],
        },
    )


@dataclass
class Twin:
    """
    LLM-backed company twin. Uses Claude to simulate C-suite decision-making.

    Implements the same interface as mimic.Twin so it can be swapped out
    transparently once the mimic package is published.

    Usage:
        twin = Twin.from_ticker("AAPL")
        decision = twin.simulate(world_state={"semiconductor_supply": -0.65}, step=1)
    """

    ticker: str
    profile: dict = field(default_factory=dict)
    model: str = "claude-sonnet-4-6"
    _client: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.profile:
            self.profile = _get_profile(self.ticker)
        if self._client is None:
            self._client = _build_client(self.model)
            # _build_client may update the model name to match the provider
            self.model = self._client._mimic_model  # type: ignore[attr-defined]

    @classmethod
    def from_ticker(cls, ticker: str, profile: Optional[dict] = None) -> Twin:
        return cls(ticker=ticker, profile=_get_profile(ticker, profile))

    def simulate(self, world_state: dict, step: int = 1) -> Decision:
        """
        Given the current world_state, simulate what this company's leadership decides.
        Calls the configured LLM (Anthropic or DeepSeek) and returns a structured Decision.
        """
        prompt = self._build_prompt(world_state, step)
        provider = getattr(self._client, "_mimic_provider", "anthropic")

        if provider == "deepseek":
            response = self._client.chat.completions.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content
        else:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text

        return self._parse_response(text, step)

    def _build_prompt(self, world_state: dict, step: int) -> str:
        def fmt_val(v: Any) -> str:
            if isinstance(v, float):
                return f"{v:+.1%}"
            return str(v)

        # Filter out internal keys for display
        display_state = {
            k: fmt_val(v) for k, v in world_state.items() if not k.startswith("_")
        }
        state_lines = "\n".join(f"  {k}: {v}" for k, v in display_state.items())

        scenario_title = world_state.get("_scenario_title", "economic disruption")
        severity = world_state.get("_scenario_severity", 0.5)
        partners = world_state.get("_affected_partners", "")

        partner_line = f"\nAffected supply-chain partners: {partners}" if partners else ""

        return f"""You are the CEO/CFO of {self.profile['name']} ({self.ticker}), one of the world's largest companies.

SCENARIO: {scenario_title} (severity: {severity:.0%})

COMPANY PROFILE:
Sector: {self.profile['sector']}
Annual Revenue: ~${self.profile['annual_revenue_bn']}B
Business: {self.profile['business']}
Key inputs: {', '.join(self.profile['key_inputs'])}
Key risks: {', '.join(self.profile['key_risks'])}{partner_line}

CURRENT WORLD STATE — Day {step}:
{state_lines}

What does {self.profile['name']} do RIGHT NOW in response to this situation?

Respond ONLY with this JSON (no markdown, no explanation outside the JSON):
{{
  "actions": [
    "Specific concrete action 1 (e.g. activate $2B emergency inventory purchase)",
    "Specific concrete action 2",
    "Specific concrete action 3"
  ],
  "reasoning": "One to two sentences explaining the core decision logic.",
  "world_state_updates": {{
    "key_affected_by_this_decision": delta_as_float
  }},
  "financial_impact": {{
    "revenue_impact_pct": float,
    "margin_impact_pct": float,
    "severity": "low|medium|high|critical"
  }}
}}

Rules:
- actions: 2–4 specific, realistic actions at the scale of this company
- world_state_updates: how this company's decisions change shared market conditions
  Examples: hoarding chips → "semiconductor_spot_demand": +0.15
             cutting orders → "supplier_order_volume": -0.12
             rerouting ships → "alternative_shipping_route_demand": +0.20
- revenue_impact_pct: fraction of annual revenue affected (negative = loss)
- Be realistic about this company's actual capabilities, scale, and timeline
- world_state_updates represent second-order effects that other companies will see"""

    def _parse_response(self, text: str, step: int) -> Decision:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return Decision(
                ticker=self.ticker,
                step=step,
                actions=["Unable to determine action — awaiting more information"],
                reasoning="Response parse error; defaulting to wait-and-see.",
                world_state_updates={},
                financial_impact={"revenue_impact_pct": 0.0, "severity": "low"},
            )

        try:
            data = json.loads(text[start:end])
        except json.JSONDecodeError:
            return Decision(
                ticker=self.ticker,
                step=step,
                actions=["Hold current operations; monitor situation closely"],
                reasoning="Unable to parse LLM response; defaulting to status quo.",
                world_state_updates={},
                financial_impact={"revenue_impact_pct": -0.02, "severity": "low"},
            )

        return Decision(
            ticker=self.ticker,
            step=step,
            actions=data.get("actions", []),
            reasoning=data.get("reasoning", ""),
            world_state_updates={
                k: float(v)
                for k, v in data.get("world_state_updates", {}).items()
                if isinstance(v, (int, float))
            },
            financial_impact=data.get("financial_impact", {}),
        )

    def __repr__(self) -> str:
        return f"Twin(ticker={self.ticker!r}, sector={self.profile.get('sector', '?')!r})"
