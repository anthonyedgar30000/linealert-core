# Lab clock telemetry adapter v1

This is a contained, read-only fixture path after PR #144. The repository's
machine documentation is synthetic; no commissioned clock topology, equipment
connection, NTP/PTP management query, or production reference authority is
established here. `examples/clock_telemetry_lab_v1.json` deliberately declares
`synthetic_lab_only` and cannot be relabeled as plant telemetry in the loader.

## Input contract

Each source has one exact lab binding: source and clock IDs, reference clock,
acyclic reference-to-clock path, firmware, configuration, calibration, sampling
profile, and maximum sample age. Samples retain those same identities plus a
reference-time validity interval, signed offset (source minus reference),
measurement uncertainty, maximum holdover drift rate, synchronization state,
method, classification and sample ID. A merely configured NTP/PTP client is
not an offset measurement.

For an event, the adapter conditionally estimates its reference time by
subtracting the *measured* sample offset from the raw source timestamp. It
expands uncertainty for elapsed time since sampling. With rate `p` in ppm and
age `t` in seconds, the conservative bound in milliseconds is:

```text
U = (sample_uncertainty_ms + p × t / 1000) / (1 - p / 1,000,000)
```

The entire `[estimated reference time ± U]` interval must fit inside the
sample's declared validity window. The event must be within the binding's
maximum sample age. Only one sample may qualify, and it must declare `LOCKED`.
Any missing binding or sample, identity conflict, expired or future sample,
overlap, or degraded synchronization returns a reasoned refusal. There is no
latest-wins or implicit reference-path normalization.

An accepted projection adds `ClockObservation` to a `StreamEnvelope` without
changing its event, raw timestamp or transport `clock_quality`. The numeric
cross-source gate from #144 then applies its own declared uncertainty limit.
The event-bound reference timestamp is **an estimate derived from sample
telemetry**, not an independently witnessed physical event time. Source and
clock evidence may both be synthetic in the lab.

## Evidence and staged verification

The observation preserves the full lab sample identity and calculation:
sample ID and measurement method, binding ID, reference path, validity,
configuration/firmware/calibration/sampling identity, sample uncertainty,
maximum age, drift rate and allowance, and actual sample age. The existing
report and historian JSON round trip retains this record. No historical rows
are rewritten. The adapter never adjusts a clock or creates a diagnosis.

Tests feed the fixture into the current live timing gate; exercise stable
projection, drift and step candidates, stale/expired data, conflicting
topology/configuration/calibration, degraded state and overlapping samples.
This establishes the software contract under synthetic input only. A future
connector must independently establish the measurement path and uncertainty
for real NTP/PTP or controller telemetry, including clock steps during a
validity window. Qualified review and equipment-specific timing requirements
are needed before using this for physical cross-system claims.

Rollback is removal of the lab adapter/fixture or stopping fixture injection.
It has no runtime service or equipment side effects.
