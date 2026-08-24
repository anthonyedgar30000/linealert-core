# LineAlert Core

For the live read-only Microsoft OPC PLC dashboard lab, see
[docs/opcua-local-demo.md](docs/opcua-local-demo.md).

The lab bridge can capture normalized observation snapshots for deterministic replay:

```bash
linealert-opcua-bridge --operating-mode demo_emulation --capture-jsonl evidence/opcua/microsoft-opc-plc.jsonl
linealert-opcua-bridge --replay-jsonl evidence/opcua/microsoft-opc-plc.jsonl
```

`demo_emulation` is an explicit source-authority setting. Selecting `physical_commissioning` or
`physical_operational` disables this simulator source; discovering a physical connection never
changes modes automatically. Unknown or mixed-source states fail closed.

## Hybrid role interface

The current role-based interface is included in `ui/`. It reads qualified observations through a
same-origin server route and privately proxies them to the local read-only bridge. The standalone
guide at `docs/troubleshooting-guide.html` preserves controlled troubleshooting knowledge; the
retired static dashboard remains available only through Git history.

On Windows, with the OPC PLC container running and the Python environment installed:

```powershell
.\scripts\start-hybrid.ps1
```

Open `http://localhost:8766`. The evidence console must report `LIVE OPC UA` and identify
`SIM-OPCPLC-01`. If the bridge retains stale observations after a disconnect, the interface reports
`STALE · FAIL CLOSED`; it does not silently treat the last value as current.

The local process boundary is:

```text
OPC UA simulator :50000
→ Python evidence bridge :8765
→ same-origin UI telemetry route :8766/api/telemetry
→ role-based interface :8766
```

## Machine health / condition monitoring prototype

The `/health` UI reuses the same evidence boundary for a separate condition-monitoring experiment.
Its primary economic hypothesis is earlier maintenance intervention when real production history
shows that specific relationship drift reliably precedes downtime, scrap, or emergency maintenance.

The maturity sequence is explicit:

```text
deviation detected
→ persistent condition degradation detected
→ failure prediction validated only after real maintenance outcomes support it
```

The initial screen demonstrates a simulated `Photoeye → label-feed response` relationship with a
120–140 ms commissioned envelope. It also reads the local bridge and recent observation history,
but it does not reinterpret existing simulator proxies as that response-time relationship.

A live condition view is enabled only when a signal named `label_feed_response_ms` is both present
and semantically admitted. Until then, RPM, derived conveyor-arrival timing, and pressure remain
live context beside the clearly labelled simulated condition model.

The bridge exposes recent observation history at:

```text
http://127.0.0.1:8765/api/history?limit=240
```

The default history buffer is 7,200 snapshots and can be changed with `--history-size`. The buffer
is not durable by itself. Use the existing `--capture-jsonl` option to retain the same qualified
observation snapshots for later replay and analysis. The Next.js route `/api/history` proxies the
recent-history endpoint just as `/api/telemetry` proxies the current snapshot.

Open the condition-monitoring screen locally at:

```text
http://localhost:8766/health
```

LineAlert Core is the deterministic machine-event reasoning layer for LineAlert.

The first vertical slice implements:

```text
typed machine events
→ Fusion Mosaic subscription routing
→ correlation-aware timing relationship
→ approved timing-envelope comparison
→ topology-aware diagnostic recommendation
→ replayable deterministic tests
```

The output is deliberately bounded. A timing deviation can localize the first observed process
relationship that moved outside its envelope and recommend low-risk checks. It does not claim
to prove a root cause.

## Repository boundary

- **`linealert-core`**: authoritative current LineAlert implementation for machine events, Fusion
  Mosaic, temporal relationships, topology, expected-versus-observed reasoning, governed baseline
  resolution, replay-baseline assessment, bounded recommendations, PMV, and rule promotion.
- **`helix-protocol-kernel`**: separate governed evidence-package and transport-contract boundary.
- **`ContextOS`**: separate execution-containment and policy-enforcement boundary.
- **`HelixMemoryService`**: early memory-service prototype retained as design archaeology; it is not
  current LineAlert persistence, retrieval, or lifecycle-system authority.
- Other legacy LineAlert repositories are design archaeology. Their code or ideas become current
  only through bounded reimplementation, source attribution, tests, review, and explicit approval.

No current persistence or retrieval integration is established by installing a legacy repository.
Future integration must use an explicit package boundary, current data and provenance contracts,
tests, deployment evidence, rollback, and review. The initial package does not directly install the
private protocol repository, keeping public CI self-contained.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ruff check .
pytest
```

## Python example

```python
from datetime import UTC, datetime, timedelta

from linealert_core import (
    DependencyEdge,
    LineAlertCore,
    MachineEvent,
    TemporalRule,
    TopologyGraph,
)

topology = TopologyGraph(
    [
        DependencyEdge("ProductDetected", "ActuatorCommand"),
        DependencyEdge("ActuatorCommand", "ProductTransfer"),
    ]
)
rule = TemporalRule(
    rule_id="transfer-delay",
    start_event="ActuatorCommand",
    end_event="ProductTransfer",
    min_delay_seconds=2.0,
    max_delay_seconds=4.0,
    topology_from="ActuatorCommand",
    topology_to="ProductTransfer",
)
core = LineAlertCore(rules=[rule], topology=topology)

started = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
core.ingest(
    MachineEvent(
        event_id="e-1",
        source_id="plc-1",
        asset_id="LABELER-04",
        component_id="label-feed",
        event_type="ActuatorCommand",
        timestamp=started,
        correlation_id="cycle-1",
    )
)
result = core.ingest(
    MachineEvent(
        event_id="e-2",
        source_id="plc-1",
        asset_id="LABELER-04",
        component_id="transfer",
        event_type="ProductTransfer",
        timestamp=started + timedelta(seconds=5),
        correlation_id="cycle-1",
    )
)

print(result.timing_findings[0].status)
print(result.recommendations[0].summary)
```

## Replay captured or simulated data

The replay adapter accepts an ordered event stream in JSON Lines or CSV. A source adapter can
therefore export PLC, Node-RED, MQTT, historian, or simulated observations without being coupled
to the reasoning core.

Run the small smoke-test example:

```bash
linealert-replay \
  --config examples/replay_config.json \
  --input examples/events.jsonl \
  --output replay-report.json
```

The command processes records in file order and writes a machine-readable JSON report containing:

- the loaded machine profile, when one is supplied;
- the approved process topology;
- exact Fusion Mosaic delivery receipts;
- duplicate-event status;
- timing findings;
- topology-aware recommendations;
- retained uncertainty.

Each JSONL record is one `MachineEvent`:

```json
{
  "event_id": "evt-1001",
  "source_id": "plc-labeler-04",
  "asset_id": "LABELER-04",
  "component_id": "label-feed-servo",
  "event_type": "ServoCurrent",
  "timestamp": "2026-07-19T12:00:00Z",
  "correlation_id": "cycle-827",
  "value": 3.8,
  "unit": "A",
  "quality": "good",
  "attributes": {
    "recipe": "500ml"
  }
}
```

Required columns for CSV are the same required event fields. Optional columns are `value`, `unit`,
`quality`, and `attributes`. The `attributes` cell must contain a JSON object. Timestamps must be
ISO 8601 and timezone-aware.

A replay configuration defines the approved topology and timing envelopes:

```json
{
  "topology": {
    "dependencies": [
      {"from": "ActuatorCommand", "to": "ProductTransfer"}
    ]
  },
  "temporal_rules": [
    {
      "rule_id": "transfer-delay",
      "start_event": "ActuatorCommand",
      "end_event": "ProductTransfer",
      "min_delay_seconds": 2.0,
      "max_delay_seconds": 4.0,
      "topology_from": "ActuatorCommand",
      "topology_to": "ProductTransfer"
    }
  ]
}
```

## Measured condition-signal projection

The timing core already measures the delay between explicitly correlated machine events. A bounded
projection can now give a selected timing rule a stable condition-monitoring signal name without
pretending that a different proxy represents the relationship.

For example, the labeler demo can project the measured
`LabelFeedCommand → LabelAtPeelPoint` timing finding as `label_presentation_delay_ms`:

```bash
linealert-replay \
  --config examples/labeler_demo_config.json \
  --input examples/labeler_demo_events.jsonl \
  --condition-signal-bindings examples/condition_signal_bindings.json \
  --output labeler-demo-report.json
```

The resulting `condition_signal_projection` retains the rule ID, correlation ID, event-pair start
and end timestamps, topology relationship, temporal-envelope status, and an explicit claim boundary.
The projection establishes only a measured correlated-event delay. It does **not** establish root
cause, component health, remaining useful life, or a future failure prediction.

This increment is deliberately offline and deterministic. It adds no new PLC connector, listener,
physical-equipment access, or deployment path. Wiring a live adapter to physical start/end signals
remains a separate Tier 2 change requiring the repository's qualified-review gate.

The current `/health` prototype still waits specifically for a semantically admitted
`label_feed_response_ms`. The example above does not rename the different label-presentation
relationship to make that screen appear live. The exact event pair must be mapped first.

## Full pressure-sensitive labeler demo

The full demo requires an explicit machine profile rather than treating structurally valid events
as automatically applicable. The profile declares:

- the asset identity;
- twelve physical and logical components;
- functional dependencies between those components;
- event-to-component bindings;
- the approved operating mode;
- the forward process graph;
- nine timing envelopes.

Run it with:

```bash
linealert-replay \
  --config examples/labeler_demo_config.json \
  --input examples/labeler_demo_events.jsonl \
  --output labeler-demo-report.json
```

The demo process topology is:

```text
BottleDetected
      ↓
SpacingConfirmed
      ↓
AlignmentConfirmed ───────────────┐
      ↓                           │
LabelFeedCommand ← WebTensionStable
      ↓
LabelAtPeelPoint
      ↓
InitialContact
      ↓
WipeDownComplete
      ↓
InspectionComplete
      ↓
ProductReleased
```

The sample cycle keeps every approved relationship within its envelope except
`LabelFeedCommand → LabelAtPeelPoint`. That relationship takes 0.55 seconds against an approved
0.05–0.35 second envelope. The core localizes the observed deviation to the label-presentation
handoff and recommends bounded checks without declaring a root cause.

When a machine profile is loaded, the core rejects:

- events for another asset;
- undeclared components;
- undeclared event types;
- event types emitted by the wrong component;
- operating modes outside the approved profile;
- topology or timing rules that reference undeclared events.

## Development workflow

`main` is merged repository reality. Issue #27 defines the risk-tiered workflow: Tier 1 work requires
bounded scope, exact-head CI, and fresh named merge authority; qualified review remains mandatory
for live adapters, persistent external integration, physical equipment, production networks,
equipment control, safety or OEM claims, and production release. Issue #31 records the disposable
Stage 1 simulator exception under owner authority. Changes belong on bounded branches with tests
and pull requests. AI may propose patches or rules, but activation remains governed, versioned,
testable, and reversible.
