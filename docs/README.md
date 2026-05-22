# Mimic Documentation

Docusaurus or MkDocs site. **MIT-licensed.**

## Required sections at launch (Plan §14.1)

- Quickstart (5-minute scenario run)
- Architecture (slimmed user-facing version of PLAN.md)
- Scenario authoring guide → see `.claude/skills/mimic-scenario-author.md`
- Connector authoring guide → see `.claude/skills/mimic-connector-author.md`
- Prefab authoring guide → see `.claude/skills/mimic-prefab-author.md`
- Determinism & audit guide (for regulator-facing buyers)
- API reference (auto-gen from docstrings)
- Hub publishing guide
- Migration guide v0.1 → v0.2 (the package consolidation)

## Status reports

At day 30 / 90 / 180 from project kickoff (2026-05-21), write a milestone status report to
`docs/status/<date>.md` against the checklists in Plan §16.

## Site layout

```
docs/
├── architecture/    # System diagrams, sequence diagrams
├── guides/          # Authoring guides (mirror of skills, written for humans)
├── api/             # Auto-generated API ref
├── connectors/      # One page per data connector
├── migration/       # Version-bump migration guides
├── schema/          # FIBO/ACORD/ISO 20022/FpML version notes
└── status/          # Milestone status reports
```
