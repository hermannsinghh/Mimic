---
name: mimic-determinism-check
description: Review a PR for determinism violations — golden hash drift, missing seeds, frozen-run holes
---

# Reviewing a Mimic PR for determinism

Read this before approving any PR that touches `mimic.framework.determinism`,
`mimic.framework.schema`, `mimic.framework.routing.LLMProvider`, or `tests/determinism/golden/`.

Contract: Plan §7. The three audit-grade guarantees are:

1. **Same inputs + same seed = same `world_state_hash`** across re-runs.
2. **LLM responses are recorded** when `MIMIC_FROZEN_RUN=1` and replayed by content hash.
3. **Hash computation is versioned** — any change forces a schema major bump.

## Review checklist

### Schema / hash drift
- [ ] If `mimic/framework/schema/decision.py` changed: was the schema major version bumped?
- [ ] If `tests/determinism/golden/*.json` changed: is there a matching schema major bump and
      a `decision-record/` ADR explaining the change?
- [ ] If `world_state_hash` computation changed in any way: same answer.

### Seeds
- [ ] Every new Monte Carlo entry point accepts a `SeedManifest` or inherits one. Nothing seeds
      from `random.seed()` or `os.urandom()` outside `SeedManifest`.
- [ ] Per-shard and per-agent seeds derived via HKDF-SHA256 from `global_seed`. Not via `+ shard_idx`.

### LLM determinism
- [ ] Every LLM call goes through `mimic.framework.routing.LLMProvider`.
- [ ] Provider adapter emits `model_fingerprint` on every call.
- [ ] In `MIMIC_FROZEN_RUN=1` mode, cache miss raises `FrozenRunCacheMiss`. The PR must not
      add a silent re-call path.

### GPU determinism
- [ ] PyTorch code calls `torch.use_deterministic_algorithms(True)`.
- [ ] vLLM runs in batch-invariant mode.
- [ ] BFloat16 forced; FP16 only behind an explicit opt-in flag.
- [ ] If running outside the pinned `mimic/runtime:gpu` image,
      `mimic.framework.determinism.check_env()` is called and refuses to produce a
      `world_state_hash`.

## Red flags that block merge

- Any change to hash computation without a major version bump.
- A new caller of `time.time()`, `datetime.now()`, or `uuid4()` in a workflow's deterministic
  path. Use Temporal's `workflow.now()` and seed-derived IDs.
- A test that compares hashes with `==` but is marked `@pytest.mark.skip` "because flaky."
- A new LLM call that bypasses the routing layer.
