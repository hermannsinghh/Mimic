# MIMIC 2.0 — Build Plan

**Audience:** Claude Code (and any agent operating the Mimic repos). This document is the single source of truth. When in conflict with anything else, this wins.

**Mode:** Strategy 3 — *Dual Track, vertical-tilted*. Open-source SDK + Mimic Hub marketplace, monetized via managed reinsurance treaty product.

**Time horizon:** 0–18 months. 30/90/180-day acceptance criteria at the bottom of every section.

---

## 0. North Star

> **Mimic is the composable, audit-grade stress-testing SDK for any financial institution — with reinsurance treaty pricing as the lighthouse vertical.**

Three non-negotiable invariants every commit must respect:

1. **Auditability** — every simulation run produces a `world_state_hash` and a signed event log replayable from inputs.
2. **Composability** — every capability is a Python module callable from a Temporal workflow; no monolithic CLI assumptions.
3. **Schema-canonical** — entities, instruments, events, decisions, outcomes are FIBO/ACORD/ISO 20022/FpML-IRI-addressable before they touch any solver.

Anti-goals (do not build, do not accept PRs for):

- A web UI no-code workflow builder (we are SDK-first; UI is a separate product later).
- A new ontology (use FIBO; write translators only).
- Crypto tokens, on-chain marketplaces, blockchain replay (kills regulated-buyer trust).
- Reproductions of Aladdin/RMS/Verisk integrations (avoid Aladdin-land for 18 months).

---

## 1. Repo & Package Layout

### 1.1 Collapse 6 packages → 3 + 1 hub

**Before (current, v0.1.x):** mimic-forecast, mimic-world, mimic-signal, mimic-sim, mimic-bench, mimic-framework.

**After (target, v0.2.0):**

```
mimic/                          # monorepo (uv workspaces)
├── packages/
│   ├── mimic-framework/        # top-level: scenario spec, schema, runtime glue
│   │   └── (absorbs mimic-sim, mimic-signal, mimic-bench as internal modules)
│   ├── mimic-forecast/         # KEEP standalone — frontier TS models
│   └── mimic-world/            # KEEP standalone — contagion graph math
├── hub/                        # Mimic Hub: scenario registry service
├── scenarios/                  # First-party reference scenarios
├── eval/                       # Calibration harness against historical episodes
├── infra/                      # Terraform / Pulumi
└── docs/                       # Docusaurus / MkDocs site
```

Internal modules (`sim`, `signal`, `bench`) remain importable as `mimic.framework.sim` etc.

### 1.2 Internal module map inside `mimic-framework`

```
mimic/framework/
├── scenario/      # Scenario spec parser, OCI artifact pack/unpack, signing
├── schema/        # FIBO/ACORD/ISO 20022/FpML translators + canonical Decision/Outcome
├── workflow/      # Temporal workflow definitions + activities
├── agents/        # Concordia fork glue + LangGraph reasoning nodes
├── routing/       # RouteLLM-style tier cascade
├── determinism/   # Seed manifests, world_state_hash, frozen-run cache
├── sim/           # Monte Carlo orchestration
├── signal/        # Event extraction pipeline
├── bench/         # GIFT-Eval / Chronos-ZS / AgentDojo wrappers + calibration
└── policy/        # OPA/Cedar policy decision point
```

### 1.3 License

- `mimic-framework`, `mimic-world`, `mimic-forecast` core: **BSL 1.1**, 3-year Apache-2.0 conversion, non-production + ≤$1M revenue internal use carve-out.
- `scenarios/`, `docs/`, examples: **MIT**.
- Mimic Hub server (`hub/`): **AGPL-3.0**.
- Hub-client SDK: **Apache-2.0**.

CI must fail if any package is published without LICENSE, LICENSE-BSL, LICENSE-CHANGE-DATE, NOTICE.

---

## 2. Architecture

```
HUB (FastAPI + Postgres + OCI + Sigstore + SLSA)
  ↓ oras pull, signed manifest
SDK: mimic-framework ↔ mimic-forecast ↔ mimic-world
  ↓ scenario.run()
REASONING (LangGraph 1.x, Concordia fork, BAML)
  ↔ ORCHESTRATION (Temporal: workflows=runs, activities=LLM/fetch/MC)
ROUTING (RouteLLM cascade): T1 Opus 4.5 / T2 Sonnet 4.5 / T3 DeepSeek V3.2 / Adj Grok 4
COMPUTE: Modal (preferred) or Ray Serve, Postgres + S3
SCHEMA: FIBO 2025-Q3 / ACORD / ISO 20022 / FpML → canonical Decision/Outcome
INGEST: SEC EDGAR, AM Best, LSEG, Bloomberg, AIS, ratings, FRED, Lloyd's
```

---

## 3. Module-by-Module Build Order

### 3.1 `mimic-framework` (P0 → P1)

| ID | Task | PRI | TARGET |
|---|---|---|---|
| F-01 | Scenario spec parser; FIBO IRI validation | P0 | 0.2.0 |
| F-02 | OCI artifact pack/unpack via `oras-py` | P0 | 0.2.0 |
| F-03 | Sigstore/cosign signing + verification | P0 | 0.2.0 |
| F-04 | Canonical Decision/Outcome Pydantic models | P0 | 0.2.0 |
| F-05 | Temporal `ScenarioRunWorkflow` + activities | P0 | 0.2.0 |
| F-06 | RouteLLM-style tier cascade | P0 | 0.2.0 |
| F-07 | Seed manifest + `world_state_hash` Merkle-DAG | P0 | 0.2.0 |
| F-08 | Frozen-run cache (S3, content-hash-keyed) | P1 | 0.2.1 |
| F-09 | OPA policy decision point wrapper | P1 | 0.2.1 |
| F-10 | Signal: two-stage retriever→reranker→adjudicator | P1 | 0.3.0 |
| F-11 | Bench: GIFT-Eval, Chronos-ZS, AgentDojo + calibration | P1 | 0.3.0 |
| F-12 | Concordia fork integration | P0 | 0.2.0 |

### 3.2 `mimic-forecast`

| ID | Task | PRI | TARGET |
|---|---|---|---|
| FC-01 | Toto 2.0 adapter | P0 | 0.2.0 |
| FC-02 | Timer-S1 adapter | P0 | 0.2.0 |
| FC-03 | TiRex adapter | P1 | 0.2.0 |
| FC-04 | Keep existing (Chronos, FinBERT, Kronos, Moirai, TimesFM 2.5, Bistro) | P0 | 0.2.0 |
| FC-05 | Bench harness; signed badge | P0 | 0.2.0 |
| FC-06 | Per-node probabilistic forecast API | P0 | 0.2.0 |

### 3.3 `mimic-world`

| ID | Task | PRI | TARGET |
|---|---|---|---|
| W-01 | Eisenberg-Noe clearing vector | P0 | 0.2.0 |
| W-02 | DebtRank with provable convergence | P0 | 0.2.0 |
| W-03 | Demote `cascade.py` to `mimic.world.narrative` | P0 | 0.2.0 |
| W-04 | FIBO-shaped network builder → liability matrix | P0 | 0.2.0 |
| W-05 | Combined EN + DebtRank + persona overlay | P1 | 0.2.1 |
| W-06 | Treaty math: chainladder, gemact, rippy, lifelib | P1 | 0.3.0 |

### 3.4 `hub/`

| ID | Task | PRI | TARGET |
|---|---|---|---|
| H-01 | FastAPI: /publish, /search, /scenarios/{id}, /badges/{id} | P0 | 0.2.0 |
| H-02 | OCI artifact backend (Harbor / GHCR via oras) | P0 | 0.2.0 |
| H-03 | Sigstore Fulcio + Rekor | P0 | 0.2.0 |
| H-04 | SLSA Level 3 provenance | P1 | 0.2.1 |
| H-05 | Eval-badge service | P1 | 0.2.1 |
| H-06 | "Verified Publisher" + SOC 2 attestation upload | P2 | 0.3.0 |
| H-07 | Revenue-share metering (70/30) | P2 | 0.4.0 |

---

## 4. Connectors

### 4.1 Data (tiered MVP → 6 month)

**T0 (MVP):** SEC EDGAR, FRED.

**T1 (month 1–3):** AM Best, LSEG (Refinitiv), Bloomberg BLPAPI, NOAA, AIS (Spire/MarineTraffic), news (GDELT/RavenPack), OpenSanctions.

**T2 (month 3–6):** Lloyd's RDS, NAIC SERFF, ACORD message feeds.

Each connector implements `fetch`, `schema`, `health`, `rate_limit_policy`. Tests use VCR fixtures.

### 4.2 Model providers

| Provider | Model | Tier | Cost in/out $/M |
|---|---|---|---|
| Anthropic | Claude Opus 4.5 | T1 | 5 / 25 |
| Anthropic | Claude Sonnet 4.5 | T2 | 3 / 15 |
| Google | Gemini 3 Pro | T2 | 2 / 12 |
| xAI | Grok 4 | T1 (adj) | 3 / 15 |
| OpenAI | GPT-5.1 | T2 | 1.25 / 10 |
| DeepSeek | V3.2 | T3 | 0.28 / 0.42 |

Adapter exposes `complete(messages, schema, tools, temperature, seed) -> StructuredResponse` and emits `model_fingerprint = sha256(provider|model|version|system_prompt|temperature|tool_schema)` per call.

### 4.3 Infra

Temporal Cloud (durable workflows), Modal (GPU/CPU burst), Ray Serve (alternative), Harbor or GHCR (OCI), Sigstore (Fulcio + Rekor), Postgres, S3 / R2, OpenTelemetry → Tempo/Honeycomb.

---

## 5. Schema Layer

### 5.1 Canonical models (live in `mimic/framework/schema/decision.py`)

`RationaleStep`, `Decision`, `Outcome` — see file. Decision has decision_id (ULID), agent_did, instrument_iri (FIBO), action_type (hedge|raise_capital|cut_exposure|lobby|hold|sell|buy|reinsure|cede|retain), quantity, unit (ISO 4217 or FIBO unit IRI), rationale_chain, timestamp, model_fingerprint, confidence, policy_version.

### 5.2 Translators

`schema/translate/{fibo,acord,iso20022,fpml}_to_internal.py`. Each exposes `to_canonical`, `to_native`. Round-trip tests must be bit-equivalent on the round-trip-stable subset.

### 5.3 FIBO release pinning

`[tool.mimic] fibo-version = "2025-Q3"` in pyproject.toml. CI job `fibo-bump.yml` opens PRs quarterly. Never auto-merge.

---

## 6. Tiered Model Routing

### 6.1 Deterministic tier criteria

```python
def assign_tier(entity) -> Literal["T1","T2","T3"]:
    if entity.systemic_score >= SYSTEMIC_T1_THRESHOLD: return "T1"
    if entity.systemic_score >= SYSTEMIC_T2_THRESHOLD: return "T2"
    return "T3"
```

`systemic_score` from FSB G-SIB, IAIS IAIG, SEC 13F AUM, NAIC P&C premium. Formula change = semver minor bump.

### 6.2 Cascade with confidence escalation

- T3 confidence < 0.6 → escalate T2
- T2 disagreement (cosine < 0.7) → adjudicate T1
- T1 final

Every workflow has `max_cost_usd`. Routing layer refuses to exceed — raises `BudgetExceeded` Temporal failure overridable via signal.

### 6.3 Telemetry

Each routed call emits OTEL span `mimic.route` with {tier, provider, model, input_tokens, output_tokens, cost_usd, confidence, escalated_to}.

---

## 7. Determinism, Audit, Replay

### 7.1 SeedManifest

HKDF-SHA256 derivation. Per-shard seed = HKDF(global_seed, info=f"shard/{shard_idx}"). Per-agent seed = HKDF(global_seed, info=f"agent/{agent_did}").

### 7.2 `world_state_hash` Merkle-DAG

```
root = sha256(
  hash(entity_graph_state) ||
  hash(agent_memory_state) ||
  hash(market_state) ||
  hash(time_step)
)
```

Each component is a sorted, canonical-JSON-serialized Merkle tree. Golden vectors in `tests/determinism/golden/`. Any change → schema major bump + vector refresh.

### 7.3 Frozen-run mode

`MIMIC_FROZEN_RUN=1` → LLM adapter checks S3 cache by `model_fingerprint + sha256(messages)`. Cache miss raises `FrozenRunCacheMiss`. Never silently re-call. **Only audit-grade reproducibility path for closed-provider LLMs.**

### 7.4 GPU determinism

Base image `mimic/runtime:gpu` pins: CUDA 12.4, cuDNN 9.x, PyTorch 2.5.x deterministic mode, BFloat16 forced, FP16 forbidden without explicit flag, vLLM batch-invariant. Outside this image, `check_env()` refuses to emit world_state_hash.

---

## 8. Workflows (Temporal)

### 8.1 `ScenarioRunWorkflow` (orchestration spine)

1. Resolve & verify signed scenario artifact
2. Ingest data (parallel fan-out per source)
3. Seed personas (T1 & T2 only; T3 sector-sampled)
4. Phase 1: Strategic decision phase (agent reasoning)
5. Phase 2: Monte Carlo over uncertainty (sharded)
6. Contagion propagation (EN + DebtRank)
7. Phase 3 (optional): re-loop
8. Emit signed run manifest

### 8.2 Child workflows

`SeedPersonasWorkflow`, `DecisionPhaseWorkflow`, `MCWorkflow`.

### 8.3 Versioning

Use Temporal `workflow.patched()`. Never edit a deployed workflow's deterministic path; add a patch branch.

---

## 9. Agent Reasoning

### 9.1 Concordia fork

Vendor DeepMind Concordia v2.0 as `mimic-concordia/`. We own the fork. Patches the callback API to emit `Decision` (per §5.1), not free text.

### 9.2 Domain prefabs

| Prefab | Tier | Output |
|---|---|---|
| ReinsurerTreatyPricer | T1 | Bid/no-bid + price + retention |
| BankTreasuryALM | T1 | Liquidity actions |
| HedgeFundRiskOfficer | T2 | Position trims, hedges |
| CentralBankLiquidityProvider | T1 | Facility opening, rate decision |
| RatingAgencyAnalyst | T2 | Watch/downgrade/no-action |
| BrokerCedentAdvisor | T2 | Recommended placement |

Each is Concordia agent + LangGraph reasoning + BAML schema in `agents/baml/`.

### 9.3 Calibration

A prefab without a published calibration badge MUST NOT ship to Hub.

---

## 10. Scenario Spec

### 10.1 Layout — see scenarios/CLAUDE.md and `.claude/skills/mimic-scenario-author.md`.

### 10.2 Canonical scenario.yaml — see svb-replay-2023/scenario.yaml as reference.

### 10.3 First-party scenarios — already scaffolded in scenarios/:

- taiwan-strait-30d-closure (reinsurer)
- svb-replay-2023 (mid-banks)
- uk-gilt-ldi-2022 (UK pension / BoE)
- covid-dash-for-cash-2020 (central bank)
- 2008-gfc-bank-cascade (G-SIB / regulator)
- cyber-cat-2026 (reinsurer / cyber syndicate)
- eu-ai-act-model-risk-2026 (EU life/health insurer)

---

## 11. Calibration / Eval Harness

### 11.1 Historical episode benchmark

Dataset `mimic-ai/historical-episodes-v1` on HF Hub. Metrics: directional accuracy, CRPS, decision realism (Wasserstein), cost.

### 11.2 Forecasting bench

GIFT-Eval, Chronos-ZS, BOOM. Signed badge per release. Regressions block merge.

### 11.3 Agent bench

AgentDojo (prompt injection), Inspect (UK AISI), Concordia Contest (NeurIPS 2024).

---

## 12. Policy Engine

OPA bundle in `policy/opa/`. Wraps every agent action and data egress. Bundle is signed (cosign), pulled at workflow start, version recorded in `Decision.policy_version`. Run is NOT audit-grade unless every decision has a verified policy_version.

---

## 13. CI/CD

### 13.1 Required workflows

| Workflow | Trigger | Must pass |
|---|---|---|
| test.yml | PR | unit + integration; coverage ≥80% on framework/forecast/world |
| bench.yml | PR + nightly | forecast bench, agent bench, calibration replay |
| license.yml | PR | LICENSE + NOTICE + LICENSE-BSL + LICENSE-CHANGE-DATE present; no GPL deps in BSL |
| determinism.yml | PR | golden vectors match |
| release.yml | tag | wheel + OCI image + cosign + SLSA |
| fibo-bump.yml | quarterly cron | opens PR on FIBO release |
| sbom.yml | release | CycloneDX SBOM in release assets |

### 13.2 Release cadence

Framework/forecast/world minor every 6 weeks, patch on demand. Hub continuous deploy. Scenarios independent.

### 13.3 SemVer policy

- **Major:** canonical schema change, world_state_hash change, scenario spec change.
- **Minor:** new adapters, new prefabs, new connectors.
- **Patch:** bugfixes, perf, docs.

---

## 14. Documentation & Skills

### 14.1 Docs site — see docs/README.md.

### 14.2 Claude Code skills in `.claude/skills/`

- mimic-scenario-author.md
- mimic-connector-author.md
- mimic-prefab-author.md
- mimic-determinism-check.md
- mimic-release.md
- mimic-schema-bump.md

Before any task matching a skill, the relevant skill file MUST be read first.

---

## 15. Go-to-Market

- **Month 0–3:** 1 lighthouse reinsurer running taiwan-strait-30d-closure end-to-end. Hub private alpha (single tenant). SOC 2 Type I evidence starts month 1.
- **Month 3–6:** Public Hub launch (read-only). Show HN. Calibration on 2008 GFC + 2023 SVB on HF Hub. 2 more reinsurers + 1 mid-bank + 5 HF early access.
- **Month 6–12:** SOC 2 Type II. Paid scenario tier opens. First central-bank ref customer (free perpetual). EU AI Act Article 13 logging.
- **Month 12–18:** 12 paying logos. Series A. 200+ scenarios on Hub. Verified Publisher SOC 2-attested badge live.

---

## 16. Acceptance Criteria

### Day 30
- [ ] Monorepo restructured; CI green.
- [ ] BSL + change-date in every package; `license.yml` passing.
- [ ] scenario.yaml v1 finalized; svb-replay-2023 parses + validates.
- [ ] EN clearing vector in mimic-world; golden tests pass.
- [ ] Toto 2.0 adapter in mimic-forecast.
- [ ] Concordia forked & integrated as `mimic.framework.agents.concordia_runtime`.
- [ ] Temporal `ScenarioRunWorkflow` runs svb-replay-2023 e2e on laptop.
- [ ] `world_state_hash` reproducible across two consecutive runs (frozen mode).

### Day 90
- [ ] All P0 tasks complete (F-01..F-07, F-12, FC-01..FC-06, W-01..W-04, H-01..H-03).
- [ ] Routing T1/T2/T3 cascade live; cost guardrail tested.
- [ ] 5 prefabs shipped with calibration badge ≥0.7 directional accuracy.
- [ ] Hub private alpha live; 1 reinsurer pulling signed scenarios.
- [ ] docs.mimic.ai with quickstart.
- [ ] SOC 2 Type I evidence ≥80% complete.

### Day 180
- [ ] All P1 tasks complete.
- [ ] Public Hub launched.
- [ ] All 7 first-party scenarios published with badges.
- [ ] Forecasting bench: ≥1 Mimic adapter on GIFT-Eval podium.
- [ ] 3 paying logos.
- [ ] SOC 2 Type II in audit.
- [ ] ARR ≥ $500K.

---

## 17. Risks

1. LLM pricing volatility — rebuild routing quarterly.
2. LLM determinism is best-effort — frozen-run cache is the only audit-grade path.
3. EU AI Act timeline — fallback to PRA SS1/23 if Digital Omnibus delays.
4. Concordia governance — we own the fork.
5. Aaru competition — moat is decision + contagion + audit-grade, not personas alone.
6. Aladdin embedding agents — stay out 18 months.
7. OSS conversion timing — measure paying logos, not stars.
8. Strategy 3 needs infra + enterprise DNA both — fallback to Strategy 1 if not hireable by month 12.
9. Schema drift — round-trip tests are the early-warning.
10. BSL pushback — public FAQ ready; Apache conversion at year 3 non-negotiable.

---

## 18. How Claude Code Should Use This Document

1. Read top-to-bottom before any architecture-affecting change.
2. Section 3 is the build queue — pick by PRI then ID.
3. Section 5 is the schema contract — never change without major bump.
4. Section 7 is the determinism contract — never change without golden refresh + major bump.
5. Section 13 is the CI contract — never disable a required workflow.
6. Section 14.2 lists the skills — read the relevant skill before any matching task.
7. Section 16 is the milestone gate — write status report at day 30/90/180 to `docs/status/<date>.md`.
8. When in doubt — open a `decision-record/` ADR.

---

*End of plan. Version 1.0. Next review: at day-30 milestone (2026-06-20).*
