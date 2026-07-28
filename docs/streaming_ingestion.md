# Bounded lab streaming ingestion

This increment adds a read-only transport boundary around the existing deterministic LineAlert Core.
It does not add a PLC driver, network listener, persistence service, deployment, or equipment-control
capability.

```text
supplied machine events
→ deterministic lab transport envelopes
→ source-session and sequence validation
→ unchanged LineAlert Core ingestion
→ timing findings and bounded recommendations
→ machine-readable transport and analysis evidence
```

## Purpose

The first acceptance question is transport invariance:

```text
same ordered events
+ same approved configuration
+ same deterministic core
= same pipeline results
```

The existing pressure-sensitive labeler event file can therefore be processed through both ordered
file replay and the lab stream simulator. The resulting Fusion Mosaic receipts, timing findings, and
bounded recommendations must compare equal.

## Transport evidence

Each `StreamEnvelope` preserves:

- the original typed `MachineEvent` and its deterministic fingerprint;
- source identity from the machine event;
- a source-session identity;
- a monotonically increasing transport sequence number;
- the source event timestamp;
- a separate timezone-aware receive timestamp;
- declared clock quality;
- explicit transport attributes such as the adapter or lab source.

Transport metadata does not rewrite the machine event. The event fingerprint remains calculated only
from the original event content.

## Integrity behavior

`StreamConsumer` admits an envelope only when its source session and sequence are continuous.

- The first envelope in a source session must use sequence zero.
- A new session is treated as a source restart and must also begin at zero.
- A previously superseded session cannot silently reappear.
- A sequence gap is retained as `rejected_sequence_gap` and is not admitted to the core.
- An older sequence is retained as `rejected_out_of_order` and is not reordered.
- An exact machine-event duplicate arriving at the next valid transport sequence is admitted, after
  which Fusion Mosaic retains its existing idempotent duplicate behavior.
- Reuse of one event identity with different content still fails through the existing core identity
  collision control.

A rejected transport envelope does not advance the expected sequence. The source can resend the
missing expected envelope without LineAlert inventing or repairing evidence.

## Deterministic simulator

`DeterministicStreamSimulator` wraps an explicitly supplied tuple of `MachineEvent` objects. It adds a
fixed receive delay, session identity, clock-quality declaration, and transport attributes. It does
not generate a diagnosis or simulate unrecorded physical behavior.

```python
from linealert_core import (
    DeterministicStreamSimulator,
    consume_stream,
)
from linealert_core.replay import build_core_from_config, load_events

core = build_core_from_config("examples/labeler_demo_config.json")
events = load_events("examples/labeler_demo_events.jsonl")
stream = DeterministicStreamSimulator(
    events=events,
    session_id="labeler-lab-session-1",
    clock_quality="synchronized",
    transport_attributes={"source": "bounded-lab-simulator"},
)
summary = consume_stream(core, stream)
```

The current labeler fixture should still localize the one supplied late relationship:

```text
LabelFeedCommand → LabelAtPeelPoint
```

That observation remains a timing deviation, not proof of a mechanical fault.

## Machine-readable evidence

`stream_summary_to_dict()` emits:

- machine-profile and process-topology context;
- accepted, rejected, duplicate, finding, and recommendation counts;
- transport-integrity status;
- each event fingerprint and original canonical payload;
- source and receive timestamps;
- session, sequence, clock-quality, and transport evidence;
- the unchanged core delivery receipt, timing findings, and recommendations for admitted events;
- retained uncertainty for both transport admission and diagnostic interpretation.

## Current boundary

This increment deliberately excludes:

- OPC UA, MQTT, Modbus, serial, historian, SCADA, MES, and CMMS connectors;
- automatic timestamp correction or event reordering;
- persistence and lifecycle storage;
- diagnostic-rule or commissioned-baseline changes;
- automatic re-baselining;
- deployment;
- equipment commands or control;
- claims that transport integrity verifies physical state.

```text
transport_admitted != sensor_value_verified
ordered_events != complete_physical_evidence
stream_result != diagnosis
recommendation != authorized_action
successful_lab_test != safe_production_change
```
