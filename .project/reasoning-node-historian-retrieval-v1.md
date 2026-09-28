# Reasoning Node historian retrieval v1 ownership

## Live repository anchor

- repository: anthonyedgar30000/linealert-core
- base branch: main
- initial base merge: PR #145, Add deterministic Reasoning Node context bundle
- final rebased main: 1f046d14ba68fdea134c35f7e344041264e30279
- intervening merge: PR #146, Add synthetic lab clock telemetry adapter
- PR #146 changed-file overlap with this increment: none
- open pull requests observed at final rebase check: none
- active branch for this increment: agent/reasoning-historian-retrieval-v1

Live GitHub supersedes cached coordination snapshots.

## Equipment and deployment boundary

Repository coordination state reports production runtime deployment, physical equipment
connection, and equipment-control paths as not observed.

Available equipment material remains synthetic/demo material. No Labeler 2 OEM manual or
commissioned machine package was observed.

This increment therefore has no authority to claim physical machine truth or production readiness.

## Owned scope

The increment owns:

- src/linealert_core/reasoning_historian.py
- tests/test_reasoning_historian.py
- docs/architecture/reasoning-node-historian-retrieval-v1.md
- .project/reasoning-node-historian-retrieval-v1.md

It does not own existing historian write paths, clock logic, diagnostic logic, topology authority,
equipment control, or production deployment.

## Acceptance gates

1. database session must verify default_transaction_read_only=on;
2. no DDL or data-changing SQL is exposed by the adapter;
3. exact asset scope is mandatory;
4. optional relationship/episode/cycle/phase/time filters are parameterized;
5. query time bounds must be timezone-aware;
6. truncation fails closed with no candidates;
7. bad-quality records are not promoted;
8. retained evidence authority must exist and match exact expected config identity;
9. source/config/record provenance is preserved;
10. retained clock evidence is copied without reinterpretation;
11. recorded configuration version is preserved for the #145 context gate;
12. retrieval grants no diagnosis or action authority;
13. focused tests, full tests, Ruff, scoped MyPy, and diff checks pass on exact branch head.

## Rollback

Delete or revert this increment. It adds no schema migration, writer, service listener, model
runtime, equipment connection, or control path.
