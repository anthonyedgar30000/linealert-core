# Functional-temporal orchestration v1

This increment joins the existing governed evidence layers without adding a new inference authority.

```text
accepted LiveConditionResult
        -> explicit source bindings
        -> accumulated cycle EvidenceObservation values
        -> functional-temporal runtime
        -> historian-ready records
        -> one explicit historian transaction
```

## Atomic live-condition unit

A `LiveConditionResult` is the orchestration input because the end event that triggers a transition can also complete a timing relationship used by that transition's guards.

The orchestrator therefore binds the event and every same-step `LiveConditionMeasurement` before transition evaluation. It must not evaluate the trigger event first and attach its completed measurement later.

This preserves the existing transport, machine-profile, timing, clock, and source-binding admission boundaries.

Rejected transport envelopes are skipped. Duplicate machine events are not re-applied to functional-temporal state.

## Cycle evidence

Bound evidence is accumulated by exact cycle ID. A later distinct observation cannot silently replace an existing observation with the same evidence key. That condition requires an explicit temporal-selection policy and fails closed in v1.

Source-binding refusals remain refusals. Missing evidence can therefore leave a guard unresolved; the orchestrator does not manufacture substitute evidence.

## Phase assessment at candidate transitions

When an event is a declared transition candidate, the orchestrator assesses the current phase first if that phase has invariants. The assessment uses only accumulated bound evidence and occurs at the candidate-transition timestamp.

This provides a natural phase-boundary assessment without treating the trigger event itself as proof that the next phase was achieved. The transition is evaluated afterward and advances state only when the runtime returns `ADMITTED`.

An explicit `assess_cycle` operation is also available for governed assessment at another selected time.

## Persistence and rollback

Functional-temporal records generated from one orchestration unit are persisted with `record_functional_temporal_evidence_batch`. TimescaleDB uses one explicit transaction for the batch even though ordinary historian writes use autocommit.

Before reasoning, the orchestrator checkpoints functional-temporal runtime state and the cycle evidence map. If evaluation or persistence fails, both in-memory states are restored. Deterministic record IDs and idempotent historian inserts support retry after uncertain transport/database failures.

Database durability remains external to the deterministic evaluator. A successful evaluator call alone is not reported as successfully persisted evidence.

## Existing synthetic labeler proof

The current labeler fixtures exercise both outcomes:

- a 240 ms label-presentation relationship is within its declared 50-350 ms timing envelope and admits the test transition;
- the existing 550 ms relationship violates that timing envelope and rejects the test transition.

In both cases the conclusion is limited to the declared functional-temporal relationship. No component fault or physical root cause is inferred.

## Authority boundary

The orchestrator does not:

- interpret arbitrary PLC tags;
- create new evidence semantics;
- upgrade point evidence into throughout-phase evidence;
- override source-binding refusals or clock qualification;
- infer physical state or root cause;
- call CADGrounded;
- write to equipment;
- grant maintenance, production, engineering, or safety authority.

It is plumbing across already-governed LineAlert layers, not a new diagnostic engine.
