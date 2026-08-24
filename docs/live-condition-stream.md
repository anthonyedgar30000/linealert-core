# Live condition relationship measurement

LineAlert can project a configured timing relationship as condition evidence while an admitted machine-event stream is being consumed.

For the labeler example, the configured relationship is:

`LabelFeedCommand -> LabelAtPeelPoint`

The deterministic core measures the interval from the two machine-event source timestamps. `LiveConditionConsumer` then applies the explicit condition-signal binding and retains the transport clock basis used for that interval.

## What is established

A live condition measurement can establish:

- the exact delay between two correlated admitted machine events;
- the configured timing envelope used for comparison;
- whether the measured delay was early, within the envelope, or late;
- the source event IDs, source IDs, correlation ID, and event quality;
- the transport clock quality associated with both events.

For two events from the same source, LineAlert treats the interval as a same-source relative measurement. Synchronization to wall time is not claimed or required for the relative interval.

For events from different sources, both transport clocks must be declared `synchronized` before the timing finding is promoted to a live condition signal. Otherwise the timing finding remains in the deterministic core, but the live condition layer emits an explicit refusal.

## Runtime publication

`ConditionRuntimeSnapshot` publishes the current governed condition-stream state through the local dashboard bridge at:

```text
http://127.0.0.1:8765/api/condition
```

The API reports whether a condition stream is configured, whether it is still running, the source mode, measurement and refusal counts, the retained claim boundary, and the exact `LiveConditionConsumer` evidence payload.

The Next.js health UI proxies that endpoint through `/api/condition`. It no longer promotes an arbitrary OPC UA proxy into the condition relationship merely because the units or values appear useful.

For a local deterministic runtime demonstration, start the bridge with the checked-in labeler event stream, configuration, and condition binding:

```bash
linealert-opcua-bridge \
  --condition-events-jsonl examples/labeler_demo_events.jsonl \
  --condition-config examples/labeler_demo_config.json \
  --condition-bindings examples/condition_signal_bindings.json
```

The condition runtime is explicitly labelled `deterministic_event_replay`. The checked-in cycle produces the measured `label_presentation_delay_ms` value of 550 ms against the approved 50–350 ms envelope. That is runtime publication of deterministic event evidence, not current physical-machine telemetry.

A physical source adapter remains a separate integration step. When one is eventually connected, it must supply governed `MachineEvent` envelopes with preserved source identity, sequence/session integrity, event quality, and clock evidence; the runtime publication layer does not waive those requirements.

## What is not established

A live relationship measurement does **not** establish:

- physical root cause;
- component health;
- remaining useful life;
- future failure;
- maintenance urgency by itself.

Those claims require additional evidence and validation.

## Why this matters

This closes the gap between replay-only condition evidence and an event-stream runtime path. A source adapter can emit governed `MachineEvent` records, the streaming layer can preserve session and sequence integrity, the timing engine can measure an approved event relationship, the condition layer can expose that measurement, and the UI can consume it without silently upgrading it into a predictive-maintenance claim.
