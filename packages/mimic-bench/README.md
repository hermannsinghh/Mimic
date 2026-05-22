# mimic-bench

**The benchmark suite for LLM-based corporate decision simulation.**

`pip install mimic-bench`

mimic-bench answers one question: *"How accurately does a model predict what a real company actually did in response to a macro shock?"*

It provides:
1. **The dataset** — 200 historical events × 50 companies ≈ 2,800 labeled (event, company) pairs
2. **The scoring system** — a 4-component fidelity metric that compares model predictions to documented corporate actions

---

## How it fits

```
mimic         → builds company twins, simulates decisions
mimic-bench   → grades those simulations against reality   ← you are here
mimic-forecast → plugs in foundation models (TimesFM, Chronos)
mimic-world   → stress tests entire supply chains
mimic-sim     → Monte Carlo with LLM agents
mimic-signal  → real-time event detection
```

Without mimic-bench, mimic is a demo. With it, mimic is a research tool.

---

## Quickstart

```python
from mimic_bench import Benchmark
import anthropic

client = anthropic.Anthropic()

def my_predict(prompt: str) -> str:
    msg = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text

bench = Benchmark.load("v1", predict_fn=my_predict)
results = bench.run(verbose=True)

print(results)
# BenchmarkResult(n=200, errors=0, fidelity=0.67)

print(results.by_category())
# {'macro': 0.71, 'supply_chain': 0.68, 'energy': 0.65, 'geopolitical': 0.63, ...}

print(results.worst_events(n=3))
# [{'event_id': '2021_08_hurricane_ida', 'mean': 0.52, ...}, ...]
```

With a `mimic.Twin`:

```python
from mimic import Twin
from mimic_bench import Benchmark

bench = Benchmark.load("v1")
twin = Twin.from_ticker("WMT")

results = bench.run(twin, subset="supply_chain")
print(results.fidelity_score)      # 0.71
print(results.worst_events(n=5))   # where the twin failed most
```

---

## Fidelity Score

| Component | Weight | Description |
|-----------|--------|-------------|
| Action alignment | 40% | Cosine similarity of predicted vs actual action strings (sentence-transformers) |
| Financial accuracy | 30% | `1 - min(|predicted - actual| / |actual|, 1)` |
| Direction accuracy | 20% | Sign match on financial impact (+/-) |
| Timing accuracy | 10% | Whether the model identified the right response window (0-24h, 1-7d, 8-30d) |

v0.1 target: **0.65+ average** across labeled pairs.

---

## Dataset

### v0.1 Seed Set (this release)
- **10 events** (hand-curated, 2020–2023)
- **20 companies** (large-cap S&P 500, spread across 5 sectors)
- **200 labeled pairs**, all human-reviewed

### v1.0 Target
- **200 events** across 8 categories (2010–2024)
- **50 companies** (10 per sector)
- **~2,800 high-signal pairs** (not every event affects every company)

### Event categories
| Category | Count | Examples |
|----------|-------|---------|
| Supply chain shocks | 30 | Suez Canal, Port of LA, COVID factory shutdowns |
| Geopolitical shocks | 30 | Russia-Ukraine, US-China tariffs, TSMC export controls |
| Macro / monetary | 25 | Fed hikes, SVB collapse, 2022 inflation peak |
| Energy | 20 | Oil crash, European gas crisis, OPEC cuts |
| Natural disasters | 20 | Hurricane Ida, Texas freeze, Japan earthquake |
| Industry-specific | 30 | Chip shortage, EV battery crunch |
| Pandemic / health | 20 | COVID waves, China lockdowns and reopening |
| Regulatory / policy | 25 | EU DMA, SEC climate rules, IRA credits |

### Ground Truth Schema

```jsonc
// data/ground_truth/labels_v1.jsonl  (one JSON object per line)
{
  "event_id": "2021_03_suez_canal",
  "ticker": "FDX",
  "actual_action_0_24h": "Issued customer advisory; began contingency routing planning",
  "actual_action_1_7d": "Rerouted 14 ocean freight shipments via Cape of Good Hope",
  "actual_action_8_30d": "Added temporary fuel/route surcharge on affected trade lanes",
  "financial_impact_usdM": -45.0,
  "financial_impact_reported": true,
  "source_type": "earnings_call",
  "source_url": "https://seekingalpha.com/...",
  "extraction_method": "llm_claude-opus-4-7",
  "confidence": 0.82,
  "human_reviewed": false
}
```

### Event Schema

```jsonc
// data/events/2021_03_suez_canal.json
{
  "id": "2021_03_suez_canal",
  "title": "Suez Canal blockage — Ever Given grounding",
  "date": "2021-03-23",
  "end_date": "2021-03-29",
  "category": "supply_chain",
  "severity": 0.60,           // 0.0 = minimal, 1.0 = extreme
  "description": "...",
  "affected_sectors": ["logistics", "retail", "energy"],
  "affected_geographies": ["global", "europe"],
  "keywords": ["suez", "ever given", "shipping"],
  "source": "Suez Canal Authority",
  "source_url": "https://..."
}
```

---

## Ground Truth Extraction Pipeline

```
Stage 1  Signal detection (automated)
         ├── Fetch 8-K filings from SEC EDGAR within 30 days of event
         ├── Check earnings call transcripts for event keywords
         └── If signal found → proceed to Stage 2
             If no signal  → mark as "not materially affected"

Stage 2  LLM extraction (semi-automated)
         ├── Feed 8-K text + transcript excerpt to Claude
         ├── Extract: action_0_24h, action_1_7d, action_8_30d, financial_impact_usdM
         └── Store raw + structured output

Stage 3  Human review (spot-check 10%)
         ├── python scripts/validate_labels.py --sample 280
         └── Adjust confidence_in_label accordingly
```

Run it:

```bash
# Extract all events, all companies (requires ANTHROPIC_API_KEY)
python scripts/extract_ground_truth.py

# Single event
python scripts/extract_ground_truth.py --event 2021_03_suez_canal

# Dry run (print prompts, skip API calls)
python scripts/extract_ground_truth.py --dry-run
```

---

## Leaderboard

```python
from mimic_bench.leaderboard import submit, display

results = bench.run(my_twin)
submit(results, model_name="mimic-v0.2-rag", notes="Added SEC EDGAR RAG")
display()
```

```
Rank  Model                          Fidelity     Std      N   Submitted
------------------------------------------------------------------------
1     mimic-v0.2-rag                   0.7312  0.1201    200  2024-09-01
2     mimic-v0.1-baseline              0.6543  0.1389    200  2024-08-15
3     gpt-4o-zero-shot                 0.6201  0.1501    200  2024-08-20
```

---

## Repo Structure

```
mimic-bench/
├── pyproject.toml
├── README.md
├── data/
│   ├── events/              ← 200 event JSON files (v0.1: 10 events)
│   ├── ground_truth/
│   │   └── labels_v1.jsonl  ← ~2,800 labeled pairs (v0.1: 200 pairs)
│   ├── companies.json        ← 50 company definitions
│   └── leaderboard.json      ← submitted scores
├── mimic_bench/
│   ├── benchmark.py          ← Benchmark class (main entry point)
│   ├── scoring.py            ← 4-component fidelity metric
│   ├── datasets.py           ← data loaders
│   ├── leaderboard.py        ← score submission + display
│   └── extraction/
│       ├── sec.py            ← SEC EDGAR 8-K fetcher
│       ├── transcripts.py    ← earnings call transcript parser
│       └── llm_extract.py    ← Claude extraction prompt
├── scripts/
│   ├── generate_seed_labels.py   ← generates v0.1 200-record JSONL
│   ├── extract_ground_truth.py   ← Stage 1 + 2 extraction pipeline
│   ├── validate_labels.py        ← Stage 3 human review CLI
│   └── build_event_list.py       ← scaffold new event JSON files
└── examples/
    ├── 01_run_benchmark.ipynb
    ├── 02_custom_events.ipynb
    └── 03_leaderboard.ipynb
```

---

## Installation

```bash
# Core (no dependencies)
pip install mimic-bench

# With semantic similarity scoring (recommended)
pip install "mimic-bench[semantic]"

# With extraction pipeline
pip install "mimic-bench[extraction]"

# Everything
pip install "mimic-bench[all]"
```

---

## Paper

*MimicBench: A Benchmark for LLM-Based Corporate Decision Simulation*

Target venue: NeurIPS 2025 Datasets & Benchmarks track, or ICLR 2026.

---

## License

MIT © Mimic
