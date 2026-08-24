# Live condition relationship measurement

LineAlert can now project a configured timing relationship as condition evidence while an admitted machine-event stream is being consumed.

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

## What is not established

A live relationship measurement does **not** establish:

- physical root cause;
- component health;
- remaining useful life;
- future failure;
- maintenance urgency by itself.

Those claims require additional evidence and validation.

## Why this matters

This closes the gap between replay-only condition evidence and a real event-stream path. A source adapter can emit governed `MachineEvent` records, the streaming layer can preserve session and sequence integrity, the timing engine can measure an approved event relationship, and the condition layer can expose that measurement without silently upgrading it into a predictive-maintenance claim.
