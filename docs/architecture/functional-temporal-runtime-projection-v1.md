# Functional-temporal runtime projection v1

This increment connects the deterministic functional-temporal evaluator to the historian record contract without making the historian an inference engine.

## Runtime flow

```text
MachineEvent + already-classified EvidenceObservation
        -> FunctionalTemporalEvaluator
        -> transition / guard / phase / invariant evaluation
        -> historian-ready FunctionalTemporalHistoryRecord values
```

The runtime returns records to its caller. It does not write the database itself, so historian durability remains outside the deterministic runtime operation.
## Transition semantics

A trigger event is only a transition candidate.

- `ADMITTED`: all declared guards are verified; the cycle advances to the target phase and a point-in-time phase-admission record is produced.
- `REJECTED`: a guard is violated; evidence is retained but phase state does not advance.
- `UNRESOLVED`: evidence is missing, stale, insufficient, exposed, or conflicting; evidence is retained but phase state does not advance.
- `NOT_TRIGGERED`: the event does not match a transition from the current phase; no functional-temporal history records are produced.

Cycle state is independent across cycle IDs.
## Phase admission versus phase assessment

A phase-admission record says only that the declared transition guards allowed entry at a point in time. It does not prove that all phase invariants subsequently held.

Phase invariant assessment is a separate operation. Invariant records preserve their declared temporal coverage such as `THROUGHOUT_SCOPE`; the phase summary itself is a point-in-time evaluation record that references those invariant results.

```text
transition guards verified
        -> CAPTURED admitted at T1

later interval evidence
        -> CAPTURED invariants assessed at T2
```

This prevents a successful entry event from being promoted into an unsupported throughout-phase claim.
## Identity and provenance

Projection fails closed when evidence is bound to a different cycle or when the trigger event asset differs from the exact operating context. Each cycle is also bound to one machine/profile, operating mode, configuration, firmware, calibration, sampling profile, recipe/product, and context-tag identity; a mid-cycle change is rejected rather than mixed into one history. Component scope may vary between events and phase owners without changing that cycle identity.

Transition history preserves the exact trigger event ID, source ID, event quality, correlation ID, and deterministic event fingerprint.

Historian record IDs are deterministic for replayed identical evidence, allowing the historian's existing idempotent write boundary to avoid manufacturing duplicate history.

The runtime projection source is distinct from the underlying evidence sources. Backing evidence IDs, source IDs, states, validity, and actual coverage are retained in requirement-record details.
## Authority boundary

The runtime does not:

- derive `EvidenceObservation` from raw PLC values;
- convert telemetry into verified physical state;
- infer root cause;
- write to equipment;
- authorize maintenance or safety decisions;
- make historian durability part of deterministic core rollback.

A later integration can feed governed classified evidence into this runtime and persist the returned records after deterministic evaluation completes.
