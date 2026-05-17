# Mimic

**Compose foundation models into corporate decision agents.**

Mimic lets you spin up an LLM-based digital twin of any public company, then simulate how it would respond to real-world events — validated against what companies actually did.

```python
import mimic

twin = mimic.Twin.from_ticker("WMT")
result = twin.simulate("China port closes for 30 days")
print(result.pretty())
```

```
EVENT: China port closes for 30 days
────────────────────────────────────────
0-24h:  Activate Vietnam + Mexico supplier tier, alert logistics team
1-7d:   Pre-build 45-day inventory buffer on top 200 SKUs
8-30d:  Temporary pricing adjustment on affected categories (+2-4%)

Financial impact (P10/P50/P90): -$800M / -$1.4B / -$2.1B
Confidence: 73%
```

---

## How It Works

Mimic composes three things that already exist — foundation models, free public data, and textbook economic formulas — into something that doesn't: **validated company behavior simulation.**

```
SEC EDGAR (free)     →
yfinance (free)      →  CompanyContext  →  Economic Formulas  →  LLM Orchestrator  →  Decision
FRED / news (free)   →
                            ↑
                    TimesFM / Chronos (plug-and-play)
```

**You swap any component in one line.** Don't want TimesFM? Use Chronos. Don't want GPT-4? Use Claude. Don't want the default COGS formula? Override it.

---

## Install

```bash
pip install mimic-framework
```

Requires Python 3.11+. Set `OPENAI_API_KEY` in your env.

---

## Quick Start

### 1. Build a twin from any ticker

```python
from mimic import Twin

# Auto-pulls from SEC EDGAR + yfinance
twin = Twin.from_ticker("AAPL")
```

### 2. Simulate an event

```python
result = twin.simulate(
    event="Taiwan Strait closes for 6 weeks",
    severity=0.85,
)

print(result.immediate_action_0_24h)
print(result.financial_impact_mid)   # $M, P50 estimate
print(result.confidence)
```

### 3. Swap foundation models (plug-and-play)

```python
import mimic

twin = Twin.from_ticker("JPM")
result = twin.simulate("Fed raises rates 100bps", model="claude-opus-4-5")
```

### 4. Run the benchmark

```python
from mimic.benchmark import run_benchmark

results = run_benchmark(
    tickers=["WMT", "AAPL", "JPM", "XOM", "MSFT"],
    event_set="crisis_2015_2024",
)
print(results.summary())
# Average fidelity: 0.71 across 2,847 labeled (event, company) pairs
```

---

## Economic Formulas Library

Mimic ships 10 textbook economic primitives that feed into every simulation. Each is a pure Python function and fully overridable:

| Formula | What It Computes |
|---|---|
| `dcf_impact` | EV change from a cash flow shock |
| `altman_z` | Bankruptcy risk score |
| `cogs_sensitivity` | Input cost shock → margin impact |
| `fx_passthrough` | Currency moves → P&L impact |
| `inventory_burn` | Days of buffer remaining |
| `bayes_update` | Probability updating from new evidence |
| `capm_response` | Stock reaction to market move |
| `operating_leverage` | Margin elasticity to revenue |
| `supplier_hhi` | Supply concentration risk (HHI) |
| `cascade_propagate` | Supply chain shock propagation |

```python
from mimic.formulas import cogs_sensitivity

result = cogs_sensitivity(
    revenue=650_000,   # $M
    cogs=490_000,
    input_shock_pct=0.15,   # 15% cost spike
    passthrough_rate=0.40,
)
# {'margin_compression': 0.031, 'annual_ebitda_impact_usdM': -4410.0}
```

---

## Benchmark

Mimic ships a benchmark of **200 historical events × 50 companies**, with ~2,800 ground-truth-labeled (event, company) response pairs extracted from actual earnings calls and 8-K filings.

| Metric | v0.1 |
|---|---|
| Average fidelity score | 0.71 |
| Companies covered | 50 (S&P 500) |
| Historical events | 200 (2010–2024) |
| Labeled pairs | ~2,847 |

---

## Roadmap

- [x] SEC EDGAR ingestion
- [x] 10 economic formulas
- [x] LLM orchestrator (GPT-4o + Claude)
- [x] Benchmark v1 (200 events × 50 companies)
- [ ] TimesFM + Chronos integration (v0.2)
- [ ] FinBERT2 sentiment layer (v0.2)
- [ ] Multi-company simulation (v0.3)
- [ ] REST API + hosted version

---

## License

MIT
