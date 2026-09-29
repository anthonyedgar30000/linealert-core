# Live emulated historian v1

## Purpose

This increment gives the local LineAlert Reasoning Inputs surface continuously
changing, retained historian-shaped evidence without requiring Docker or
TimescaleDB.

It exists for product development, demonstrations, retrieval testing, and
Speedway service-workflow evaluation when physical plant history is not
available.

It is not a substitute for Timescale acceptance or plant historian evidence.

## Explicit mode

The hybrid launcher adds:

`-UseEmulatedHistorian`

Example:

```powershell
.\scripts\start-hybrid.ps1 -SkipInstall -UseEmulatedHistorian
```

The option is mutually exclusive with `-SkipHistorian`.

The existing no-switch path remains the real TimescaleDB path. This increment
does not silently fall back from TimescaleDB to synthetic data when Docker or
Timescale is unavailable.

## Runtime boundary

The emulator binds only to loopback:

- historian-emulator HTTP service: `127.0.0.1:8767`
- Next.js same-origin historian proxy: `:8766/api/historian/**`
- browser / laptop entry point: `:8766`

A laptop on the local network does not connect directly to port 8767.

The service reports:

- `historian_backend = sqlite_emulator`
- `persistence = sqlite_local_emulated`
- `source_mode = controlled_synthetic_live_emulation`
- `source_classification = controlled_synthetic_demo`
- `emulated = true`
- `physical_state_authority = false`
- `production_authority = false`

## Local retention

The emulator uses Python's built-in SQLite support.

Default Windows database path:

`%LOCALAPPDATA%\LineAlert\historian-emulator-v1\historian.sqlite3`

Repository-local fallback:

`.runtime\historian-emulator-v1\historian.sqlite3`

SQLite is configured with WAL journaling, `synchronous=FULL`, and bounded
cycle retention. One generated cycle commits its observation, condition
measurements, functional/temporal records, and next-sequence marker in one
local SQLite transaction.

This establishes bounded local emulator consistency only.

`sqlite_cycle_transaction != plant_historian_transaction`

## Scenario

The generator is deterministic. No random values are used.

One 48-cycle scenario repeats through:

1. `stable_reference`
2. `incipient_presentation_drift`
3. `persistent_presentation_drift`
4. `bounded_diagnostic_observation`
5. `post_intervention_observation`

At the default two-second cycle interval, the full scenario spans about
96 seconds.

The primary changed relationship is:

`LabelFeedCommand -> LabelAtPeelPoint`

with the configured illustrative expected envelope of 50–350 ms.

The primary held relationship is:

`BottleDetected -> SpacingConfirmed`

with the illustrative expected envelope of 100–400 ms.

The emulated line speed stays close to the same synthetic operating point while
label-presentation timing drifts. This gives the service workflow useful
negative evidence instead of making every signal fail together.

The post-intervention phase is a scenario label only. It does not establish
that a real intervention occurred or that a machine was safely returned to
service.

## Preserved context

Every generated functional/temporal record retains:

- asset identity;
- component identity;
- source identity;
- episode and cycle identity;
- observed timestamp;
- operating mode;
- profile identity;
- configuration version;
- firmware version;
- calibration identity;
- sampling profile;
- recipe/product identity;
- exact config SHA-256;
- scenario phase;
- clock-evidence basis;
- measurement value and engineering unit;
- expected min/max envelope;
- evidence IDs;
- reason code / evidence state.

Clock evidence is explicitly classified as an emulator clock model. It does not
establish PLC/SCADA/historian clock synchronization.

## API compatibility

The emulator serves the existing read paths used by the local UI:

- `GET /api/status`
- `GET /api/history/functional-temporal`
- `GET /api/history/conditions`
- `GET /api/history/observations`
- `GET /api/history/episodes/{episode_id}`

The HTTP surface refuses external historian writes with HTTP 405.

The following governed capabilities remain explicitly unavailable in this
emulator increment and return fail-closed responses:

- configured-policy condition localization;
- functional/temporal reference-versus-selected comparison.

Those capabilities continue to belong to the real historian / acceptance path
until separately implemented and verified for emulated storage.

## Reasoning Inputs UI

The Reasoning Inputs page reads the same historian routes as before.

When the backend reports `emulated = true`, the UI changes its wording to:

- `LIVE EMULATION`
- `EMULATED SOURCE LIVE`
- `Local emulated historian`

and exposes backend, persistence, source classification, latest scenario phase,
latest cycle, measured value, engineering unit, and expected envelope.

It does not label emulated SQLite history as TimescaleDB.

## Server-rendered readiness

A later bounded frontend increment server-renders the initial historian status and recent functional/temporal history for `/reasoning` before browser hydration. Client polling still continues through the same-origin historian proxy afterward. This prevents a browser hydration failure from leaving a healthy emulator displayed as an unassessed `WAITING` state. See `docs/architecture/reasoning-server-rendered-readiness-v1.md`.

## Failure behavior

Retained-store availability and live generator availability are distinct.

If a cycle append fails:

- retained SQLite history remains queryable if the store is healthy;
- `connected` may remain true for the retained store;
- `source_available` becomes false;
- the reason code becomes
  `EVIDENCE.EMULATED_HISTORIAN_SOURCE_UNAVAILABLE`;
- no synthetic replacement record is invented for the failed cycle.

If the service is absent, the existing Next.js historian proxy continues to
return the normal fail-closed historian-unavailable response.

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

## Deferred

This increment does not add:

- physical PLC, SCADA, historian, MES, or CMMS history;
- Docker / Timescale repair;
- Timescale replacement;
- configured-policy localization over SQLite;
- reference-versus-selected functional/temporal comparison over SQLite;
- model inference;
- causal diagnosis;
- equipment control;
- safety approval;
- return-to-service authority.
