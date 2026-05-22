# Mimic Calibration / Eval Harness

Per Plan §11. Replays scenarios through Mimic and scores against known outcomes.

## Layout

```
eval/
├── harness/         # Python harness — replay, score, emit badge
├── historical/      # Episode datasets (known outcomes)
└── README.md
```

## Metrics (Plan §11.1)

- **Directional accuracy** — sign of net change.
- **Distributional calibration** — CRPS.
- **Decision realism** — Wasserstein distance between simulated and historical CEO action
  distributions.
- **Cost** — USD per full run, $ per firm-simulation.

## Bench targets (Plan §11.2 — forecasting)

- GIFT-Eval (general TS)
- Chronos-ZS (zero-shot)
- BOOM (long-horizon)

## Agent bench (Plan §11.3)

- AgentDojo (prompt-injection robustness)
- Inspect (UK AISI capability evals)
- Concordia Contest (NeurIPS 2024 cooperative-game release)
