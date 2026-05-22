# mimic-forecast

**Foundation model adapter layer for the Mimic ecosystem.**

Replace LLM-guessed financial numbers with real quantitative forecasts.

```
Without mimic-forecast:
  twin.simulate("oil spikes") → LLM guesses financial impact

With mimic-forecast:
  twin.simulate("oil spikes") → TimesFM forecasts price trajectory
                              → Chronos forecasts market dynamics
                              → LLM reasons on top of real numbers
```

## Install

```bash
# Core only (abstractions + ensemble, no model deps)
pip install mimic-forecast

# With a specific model
pip install 'mimic-forecast[timesfm]'
pip install 'mimic-forecast[chronos]'
pip install 'mimic-forecast[finbert]'

# With data utilities (FRED + yfinance)
pip install 'mimic-forecast[data]'

# Everything
pip install 'mimic-forecast[all]'
```

## Quickstart

```python
from mimic_forecast import TimesFMAdapter
import yfinance as yf

adapter = TimesFMAdapter()
data = yf.download("WMT", period="2y")["Close"].squeeze()
forecast = adapter.forecast(data, horizon=30, frequency="D")

print(forecast.point)           # 30-day point forecast
print(forecast.quantiles[0.1])  # P10 (downside)
print(forecast.quantiles[0.9])  # P90 (upside)
print(forecast.summary())       # compact dict for LLM prompts
```

## Models

| Adapter | Model | Best For | Quantiles |
|---------|-------|----------|-----------|
| `TimesFMAdapter` | google/timesfm-2.0-500m | Demand, retail, energy | ✓ |
| `ChronosAdapter` | amazon/chronos-t5-large | Multivariate, covariates | ✓ |
| `FinBERT2Adapter` | ProsusAI/finbert | News sentiment → signal | ✓ |
| `KronosAdapter` | AntGroup/Kronos | Price microstructure | ✓ |
| `MoiraiAdapter` | Salesforce/moirai-1.0-R-large | Zero-shot benchmark | ✓ |
| `BISTROAdapter` | bis-models/bistro | Macro (GDP, CPI, rates) | ✓ |
| `EnsembleAdapter` | weighted combination | Maximum accuracy | ✓ |

## Auto-select

```python
from mimic_forecast import AutoForecaster

# Picks the best available model per series type
af = AutoForecaster()
results = af.forecast_for_event(
    context={"ticker": "WMT"},
    event="oil spikes to $150",
    horizon=30,
)
# results["oil_price"]["point_end"] → float
# results["oil_price"]["q10"]       → float (downside)
# results["oil_price"]["model"]     → "kronos-499m"
```

## Compare Models

```python
from mimic_forecast import compare_models, TimesFMAdapter, ChronosAdapter

results = compare_models(
    series=data,
    models=[TimesFMAdapter(), ChronosAdapter()],
    horizon=30,
    metric="RMSE",
)
print(results.winner)   # "timesfm-2.0-500m"
print(results.scores)   # {"timesfm-2.0-500m": 0.042, "chronos-t5-large": 0.051}
```

## Mimic Integration

mimic-forecast is a **zero-hard-dependency plugin** for mimic.
When installed, mimic automatically upgrades from LLM number-guessing to real forecasts.

```python
# In mimic/core/twin.py — this is what mimic does internally:
try:
    from mimic_forecast import get_forecaster
    forecaster = get_forecaster(auto=True)
    forecast_context = forecaster.forecast_for_event(self.context, event)
except ImportError:
    forecast_context = {}  # graceful fallback to LLM estimates
```

## Architecture

```
mimic_forecast/
├── base.py              ← ForecasterAdapter + ForecastResult
├── registry.py          ← Model registry + event → series mapping
├── ensemble.py          ← EnsembleAdapter
├── benchmarks.py        ← Model comparison (walk-forward backtest)
├── adapters/
│   ├── timesfm.py       ← Google TimesFM 2.0
│   ├── chronos.py       ← Amazon Chronos T5-Large
│   ├── finbert.py       ← FinBERT sentiment
│   ├── kronos.py        ← Kronos market microstructure
│   ├── moirai.py        ← Salesforce Moirai
│   └── bistro.py        ← BIS macro model
├── data/
│   ├── series.py        ← Pull from FRED / yfinance
│   └── covariates.py    ← Build covariate matrices
└── integration/
    └── mimic_plugin.py  ← Plugin interface for mimic core
```

## License

MIT
