# LineAlert Core

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

- **`linealert-core`**: machine events, Fusion Mosaic, temporal relationships, topology,
  expected-versus-observed reasoning, bounded recommendations, PMV, and rule promotion.
- **`helix-protocol-kernel`**: governed evidence-package and transport contracts.
- **`HelixMemoryService`**: persistence and retrieval services.
- Legacy LineAlert repositories are design archaeology and sources of reusable tests or ideas.

The initial package does not directly install the private protocol repository, keeping public CI
self-contained. Protocol integration will be added at explicit package boundaries.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ruff check .
pytest
```

## Example

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

## Development workflow

`main` is the trusted, reviewed state. Changes belong on bounded branches with tests and pull
requests. AI may propose patches or rules, but activation remains governed, versioned,
testable, and reversible.
