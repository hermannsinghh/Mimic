# svb-replay-2023

Calibration benchmark: Silicon Valley Bank deposit run, 2023-03-08 → 2023-03-13.

Lighthouse buyer: mid-size US regional banks.

## Why this scenario

It is one of the few recent episodes with a fully-public timeline (Twitter ledger, deposit
flow disclosures, FDIC receivership report) that we can replay deterministically and score.
A model that fails to predict the directional sign of the deposit outflow on this scenario is
not audit-grade for any bank-run analysis.

## Status

- [ ] `inputs.schema.json` — FIBO bank entities + deposit liability instruments
- [ ] `workflow.py` — runs ScenarioRunWorkflow with deposit-run event
- [ ] `eval/historical/` — actual deposit flow, share price, regulator action timeline
- [ ] `seeds/manifest.yaml`
- [ ] `data_refs.lock`
