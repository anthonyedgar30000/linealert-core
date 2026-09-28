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

## Supplied step boundaries

The optional `step_boundaries` array contains **synthetic lab notices** for one
exact bound source clock and reference path. Each notice has a unique ID, an
observation method, and an inclusive `[earliest_reference, latest_reference]`
bracket in reference time. A drift-analysis `STEP_CANDIDATE` is not a notice;
the adapter never infers a step boundary from an offset jump.

For each otherwise eligible sample, the adapter tests the entire estimated
event reference-time interval. If it touches a step bracket, that sample is
disqualified. If the event is after the bracket but the sample was taken at or
before its latest possible step time, that sample is also disqualified. A
fresh sample taken strictly after the bracket can qualify an event whose
entire interval is strictly after it. Other source clocks are unaffected.
Disqualified samples do not make a fresh sample ambiguous; if none qualifies,
the refusal retains the implicated sample and boundary IDs. An accepted
post-step observation retains the last boundary ID, reference-time bracket and
observation method with the fresh sample provenance through the historian round
trip.

This is conditional on the completeness and accuracy of the supplied lab
notices. The absence of a notice is not evidence that a physical clock did
not step. A real connector must establish how a step is detected, bound its
time and invalidate cached offsets before any physical timing claim.

## Strict synthetic step coverage

The shipped fixture now opts into `require_step_coverage: true`. Each source
declares a synthetic `step_coverages` record with its exact binding, clock,
reference path, firmware, configuration, calibration and sampling identity,
monitor method and state, and a half-open reference-time coverage interval. An
eligible offset sample must
be taken within **one** `COMPLETE` coverage interval, and the entire estimated
event reference-time interval must end before that coverage ends. The coverage
must start no later than the sample. Missing, partial, degraded, or overlapping
records cause a reasoned refusal. Separate adjacent records cannot silently
be stitched together into a completeness claim.

Accepted strict projections retain the coverage ID, method, and full interval
with the offset sample and any last step boundary through the historian payload.
Retained evidence refuses missing or contradictory coverage fields. The
existing adapter constructor remains compatible with earlier lab callers
unless strict mode is explicitly selected; providing coverage while strict
mode is off is rejected so a declaration cannot be silently ignored.

`COMPLETE` is a **supplied synthetic assertion about the notice feed**, not
independent proof of monitoring completeness. A configured NTP peer or host
time-service state does not establish coverage for a PLC or SCADA clock. A real
connector needs a qualified device-specific observation path and evidence of
monitor continuity, including gaps, restarts and missed steps.

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
topology/configuration/calibration, degraded state, overlapping samples and
strict monitoring coverage refusal.
This establishes the software contract under synthetic input only. A future
connector must independently establish the measurement path and uncertainty
for real NTP/PTP or controller telemetry, including completeness of step
notices during a validity window. Qualified review and equipment-specific
timing requirements are needed before using this for physical cross-system claims.

Rollback is removal of the lab adapter/fixture or stopping fixture injection.
It has no runtime service or equipment side effects.
