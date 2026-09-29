# Reasoning deterministic timestamp rendering v1

Repository: anthonyedgar30000/linealert-core
Base: main@8c0221ba00ca199b8076701188d7a1f10558a280
Branch: agent/reasoning-deterministic-time-v1

## Objective

Eliminate the Reasoning Inputs hydration mismatch caused by locale-dependent
timestamp formatting while preserving the historian record timestamp unchanged.

## Permitted paths

- ui/app/reasoning/reasoning-client.tsx
- tests/test_reasoning_inputs_emulation.py
- tests/test_project_state.py
- docs/architecture/reasoning-deterministic-timestamp-rendering-v1.md
- docs/architecture/reasoning-server-rendered-readiness-v1.md
- README.md
- .project/active-work.json
- .project/reasoning-deterministic-timestamp-rendering-v1.md

## Observed failure

React hydration error on the LAN browser:

- client text: 9/29/2026, 3:49:05 PM
- server text: 2026-09-29, 3:49:05 p.m.

Root cause: Date.toLocaleString() selected different locale representations on
the browser and Next.js server.

## Fix

Valid historian timestamps are normalized for display using toISOString() and
rendered as YYYY-MM-DD HH:MM:SS UTC.

The retained evidence timestamp is not mutated.

## Verification

- no toLocaleString/toLocaleDateString/toLocaleTimeString in reasoning timestamp rendering
- npm run lint
- npm run build
- pytest
- ruff check .
- LAN /reasoning initial HTML still contains live emulation state
- headless Chrome hydrated the LAN page with live emulation and canonical UTC labels
- hydrated DOM contained neither `Hydration failed` nor `Recoverable Error`
- browser hydration no longer reports timestamp text mismatch
- 8767 and 8768 remain loopback-only

## Boundaries

- timestamp_display_normalization != timestamp_source_mutation
- canonical_utc_label != verified_clock_synchronization
- hydration_match != historian_truth
- rendered_timestamp != verified_physical_event_order
- presentation_fix != diagnosis

## Rollback

Revert this UI-only rendering increment. No historian, service-case, or
equipment rollback is required.
