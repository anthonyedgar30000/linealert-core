# Live emulated historian v1

Repository: anthonyedgar30000/linealert-core
Base: main@a39007ab09ec1be4ff7fb051e524ae7bc2833227
Branch: agent/live-emulated-historian-v1

## Objective

Provide continuously changing, retained, realistic synthetic historian-shaped
evidence to the existing Reasoning Inputs surface without requiring Docker or
TimescaleDB.

The mode must remain explicit and must never silently substitute emulated data
for unavailable plant or Timescale history.

## Permitted paths

- src/linealert_core/historian_emulator.py
- src/linealert_core/historian_emulator_service.py
- pyproject.toml
- scripts/start-hybrid.ps1
- ui/app/reasoning/page.tsx
- tests/test_historian_emulator.py
- tests/test_reasoning_inputs_emulation.py
- tests/test_project_state.py
- README.md
- docs/architecture/live-emulated-historian-v1.md
- .project/active-work.json
- .project/live-emulated-historian-v1.md

## Runtime scope

- explicit launcher switch: -UseEmulatedHistorian
- loopback-only service: 127.0.0.1:8767
- browser/laptop access remains through Next.js :8766
- default local SQLite:
  %LOCALAPPDATA%\LineAlert\historian-emulator-v1\historian.sqlite3
- no Docker dependency
- no automatic fallback from TimescaleDB to emulation

## Deterministic scenario

One 48-cycle scenario repeats:

1. stable_reference
2. incipient_presentation_drift
3. persistent_presentation_drift
4. bounded_diagnostic_observation
5. post_intervention_observation

Primary changed relationship:
LabelFeedCommand -> LabelAtPeelPoint

Primary held relationship:
BottleDetected -> SpacingConfirmed

No random values are used.

## Evidence preservation

Generated records retain:

- source identity
- asset/component identity
- timestamps
- episode/cycle identity
- clock model/quality basis
- engineering units
- expected min/max envelope
- profile / operating mode
- configuration version
- firmware version
- calibration identity
- sampling profile
- recipe/product identity
- exact config SHA-256
- scenario phase
- evidence IDs
- reason code / state

## Persistence

SQLite:
- WAL
- synchronous=FULL
- bounded cycle retention
- one local transaction per generated cycle
- restart continuation through persisted next sequence

This is local emulator consistency only.

## Failure behavior

Retained-store connectivity and live source availability are separate.

If generation fails:
- retained history remains queryable when SQLite remains healthy
- source_available becomes false
- reason_code becomes EVIDENCE.EMULATED_HISTORIAN_SOURCE_UNAVAILABLE
- no replacement cycle is invented

If the service is absent, existing Next historian routes remain 503 /
fail-closed.

## API boundary

Read-compatible endpoints:
- GET /api/status
- GET /api/history/functional-temporal
- GET /api/history/conditions
- GET /api/history/observations
- GET /api/history/episodes/{episode_id}

HTTP writes are refused.

Still unavailable / fail-closed:
- configured-policy condition localization
- functional/temporal reference-versus-selected comparison

## Canonical boundaries

- emulated_history != plant_history
- emulated_historian != timescaledb
- deterministic_synthetic_pattern != historical_pattern
- synthetic_clock_model != verified_clock_synchronization
- simulated_departure != current_root_cause
- emulated_condition_violation != physical_fault
- post_intervention_scenario != verified_maintenance_action
- successful_emulated_retrieval != explanation_truth
- historian_retrieval != diagnosis
- recommendation != authorized_action

## Verification

Required before publication:

- ruff check .
- pytest
- npm run lint
- npm run build
- start-hybrid.ps1 parse
- direct emulator status 200 with emulated=true
- functional/temporal latest record advances over wall time
- same-origin Next historian status 200
- same-origin Next functional/temporal history 200
- emulator POST write refusal 405
- emulator persistence survives service restart
- 8767 binds loopback only in deployed mode
- no 5433 / Docker dependency for emulated mode
- git diff --check

## Rollback

Revert this increment and stop the loopback emulator on 8767. Existing local
SQLite data may remain as inert synthetic demo data; deleting local user data
is a separate explicit action. The Timescale implementation remains untouched.
