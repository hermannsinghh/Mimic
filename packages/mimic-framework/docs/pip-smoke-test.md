# Pip smoke test — `mimic-framework`

Acceptance checklist for verifying the **published PyPI package** (and optionally an editable dev install). Run in a **fresh virtualenv** so you are not accidentally testing your source tree.

## Prerequisites

- Python **3.11** or **3.12** (system `python3` on macOS is often 3.9 — use `python3.11` or set `PYTHON=python3.11`)
- Network access (SEC EDGAR, yfinance) for Layers 2–3
- **`DEEPSEEK_API_KEY`** in `deepseek.env` (preferred) or **`OPENAI_API_KEY`** in `.env` for Layer 3 and 10-K extraction

Copy `deepseek.env.example` → `deepseek.env`. The CLI and smoke script load `deepseek.env` before `.env`.

Optional: `pip install mimic-framework[dotenv]` for automatic env loading.

## Quick run (automated)

From the repo root, with a venv already activated or let the script create one:

```bash
./scripts/acceptance_pip.sh
```

Set `MIMIC_SMOKE_LAYER=3` and `OPENAI_API_KEY` to run the full LLM simulate step. Default is Layer 0–2 only (no API key required).

## Layer 0 — Install and entry point

```bash
python3.11 -m venv /tmp/mimic-pip-test
source /tmp/mimic-pip-test/bin/activate
pip install --upgrade pip
pip install mimic-framework
pip install mimic-framework[dotenv]   # optional
mimic --help
python -c "import mimic; from mimic import Twin; print('OK', mimic.__file__)"
```

**Pass:** `mimic` on PATH; import resolves inside the venv.

## Layer 1 — Offline (no API key, no network)

```bash
python -c "
from mimic.formulas import cogs_sensitivity
r = cogs_sensitivity(revenue=650_000, cogs=490_000, input_shock_pct=0.15, passthrough_rate=0.40)
assert r['annual_ebitda_impact_usdM'] < 0
print('formulas OK', r['annual_ebitda_impact_usdM'])
"
```

**Pass:** assertion succeeds; negative EBITDA impact printed.

## Layer 2 — Data path (network; LLM optional)

```bash
mimic context WMT
```

**Pass:** ticker resolves; financial snapshot and company name print. A second run the same day should use cache (`~/.mimic/cache`).

Without `OPENAI_API_KEY`, 10-K strategy fields may be empty — that is expected.

## Layer 3 — Full simulate (requires `OPENAI_API_KEY`)

```bash
# With deepseek.env in the repo root (or cwd):
mimic simulate WMT "China port closes for 30 days" -s 0.7
# Default model: deepseek-chat when DEEPSEEK_API_KEY is set, else gpt-4o
```

**Pass:** structured output with 0–24h / 1–7d / 8–30d actions and P10/P50/P90 financial impacts.

## Dev parity (repo contributors)

```bash
cd /path/to/Mimic
pip install -e ".[dev]"
pytest tests/ -v --tb=short
./scripts/acceptance_pip.sh --editable
```

## Release matrix (before tagging)

| Install | Python | Layer 1 | Layer 2 | Layer 3 |
|---------|--------|---------|---------|---------|
| `pip install mimic-framework==X.Y.Z` | 3.11 | required | required | optional |
| same | 3.12 | required | required | optional |
| `pip install -e ".[dev]"` | 3.11 | pytest + L1 | L2 | L3 |

## Known gaps (v0.1)

- `from mimic.benchmark import run_benchmark` in README is **not implemented**; use `Twin.benchmark(events)` only.
- LLM output is **not** byte-identical across runs (temperature 0.2).
- CI runs editable install + pytest only; it does **not** substitute for this PyPI smoke test.

## Record results

| Field | Value |
|-------|-------|
| Version (`pip show mimic-framework`) | |
| Python | |
| Install source (PyPI / editable) | |
| Highest layer passed | |
| Date | |
| Notes | |

### Latest run (2026-05-20)

| Check | Result |
|-------|--------|
| Editable `pip install -e ".[dev,dotenv]"` L0–L2 | **PASS** (Python 3.11, venv `/tmp/mimic-pip-test`) |
| PyPI `pip install mimic-framework[dotenv]` L0–L2 | **PASS** (venv `/tmp/mimic-pip-pypi`) |
| Layer 3 simulate (DeepSeek `deepseek-chat`) | **PASS** (2026-05-20) |

**Follow-ups from smoke test:**

1. Layer 3 with DeepSeek: `MIMIC_SMOKE_LAYER=3 ./scripts/acceptance_pip.sh --editable`
2. ~~Revenue TTM $0M~~ — fixed in v0.1+ (`unwrap_company_facts`; cache schema `v2` invalidates stale zeros).
3. Run PyPI test from a neutral cwd — the script uses `${TMPDIR}/mimic-smoke-run` so a repo checkout does not shadow the installed package.

**Re-fetch after SEC fix:** cache files use schema `v2`. Old caches are ignored automatically. Force refresh: `Twin.from_ticker('WMT', use_cache=False)` or `mimic simulate WMT "..." --no-cache`.
