# Reasoning Node live Timescale acceptance v1 ownership

## Repository anchor

- repository: anthonyedgar30000/linealert-core
- base branch: main
- initial implementation base: 720d0ea1c4252141b98529385dbd149d65f843aa
- final rebased main: 5b719850bcb30e166ef6501c326d1475bcbbd0be
- intervening merge: PR #149, Require synthetic step-monitor coverage for clock projection
- changed-file overlap with PR #149: none
- open pull requests at final rebase check: none
- branch: agent/reasoning-live-timescale-acceptance-v1

Live GitHub supersedes this coordination record if repository state advances.

## Owned paths

- src/linealert_core/reasoning_historian_acceptance.py
- tests/test_reasoning_historian_acceptance.py
- docs/architecture/reasoning-node-live-timescale-acceptance-v1.md
- docs/acceptance/2026-09-28-reasoning-node-timescale-acceptance.md
- .project/reasoning-node-live-timescale-acceptance-v1.md
- pyproject.toml only for the acceptance CLI entrypoint

## Explicit non-ownership

This increment does not own or change:

- clock-evidence semantics;
- clock step detection or monitoring;
- historian write paths;
- database schema;
- production deployment;
- topology authority;
- diagnostic rules;
- maintenance or control authority;
- physical equipment integration.

## Live acceptance boundary

The acceptance uses the preserved local development Timescale volume only. It does not seed new
evidence or interpret the retained synthetic records as physical machine truth.

The preserved dataset lacks operating_context.configuration_version, so current configuration
applicability remains UNASSESSED.

## Acceptance gates

1. verified database read-only session;
2. no truncation;
3. no retrieval refusals;
4. exact expected candidate count;
5. unique evidence identity;
6. exact source binding and retained historian authority;
7. exact configuration-file provenance;
8. retained clock evidence copied without interpretation;
9. deterministic reasoning-context bundle;
10. no model invocation;
11. no diagnosis or action authority;
12. focused tests, full tests, Ruff, scoped MyPy, and diff checks pass;
13. live exact-head acceptance passes against the preserved Timescale volume;
14. runtime is returned to a bounded stopped state after final verification.

## Rollback

Revert or delete this increment. The code introduces no schema migration, data writer, model
runtime, equipment listener, or equipment-control path.
