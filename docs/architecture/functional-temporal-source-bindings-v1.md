# Functional-temporal source bindings v1

This increment defines the explicit boundary between governed LineAlert source evidence and the `EvidenceObservation` values consumed by functional-temporal guards and invariants.

The binding layer does not inspect arbitrary PLC tags and does not infer mechanical state. It accepts only source objects that have already crossed an existing LineAlert evidence boundary: immutable `MachineEvent` values and clock-qualified `LiveConditionMeasurement` timing relationships.
## Supported source classes

### Machine event occurrence

A binding identifies one exact event type, component, and source. A good-quality matching event can verify only the proposition represented by the binding semantic: that the declared source event was observed.

```text
BottleDetected event observed
        !=
physical bottle presence proven
```

Suspect, bad, or unknown event quality remains `UNRESOLVED`. A source, component, or cycle mismatch produces a refusal and no `EvidenceObservation`.

### Clock-qualified timing relationship

A binding identifies the exact relationship ID, timing rule, condition signal, semantic, scope, unit, and start/end source identities. The measurement must also retain an accepted clock basis.

For good-quality measurements:

- `within` -> `VERIFIED` for the timing-envelope proposition;
- `early` or `late` -> `VIOLATED` for that proposition.

That violation remains a timing-envelope finding. It is not a component-failure or physical-root-cause finding.
## Temporal coverage

All source evidence emitted by v1 is `POINT_ONLY`.

This is intentional. One event occurrence or one completed timing relationship cannot establish that a condition remained true throughout a phase. A phase invariant requiring `THROUGHOUT_SCOPE` therefore remains unresolved until a future interval-evidence mechanism explicitly supplies that coverage.

```text
point sensor/event evidence
        -> POINT_ONLY
        -> cannot satisfy THROUGHOUT_SCOPE invariant
```
## Binding identity and conflicts

Bindings have unique `binding_id` and `evidence_key` values. The example labeler binding document is `examples/labeler_functional_temporal_source_bindings.json`.

Projection refuses silent latest-wins behavior. If multiple distinct source observations attempt to populate the same evidence key in one bounded projection, the caller must resolve the intended temporal selection explicitly rather than having LineAlert choose one implicitly.

Source-level reason codes and retained uncertainty are carried into `EvidenceObservation`. Functional-temporal evaluation preserves those reasons when a source observation is unresolved or violated, and runtime historian projection retains source classification, semantic, reason, uncertainty, validity, and actual coverage in backing-evidence details.
## Authority boundary

The source-binding layer does not:

- equate a PLC command with physical action;
- equate a position-feedback event with successful product restraint or contact;
- upgrade one point observation into interval coverage;
- infer root cause from an out-of-envelope relationship;
- authorize maintenance, safety, or equipment action;
- replace the operating-context binding enforced by the functional-temporal runtime.

The intended path is:

```text
MachineEvent / LiveConditionMeasurement
        -> explicit source binding
        -> EvidenceObservation
        -> guard / invariant evaluator
        -> runtime phase projection
        -> historian-ready evidence
```
