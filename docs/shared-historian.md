# Shared operational historian

LineAlert now has an optional local TimescaleDB historian that both the Machine Health view and the Operator View can access through one API boundary.

The historian is deliberately **outside** the deterministic core transaction. It observes evidence that has already been published by the bridge, persists it idempotently, and stores operator verification outcomes. A historian write does not retroactively admit an event, change a timing finding, prove a physical root cause, or authorize equipment action.

## Local topology

```text
OPC UA / deterministic event replay
                |
                v
      LineAlert evidence bridge :8765
                |
        published evidence only
                |
                v
      Historian service :8767
                |
                v
     TimescaleDB / PostgreSQL :5433
                |
          +-----+------+
          |            |
          v            v
   Machine Health   Operator View
```

The UI never connects directly to PostgreSQL. Next.js proxies the historian API so both views consume the same service contract.

## Stored evidence classes

The local schema keeps four classes separate:

1. `machine_observations` — published telemetry/observation snapshots and their original evidence payload;
2. `condition_measurements` — admitted measured relationships such as `LabelFeedCommand -> LabelAtPeelPoint`, including envelope, correlation, topology, source mode, quality, clock evidence, and optional cycle/phase operating context;
3. `functional_temporal_evidence` — append-only phase, transition, guard, and invariant evaluations with exact machine/configuration context, temporal coverage, evidence validity, and epistemic state;
4. `operational_outcomes` — operator/maintenance verification records associated with an episode.

This separation is intentional:

```text
raw observation != relationship measurement != phase evidence != human outcome
```

A shared timeline preserves association and sequence. It does not by itself establish causation or predictive validity.

## Local setup

The hybrid launcher starts the local TimescaleDB container and the historian sidecar by default.

Install the historian Python extra once:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[opcua,historian]'
```

Then run:

```powershell
.\scripts\start-hybrid.ps1 -SkipInstall
```

The local development database is exposed only on loopback at `127.0.0.1:5433`. The compose credentials are development-only and must not be reused for a hosted or production deployment.

To run the UI without the shared historian:

```powershell
.\scripts\start-hybrid.ps1 -SkipInstall -SkipHistorian
```

## Historian endpoints

The sidecar serves:

```text
GET  http://127.0.0.1:8767/api/status
GET  http://127.0.0.1:8767/api/history/conditions
GET  http://127.0.0.1:8767/api/history/conditions/localize
GET  http://127.0.0.1:8767/api/history/functional-temporal
GET  http://127.0.0.1:8767/api/history/functional-temporal/compare
GET  http://127.0.0.1:8767/api/history/observations
GET  http://127.0.0.1:8767/api/history/episodes/{episode_id}
POST http://127.0.0.1:8767/api/functional-temporal
POST http://127.0.0.1:8767/api/outcomes
```

The UI proxies the shared-history paths through:

```text
GET  /api/historian/conditions
GET  /api/historian/conditions/localize
GET  /api/historian/functional-temporal
GET  /api/historian/functional-temporal/compare
GET  /api/historian/status
GET  /api/historian/episodes/{episode_id}
POST /api/historian/outcomes
```

`/api/history/conditions` accepts `asset_id`, `relationship_id`, `episode_id`, `cycle_id`, `phase_id`, inclusive timezone-aware `from_time` / `to_time`, and bounded `limit` filters. Condition-history reads now query one row beyond the requested limit and report explicit `truncated` / `older_matching_records_omitted` state. `/api/history/functional-temporal` accepts `asset_id`, `episode_id`, `cycle_id`, `phase_id`, `record_kind`, inclusive timezone-aware `from_time` / `to_time`, and bounded `limit` filters with the same visible truncation rule.

The read-only `/api/history/conditions/localize` endpoint accepts an exact asset, explicit selection label, target relationship, and bounded episode/cycle/time selection. It does not accept caller-supplied N-of-M values in the normal HTTP path. The service resolves the named persistence policy bound to that relationship from the same asset-bound `--condition-config` used for topology authority, then passes the policy's retained N-of-M rule into the existing selector/localizer path. Missing policy is a bounded refusal; there is no global default. Successful and bounded results retain the policy ID/revision plus asset/profile/config SHA provenance. A relationship-only filter is rejected because it would hide dependency evidence. New condition-history writes can also retain nullable `evidence_authority` describing the historian's exact write-time config and relationship policy binding. Pre-existing rows are not backfilled and remain `null`. The localization endpoint does not consume this new field in this increment, so historical policy equivalence remains explicitly unverified until a later verifier compares retained authority with the applied policy.

The read-only `/api/history/functional-temporal/compare` endpoint accepts one exact asset plus separately prefixed `reference_*` and `selected_*` selection fields. Each side must supply an explicit label and a bounded episode, cycle, or timezone-aware time window. The endpoint executes the governed historian selector and commissioned-vs-selected comparator; it does not infer which record set should be treated as commissioned truth.

Functional-temporal writes require exact `asset_id`, component/profile identity, operating mode, configuration version, firmware version, calibration ID, and sampling profile. Recipe/product identity and context tags are preserved when supplied. A transition record additionally requires exact from/to phase IDs, transition ID, trigger event ID, and transition disposition.

The persistence boundary accepts only already-evaluated phase evidence. The current evidence bridge does **not** infer or synthesize functional-temporal records from raw PLC values in this increment; deterministic runtime projection remains separate work.

## Current demo episode

The deterministic condition replay is persisted under:

```text
condition-runtime-replay
```

The repeated demo measurements are idempotent because the historian key includes the original observation timestamp and observation ID. Restarting the demo does not silently manufacture additional distinct measurements from the same replay evidence.

When the Operator View runs **Verify original condition**, the current admitted relationship is re-read. The verification result is then appended as an operational outcome in the same shared episode when the historian is available.

That produces the first durable LineAlert loop:

```text
condition history
      -> investigation handoff
      -> bounded operator workflow
      -> verify original relationship
      -> operational outcome in shared history
```

## Dashboard episode timeline

The dashboard handoff now projects the durable episode into a compact evidence timeline instead of leaving the historian as invisible backend plumbing. The Machine Health handoff shows the retained measurement/outcome count, while the Operator View shows selected evidence milestones from the same episode:

```text
episode evidence begins
      -> first commissioned-envelope exit
      -> latest persisted condition
      -> operator verification outcome
```

The timeline is intentionally selective rather than a second raw-data browser. It keeps the full episode in TimescaleDB while surfacing the moments most useful to the investigation. Operator-view verification records are preferred in the visible outcome milestones when present; the underlying episode still retains all outcome records.

The timeline is also claim-bounded: chronological sequence and repeated association remain evidence, not automatic proof of causation, root cause, remaining useful life, or future failure.

## Boundary notes

The historian does not change existing evidence claims:

- replay evidence remains replay evidence;
- simulator telemetry remains simulator telemetry;
- a late timing relationship is not automatically a physical fault;
- an intervention followed by recovery is an observed association, not proof that the intervention identified the root cause;
- repeated historical association is not yet predictive-maintenance validation.

A future hosted deployment will need a hosted historian/API and production credential management. The public `chatgpt.site` demonstration cannot directly access a TimescaleDB instance running only on a developer laptop.
