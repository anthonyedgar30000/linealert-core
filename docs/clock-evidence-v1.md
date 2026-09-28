# Event-bound clock evidence v1

This increment is a bounded, read-only timing assessment for LineAlert's synthetic
or explicitly supplied event streams. It does not synchronize device clocks,
query NTP/PTP infrastructure, alter source timestamps, or authorize a machine
action. There is no physical equipment connection or commissioned timing package
in this repository.

## Scope and provenance

`ClockObservation` binds an offset estimate to one exact event ID, source ID,
source timestamp, event reference time, clock ID, reference clock ID,
measurement method and evidence ID. Its signed offset is **source time minus
reference time**; the event reference time must agree with that offset within
the declared bound. The uncertainty
must include the measurement path and be supplied by a qualified adapter; a
transport label such as `synchronized` alone is not a numerical bound.

An optional `max_combined_uncertainty_ms` on a condition signal binding enables
strict cross-source assessment in the live stream path. Both event transports
must still declare synchronized clocks. Both event-bound clock observations must
be present and must identify the same exact reference clock. The bound is the
conservative sum of the two stated uncertainties:

```text
estimated interval = raw interval + start offset - end offset
interval bounds = estimated interval ± (start uncertainty + end uncertainty)
```

The whole interval must fall within, before, or after the temporal rule's
envelope, and the resulting classification must agree with the raw timing
finding. A missing or mismatched reference, excessive uncertainty, boundary
overlap, or changed classification produces a refusal. Same-source relative
timing remains on the existing path; opting it into a numeric requirement
refuses until an elapsed-time/rate bound is implemented. Replay projection
refuses bindings that ask for event-bound numeric clock evidence.

The accepted assessment retains the raw interval, estimated interval, lower
and upper bounds, and both full event-bound clock observations (IDs, clocks,
reference, timestamps, offsets, uncertainty and measurement method) in the
report and historian JSON. Functional-temporal provenance carries the key
numeric bounds and evidence IDs as string fields.
The original event timestamps and raw measurement remain unchanged. This is
conditional on the supplied clock observations; LineAlert has not independently
verified a reference source or a device's physical state.

## Drift and step candidates

`assess_clock_drift` consumes an ordered series for one source clock and one
reference. At least three samples are required. A resolved, consistently
directed offset slope above an explicit parts-per-million threshold yields
`DRIFT_CANDIDATE`. An isolated resolved jump with stable readings on both
sides yields `STEP_CANDIDATE`. Other series yield `INDETERMINATE`. These are
observations about relative clock offsets, never a diagnosis of a grandmaster,
switch, PLC, or operator action. No current runtime feeds live NTP/PTP telemetry
to this function.

## Verification and limits

Unit and stream tests cover signed offsets, exact event binding, reference
mismatch, missing bounds, uncertainty threshold, envelope overlap, changed
classification, payload retention, drift, step and unresolved noisy samples.
The installed NUC historian remains on the existing deployed code until a
separate reviewed deployment; this increment does not change its service.

The next contained stage is an adapter for actual clock telemetry with source
identity, reference topology, calibration/measurement method, synchronization
status, firmware/configuration version, measured uncertainty and explicit
validity windows. Lab-inject stable, drifting, stepped and missing-reference
streams before considering a physical plant. Disable the optional binding
threshold or revert this commit to roll back the new gate; raw historian rows
are not rewritten. Qualified review is required before production timing
claims or clock correction.
