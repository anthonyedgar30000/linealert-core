# Plant Event Log synthetic demo

## Scope

The Plant Event Log is a bounded Event Viewer-style surface over the same controlled synthetic calendar used by the Plant Canvas. It keeps the operational canvas calm while making dense chronology available on demand.

The log combines deterministic background events with a small browser-local interaction journal. Background events include production-window transitions, changeovers, telemetry threshold movement, synthetic CMMS arrivals, maintenance starts/completions, and LineAlert concern creation. The interaction journal records demo workflow actions such as entering bounded diagnostic mode, arming a five-container trial, completing a synthetic HMI run, reviewing trial evidence, explicit restore recommendations, production verification, and recovery observation.

## Roll-change evidence discipline

The alignment incident family is named **Alignment variability emerging**. The incident title does not itself claim a roll change.

For deterministic alignment incidents, the simulator separately creates a synthetic changeover record before the concern:

- production pauses for the roll change
- the operator/changeover source records the label roll replacement
- production resumes
- telemetry later moves outside matched healthy behavior
- LineAlert later records a concern-threshold crossing

The Plant Canvas and troubleshooting guide may surface that prior record as recent context and link to the Event Log. The relationship is explicitly bounded as:

**preceded by change != caused by change**

## Event identity and provenance

Each generated event includes event identity, synthetic timestamp, clock-quality classification, source identity, asset identity, event class, severity, message, and structured fields. User-driven demo workflow events are stored in a separate browser-local journal and are also classified synthetic-demo-only.

The browser implementation is not a production audit store. A production implementation would preserve governed retention, correction/supersession, source lineage, calibration/configuration context where relevant, and reviewer sign-off without silently deleting evidence.

## Display retention

The event table renders a bounded selected time window and at most 250 rows. The browser interaction journal is capped at 200 entries. This prevents the public demo DOM/local storage from growing indefinitely; it is not an operational data-retention recommendation.

## Boundaries

- Event log != diagnosis.
- Event order != causal proof.
- Operator record != verified physical state.
- Synthetic work-order event != CMMS truth.
- Recommendation != authorization or equipment command.
- Five-container response != safe production change.
- Recovery observed != root-cause proof or future reliability guarantee.
