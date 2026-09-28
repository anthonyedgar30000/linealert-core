# Reasoning Node context bundle v1 work ownership

## Repository reality at branch creation

- repository: anthonyedgar30000/linealert-core
- base branch: main
- base commit: 75fb156d6dd811ceb85e2f4beef061c1865de7c4
- latest merged PR at branch creation: #143, Add live Timescale acceptance harness
- open pull requests observed before branch creation: none
- production equipment connection: not established by this work
- equipment-control authority: not granted

Live GitHub remains authoritative over this coordination record.

## Owned increment

- branch: agent/reasoning-context-bundle-v1
- objective: create the first deterministic, provenance-preserving context package for a local
  LineAlert Reasoning Node
- implementation authority: repository software and documentation only
- runtime authority: local/offline context assembly only
- model authority: none
- equipment authority: none

## Permitted paths

- src/linealert_core/reasoning_context.py
- tests/test_reasoning_context.py
- docs/architecture/reasoning-node-context-bundle-v1.md
- .project/reasoning-node-context-bundle-v1.md

No existing timing, clock, historian, diagnostic, topology, or equipment-control implementation
file is owned by this increment.

## Explicit non-overlap

The separate time-integrity workstream owns clock quality, offset, drift, uncertainty, temporal
admissibility, and timestamp interpretation.

This increment may preserve clock evidence supplied inside retrieved records, but it must not
calculate, reclassify, correct, or reinterpret that evidence.

## Acceptance gates

The increment is acceptable only if:

1. exact asset scope is enforced;
2. invalidated and superseded evidence fail closed;
3. source-evidence roles require verified source binding and declared source authority;
4. missing or mismatched current configuration identity fails closed for current evidence;
5. historical configuration mismatch cannot masquerade as current evidence;
6. semantic retrieval is context-only;
7. generated summaries and analytical findings are context-only;
8. conflicting duplicate evidence identity fails closed;
9. bundle output is deterministic across candidate input order;
10. source content is preserved rather than rewritten;
11. no model is invoked;
12. no action or diagnosis authority is granted;
13. focused tests, full tests, lint, and type checks pass on the exact branch head.

## Rollback

Delete the branch or revert the resulting merge. The increment creates no database migration,
service listener, model runtime, external index, equipment connection, or equipment-control path.
