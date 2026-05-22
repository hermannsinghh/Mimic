# NEXT_STEPS.md — mimic-bench

## Status as of 2026-05-18

### Install
FAIL. The `pyproject.toml` declares `build-backend = "setuptools.backends.legacy:build"` which is incompatible with the pip version bundled in Python 3.10 environments. Error:

```
pip._vendor.pyproject_hooks._impl.BackendUnavailable: Cannot import 'setuptools.backends.legacy'
```

**Fix:** Change `pyproject.toml` line 3 from `"setuptools.backends.legacy:build"` to `"setuptools.build_meta"`. The package imports correctly when the source directory is on `PYTHONPATH` directly. This fix is a one-line change and should be the first thing applied before any other work.

### Tests
No `tests/` directory exists. Test status: **0 passing, 0 failing (no tests written yet).**

### CI Workflow
ADDED (`.github/workflows/ci.yml`)

---

## What This Repo Does (One Paragraph)

`mimic-bench` is the benchmark suite that grades LLM-based corporate decision simulations against what companies actually did in response to historical macro shocks. It ships a curated dataset of historical events and labeled (event, company) response pairs extracted from SEC 8-K filings and earnings call transcripts, and scores model predictions against those labels using a four-component fidelity metric: action alignment (40%, cosine similarity), financial accuracy (30%), direction accuracy (20%), and timing accuracy (10%). The current v0.1 seed set has 10 events × 20 companies = 200 labeled pairs; the v1.0 target is 200 events × 50 companies ≈ 2,800 pairs.

---

## What Is Already Built

- `mimic_bench/__init__.py` — public API; re-exports `Benchmark` and `BenchmarkResult`
- `mimic_bench/benchmark.py` — `Benchmark` class: `load()`, `run(predict_fn)`, `BenchmarkResult` with fidelity score, `by_category()`, `worst_events()`
- `mimic_bench/scoring.py` — four-component fidelity metric: action alignment, financial accuracy, direction accuracy, timing accuracy
- `mimic_bench/datasets.py` — data loaders for `data/events/`, `data/ground_truth/labels_v1.jsonl`, `data/companies.json`
- `mimic_bench/leaderboard.py` — leaderboard `submit()` and `display()` against `data/leaderboard.json`
- `mimic_bench/extraction/llm_extract.py` — Claude-based structured extraction of corporate response labels from raw text
- `mimic_bench/extraction/sec.py` — SEC EDGAR 8-K fetcher via the free full-text search API
- `mimic_bench/extraction/transcripts.py` — earnings call transcript fetcher (Seeking Alpha, Motley Fool)
- `data/events/` — 10 hand-curated event JSON files (2020–2023)
- `data/ground_truth/labels_v1.jsonl` — 200 labeled (event, company) response pairs
- `data/companies.json` — 50 company definitions

---

## Immediate Next Tasks

**Priority 1 — Fix build backend (blocker)**
In `pyproject.toml`, change line 3:
```
build-backend = "setuptools.backends.legacy:build"
```
to:
```
build-backend = "setuptools.build_meta"
```
This makes `pip install -e ".[dev]"` work correctly. Without this fix nothing else can be CI-tested.

**Priority 2 — Expand to 20 events**
Currently 10 events in `data/events/`. Add 10 more covering these missing categories:
- 2 macro/monetary events (Fed hikes 2022, SVB collapse Mar 2023)
- 2 energy events (oil crash Apr 2020, European gas crisis Aug 2022)
- 2 geopolitical events (Russia-Ukraine invasion Feb 2022, US-China tariffs Sep 2019)
- 2 natural disaster events (Texas freeze Feb 2021, Hurricane Ida Aug 2021 — note: `2021_08_hurricane_ida.json` already exists; check for duplicates)
- 2 industry-specific events (chip shortage peak 2021, EV battery crunch 2022)
Each event file must follow the exact JSON schema used in `data/events/2021_03_suez_canal.json`.

**Priority 3 — Ground truth expansion to 400 labels**
Run `scripts/extract_ground_truth.py` on the 10 new events × 20 companies. Adds ~200 new rows to `data/ground_truth/labels_v1.jsonl`. Review output with `scripts/validate_labels.py` before committing.

**Priority 4 — Scoring integration test**
Create `tests/test_scoring_integration.py`. Load `labels_v1.jsonl`. Create a dummy `predict_fn` that returns the ground truth action verbatim and confirm fidelity score is >0.90 (sanity check). Create a `predict_fn` that returns random text and confirm score is <0.30.

**Priority 5 — Leaderboard seeding**
Run the benchmark against mimic core and record the first official entry: `scorer: "mimic-framework v0.1.0 (LLM only, no forecast models)"`. Commit result to `data/leaderboard.json`.

**Priority 6 — PyPI publish**
Package name: `mimic-bench`. After fixing the build backend: `python -m build && twine upload dist/*`.

---

## How to Run (Developer Quick Reference)

```bash
cd ~/Desktop/mimic/mimic-bench
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v          # run tests (after tests/ is created)
pip install -e ".[dev]"   # reinstall after changes
```

---

## Known Issues

- **Build backend broken:** `pyproject.toml` uses `"setuptools.backends.legacy:build"` which is incompatible with pip <23.1. Change to `"setuptools.build_meta"` to fix.
- **No tests directory:** `tests/` does not exist. CI will fail with `ERROR: not found: /path/to/tests/` until tests are added.
- **No `data/leaderboard.json`:** `leaderboard.py` will raise `FileNotFoundError` on `display()` until seeded.

---

## Dependencies on Other Mimic Repos

Optional — `mimic_bench/benchmark.py` accepts a `Twin` object from `mimic-framework` (via `bench.run(twin=...)`), but this dependency is duck-typed; the package does not hard-import `mimic`. The extraction pipeline imports `anthropic` directly rather than routing through mimic's orchestrator.
