# Anthropic model choice for F-12 cassettes: claude-opus-4-7

**Status:** accepted
**Date:** 2026-05-22
**Relates to:** Plan §4.2 (model providers table), F-12 step 3 (cassette
recording), ADR `decision-record/2026-05-22-concordia-vendoring-strategy.md`.
**Forced by:** F-12 step 3 is about to record cassettes against a live
Anthropic model. Plan §4.2 named "Claude Opus 4.5" at T1; that alias is no
longer live in Anthropic's API. The model identifier needs to be locked
*before* recording, because the cassette cache key folds
``model | model_version`` into ``model_fingerprint`` (Plan §4.2). Changing
the model after recording silently invalidates every cassette.

## Context

Plan §4.2's provider table (frozen in plan v1.0, written in March 2026) lists:

    Anthropic | Claude Opus 4.5  | T1 | 5 / 25
    Anthropic | Claude Sonnet 4.5| T2 | 3 / 15

As of 2026-05-22:

- Anthropic's live Opus alias is ``claude-opus-4-7``. ``claude-opus-4-5`` is
  the deprecated alias (still callable for some accounts but not
  guaranteed available indefinitely).
- ``claude-sonnet-4-6`` is the live Sonnet alias.
- Per the user's call on 2026-05-22, F-12 records against the live Opus,
  not the deprecated 4-5 alias.

The plan's reference to "Claude Opus 4.5" was the live model at plan-write
time. Pinning to a deprecated alias for the lighthouse cassettes is the
wrong default — cassettes recorded against a model that may stop being
available in months are not an audit asset.

## Options

A. **Stick to plan §4.2 literally: `claude-opus-4-5`.** Honors the plan's
   text. Risks cassettes against a model that may be retired before F-12
   even lands; also forces every future recording to use the deprecated
   alias.

B. **Use the live alias: `claude-opus-4-7`.** Matches what's actually
   serving Anthropic API today. Cassettes are recorded against a model
   that's currently the default Opus. Diverges from plan §4.2's named
   model.

C. **Use a dated identifier: e.g. `claude-opus-4-7-20260415`.** Hardest
   pin — cassettes are bit-tied to one server-side build. Requires a
   round trip with Anthropic support to discover the dated alias, and
   the dated alias is still subject to retirement.

## Decision

**Option B: `claude-opus-4-7`** as the default model identifier for the
``AnthropicProvider`` and the ``scripts/record_svb_cassettes.py`` script.

Reasoning:

- A keeps a known-deprecated alias in the audit trail. The reproducibility
  guarantee evaporates the day the alias is retired — at that point
  ``ScenarioRunner`` runs against the cassettes still work, but a regulator
  checking "what model produced this Decision?" gets a model identifier
  that Anthropic no longer serves.
- B uses the live default. Anthropic's deprecation policy commits to ~12
  months notice for model aliases, so 4-7's cassettes have at least that
  much shelf life before a forced refresh.
- C is the *better* long-term path — the SBOM job in CI (``sbom.yml``)
  should record the dated identifier alongside the alias whenever it's
  available. Doing C now requires Anthropic-support correspondence the
  recording session shouldn't depend on. Treat C as a follow-up: once the
  first live recording lands, capture the actual ``message.id`` /
  response-side model build identifier in cassette metadata so future
  recordings can pin to it.

## Contract

- ``mimic.framework.routing.anthropic.DEFAULT_MODEL`` is now
  ``"claude-opus-4-7"``.
- ``DEFAULT_MODEL_VERSION`` is ``"2026-04"`` — a placeholder pinning string,
  bumped to a dated identifier the first time the live recording exposes
  Anthropic's internal build tag.
- ``scripts/record_svb_cassettes.py`` defaults to the same. Override via
  ``MIMIC_RECORD_MODEL`` / ``MIMIC_RECORD_MODEL_VERSION``.

## Consequences

- The Plan §4.2 table's "Claude Opus 4.5" row is now out of sync with the
  code's default. Bump-the-plan or accept-the-drift: we accept the drift
  here because the plan is a strategic doc, not the operating manifest.
  When Plan v1.1 ships, §4.2 should be a code-derived table rather than a
  hand-edited markdown one.
- Cassettes recorded against ``claude-opus-4-7`` cannot be replayed against
  ``claude-opus-4-5`` (the model_fingerprint differs). A future Opus
  upgrade triggers a fresh cassette recording pass, just like a system_prompt
  change does — see the "Expect cassette churn" section in
  ``.claude/skills/mimic-prefab-author.md``.
- ``mimic-bench/`` and ``eval/harness/`` benches that compare T1 vs T2 vs T3
  should be updated next to use ``claude-opus-4-7`` and ``claude-sonnet-4-6``
  for the live-API runs. Out of scope for this ADR; record as a follow-up.

## Open items

- Capture Anthropic's response-side ``message.id`` (and any
  ``message.model`` echo) in cassette ``_recording_metadata`` so future
  recordings can pin to the dated identifier.
- Bump Sonnet 4.5 → 4.6 if a T2 cassette set is ever recorded.
- Add a CI fail-fast guard in ``sbom.yml`` that surfaces the (model, alias,
  build-id) triple from each recorded cassette into the release SBOM.
