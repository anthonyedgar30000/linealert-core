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

The local schema keeps three classes separate:

1. `machine_observations` — published telemetry/observation snapshots and their original evidence payload;
2. `condition_measurements` — admitted measured relationships such as `LabelFeedCommand -> LabelAtPeelPoint`, including envelope, correlation, topology, source mode, quality, and clock evidence;
3. `operational_outcomes` — operator/maintenance verification records associated with an episode.

This separation is intentional:

```text
raw observation != interpreted condition != human outcome
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
GET  http://127.0.0.1:8767/api/history/observations
GET  http://127.0.0.1:8767/api/history/episodes/{episode_id}
POST http://127.0.0.1:8767/api/outcomes
```

The UI proxies the condition history and outcome write paths through:

```text
GET  /api/historian/conditions
GET  /api/historian/status
POST /api/historian/outcomes
```

`/api/history/conditions` accepts optional `asset_id`, `relationship_id`, `episode_id`, and bounded `limit` query parameters.

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

## Boundary notes

The historian does not change existing evidence claims:

- replay evidence remains replay evidence;
- simulator telemetry remains simulator telemetry;
- a late timing relationship is not automatically a physical fault;
- an intervention followed by recovery is an observed association, not proof that the intervention identified the root cause;
- repeated historical association is not yet predictive-maintenance validation.

A future hosted deployment will need a hosted historian/API and production credential management. The public `chatgpt.site` demonstration cannot directly access a TimescaleDB instance running only on a developer laptop.
