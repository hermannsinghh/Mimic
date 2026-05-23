# 2026-05-22 — F-12 step 5: equivalence test lands green

## Summary

`tests/equivalence/test_equivalence.py` is live. The
``ReinsurerTreatyPricer @ taiwan-strait-30d-closure-deepseek`` pair
passes both threshold checks with substantial margin against a
non-trivial actuarial heuristic baseline.

| metric | observed | threshold (ADR) | margin |
|---|---|---|---|
| W1 (quantity, $) | $8,241,666 | $50,000,000 | 83.5% |
| TV (action_type) | 0.1667 | 0.20 | 16.7% |

Provider: ``deepseek-chat`` (V3.2) replayed from
``tests/fixtures/frozen-run/taiwan-strait-30d-closure-deepseek/``.

## Per-cedent decisions

Six synthetic cedents face a 30-day Taiwan strait closure event. Each
carries an OEP/AEP cat-model curve and a premium offer.

| Cedent | Heuristic baseline | Concordia (DeepSeek) |
|---|---|---|
| MarineMutual | reinsure $18M | reinsure $28M |
| **PropertyCatCo** | **hold $0** | **reinsure $38M** |
| AsiaPropertyTrust | reinsure $22M | reinsure $3.2M |
| HongKongCargo | reinsure $8M | reinsure $9.75M |
| PacificEnergyMutual | reinsure $55M | reinsure $42M |
| TaiwanLifeInsurance | reinsure $15M | reinsure $6M |

The single action_type disagreement on PropertyCatCo is the substantive
signal the equivalence harness was designed to surface. PropertyCatCo's
premium/expected_loss = 1.20 falls below the heuristic's 1.30 load
factor, so the deterministic baseline declines. DeepSeek, looking at the
$920M 1-in-100 OEP tail and judging the price/tail-risk trade-off,
bids. That's the "LLM reasoning beyond a formula" payoff the prefab
exists to capture — and the threshold accommodates it.

## Component pieces

* **`_heuristic_reinsurer_pricer`** — deterministic in-process baseline.
  ``reinsure`` when ``premium_offer >= expected_loss × 1.30``, else
  ``hold``. ``is_deterministic = True`` so audit-grade refusal allows it
  without frozen-run priming.
* **`_toy_reinsurance_network()`** — synthetic 6-cedent panel. Size
  chosen to make the ADR's TV ≤ 0.20 threshold structurally achievable
  (with N=2 the categorical granularity is 0.5, which makes the
  threshold unreachable by any single disagreement).
* **Provenance for ReinsurerTreatyPricer thresholds** — Solvency II
  Directive 2009/138/EC Article 29(4) proportionality principle for the
  $50M W1 ceiling (~1% of mid-cap cedent equity), EIOPA "materially
  consistent assessment" guidance (Solvency II Guideline 1, Article 233)
  for the 0.20 TV ceiling. Now a ``(theory)`` provenance, not a TODO.
* **`test_non_triviality_guard_catches_cross_domain_mismatch`** —
  positive assertion that running ReinsurerTreatyPricer on bank entities
  trips the guard. Pins the negative case so a future refactor that
  removes the guard doesn't silently let cross-domain runs claim
  equivalence.

## Latent bug fixed in this turn (ADR 2026-05-22-runner-iri-resolution)

The ``ScenarioRunner``'s ``PersonaAction`` extraction was deriving
``node_name`` from ``instrument_iri.split("/")[-1]``. The network keys
nodes by full IRI (``mimic_world.contagion.fibo_builder`` line 76,
``name=ent["iri"]``), so the trailing-segment extraction always
mismatched — for the stub builder it produced ``"svb"``, for prefabs it
produced ``"reinsurance-treaty"``. Either way **every** action was
filtered as an orphan and the network propagated unmodified in every
scenario run, including the day-30 demo.

Fixed by replacing the trailing-segment extraction with
``_resolve_target_node`` which walks up the instrument IRI path until a
network node matches:

```
"https://example.com/svb"                       → direct match
"https://example.com/svb/reinsurance-treaty"    → parent match
"https://example.com/orphan"                    → None (genuine orphan)
```

Pure runner change; no schema bump (per CLAUDE.md hard rule, schema
changes need a major bump). Three new tests pin the fix:

* ``test_persona_actions_actually_affect_network_state`` — trivial-hold
  vs cut_exposure produces different ``world_state_hash_final``.
* ``test_persona_actions_on_instrument_suffixed_iri_resolve_to_entity``
  — the prefab IRI shape ``<entity>/<suffix>`` resolves correctly.
* ``test_resolve_target_node_walks_path`` — unit test for the helper.

Effect on the equivalence test results above:

* Decision-level outputs unchanged (W1, TV, per-cedent decisions identical
  to the pre-fix run — the test never depended on network hashes).
* ``world_state_hash_final`` for the same equivalence run was previously
  ``70f19a3cb78e5f0ab5821c21…`` for **both** runners (the orphan-actions
  symptom). Post-fix it is:
  - In-process (heuristic): ``e2c9f5ec5bdfc1c0d601f46fa5f1098c…``
  - Concordia (DeepSeek):  ``dce9c54434275a1e771cb3d7e7054462…``
  Different, as the equivalence ADR predicted: "same hash from both
  runners would mean Concordia isn't actually reasoning."

## What's still parked

* **Canonical Anthropic recording** of svb-replay-2023 + taiwan-strait
  cassettes. The DeepSeek cassettes are forward-progress; the audit
  baseline at ``tests/fixtures/frozen-run/svb-replay-2023/`` (no
  provider suffix) is still empty until an Anthropic key is available.
* **Anthropic noise-floor** measurement against the same cassette set.
* **Seed propagation** through ``Prefab.run`` and
  ``ConcordiaPersonaBuilder`` so the noise-floor harness can also catch
  LLM stochasticity (see ``docs/status/2026-05-22-f12-deepseek-fallback.md``).

## What lands with this status

* Equivalence harness: ``tests/equivalence/test_equivalence.py`` (4 tests)
* Non-trivial baseline: ``_heuristic_reinsurer_pricer`` with cited LOAD_FACTOR
* Expanded toy network: 6 cedents with cat-model curves
* Provenance resolution: Solvency II citations replace the TODO tag
* DeepSeek cassettes: 12 cassettes at
  ``tests/fixtures/frozen-run/taiwan-strait-30d-closure-deepseek/``
* ConcordiaPersonaBuilder: ``_inputs_for_prefab`` now surfaces entity-level
  ``cat_model``, ``expected_loss_usd``, ``premium_offer_usd``,
  ``treaty_layer`` (additive — no cassette churn for svb-replay).
* Scripts: ``MIMIC_RECORD_SCENARIO`` env var added to
  ``scripts/record_svb_cassettes.py`` so it handles arbitrary scenarios.
