# LineAlert Core

LineAlert is an industrial systems prototype for connecting machine evidence, commissioned expectations, condition drift, and human-facing operational context without overstating what the evidence establishes.

The current project has two deliberately separated demonstrations:

- **Operator / troubleshooting view** — bounded troubleshooting, role-specific evidence, visual machine relationships, deterministic routing, and explicit authority limits.
- **Machine Health view (`/health`)** — commissioned baselines, recent observation history, condition drift, and the path from deviation detection toward evidence-backed predictive maintenance.

## Product thesis

LineAlert's primary economic hypothesis is condition monitoring that can eventually support earlier maintenance intervention when real production history demonstrates that specific drift patterns reliably precede downtime, scrap, or emergency maintenance.

The maturity sequence is intentionally explicit:

1. **Deviation detected** — a named machine relationship moves outside a commissioned envelope.
2. **Condition degradation detected** — the deviation persists or trends across repeated qualified observations.
3. **Failure prediction validated** — only after real maintenance outcomes establish repeatable predictive value.

LineAlert does **not** treat stage 1 or 2 as proof of root cause or future failure.

The same machine relationship model may also support operator, OEM, school, and industrial-lab learning. That is a useful secondary application rather than the main production ROI claim.

## Machine Health prototype

Run the Next.js UI and open:

```text
http://localhost:8766/health
```

The Machine Health view demonstrates a photoeye-to-label-feed response relationship with a commissioned 120–140 ms envelope and a simulated degradation sequence. It also reads the local LineAlert bridge when available.

Live bridge evidence remains separate from the simulated condition model unless an exact condition signal named `label_feed_response_ms` is both present and semantically admitted. Existing simulator proxies such as RPM or derived conveyor arrival timing are shown as live context; they are not silently reinterpreted as the condition signal.

## Recent observation history

The OPC UA bridge now retains a bounded recent history and exposes it at:

```text
http://127.0.0.1:8765/api/history?limit=240
```

The default recent buffer is 7,200 snapshots and can be changed with:

```powershell
python -m linealert_core.opcua_bridge --history-size 14400
```

The in-memory history is useful for live drift views but is not durable. To preserve complete observation snapshots for later replay and analysis, enable JSONL capture:

```powershell
python -m linealert_core.opcua_bridge `
  --capture-jsonl .\captures\linealert-observations.jsonl
```

When JSONL capture is enabled, the history API reports `jsonl_capture` as its persistence mode while continuing to serve a bounded recent window to the dashboard.

Replay the exact captured observations with:

```powershell
python -m linealert_core.opcua_bridge `
  --replay-jsonl .\captures\linealert-observations.jsonl
```

## Local hybrid demo

The UI expects its telemetry route at `/api/telemetry`; the Next.js server proxies that request to the local bridge at:

```text
http://127.0.0.1:8765/api/telemetry
```

The history route `/api/history` similarly proxies the bridge's recent-history API. Override the endpoints with `LINEALERT_BRIDGE_URL` and `LINEALERT_HISTORY_URL` when needed.

A typical local workflow is:

```powershell
# Terminal 1: start the read-only OPC UA bridge
python -m linealert_core.opcua_bridge --endpoint opc.tcp://localhost:50000 --capture-jsonl .\captures\demo.jsonl

# Terminal 2: start the Next.js UI
cd ui
npm run dev
```

Then browse to:

```text
http://localhost:8766/
http://localhost:8766/health
```

## Evidence boundaries

LineAlert uses explicit evidence boundaries throughout the prototype:

- Transport connectivity does not establish semantic meaning.
- Simulator evidence does not establish physical machine state.
- A derived proxy does not become a different machine relationship because the units look compatible.
- Historical similarity does not establish root cause.
- Evidence quality does not grant action authority.
- Condition degradation does not become predictive maintenance until maintenance outcomes validate predictive value.

The operator interface and Machine Health interface are therefore designed to fail closed when an evidence binding required for a stronger claim is absent.

## Development

Python core:

```powershell
python -m pip install -e ".[dev]"
ruff check .
pytest
```

UI:

```powershell
cd ui
npm ci
npm run lint
npm run build
```

GitHub Actions runs the Python test matrix and the UI lint/build checks for pull requests.

## Repository structure

```text
src/linealert_core/   deterministic core, evidence handling, OPC UA bridge
profiles/             machine/evidence/operating-mode profiles
tests/                unit and replay tests
ui/                   Next.js operator and Machine Health interfaces
docs/                 supporting demo/reference material
examples/             replayable examples
scripts/              local startup helpers
```

## Current status

This repository is a prototype and validation environment. Simulated scenarios are clearly identified as such. Physical-machine claims require explicitly mapped and qualified evidence, and predictive-maintenance claims require real outcome validation before they are represented as established capability.
