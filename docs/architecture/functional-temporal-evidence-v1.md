# Functional-temporal evidence model v1

This increment adds deterministic semantics for sustained machine phases without
changing equipment connectivity, historian storage, UI behavior, or control authority.

## Core distinction

- **event**: a discrete observed occurrence;
- **transition**: a candidate move from one phase to another;
- **guard**: evidence that must be established before a transition is admitted;
- **phase**: a sustained operating condition inside a cycle;
- **invariant**: evidence expected to remain valid while a phase is active.

An event does not prove that a transition succeeded. A transition is admitted only
when all declared guards are VERIFIED from current evidence with sufficient temporal
coverage.
## Temporal coverage

Evidence carries one explicit coverage class:

- POINT_ONLY
- THROUGHOUT_SCOPE
- REACHABLE_STATE_SET

A point observation can satisfy only a point requirement. Interval and reachable-state
claims fail closed when the required coverage class is different. This prevents one
healthy sample from proving that a phase invariant held throughout an interval.

## Evidence validity

Immutable observations carry a separate current-applicability state:

- CURRENT
- STALE
- UNKNOWN

Stale evidence remains historically visible but is not usable as current proof.
This model deliberately does not mutate or delete historical evidence.
## Epistemic states

Requirements evaluate to:

- VERIFIED: current evidence and required dependencies establish the condition;
- UNRESOLVED: local evidence is missing, stale, unknown, or lacks required coverage;
- VIOLATED: current evidence establishes a declared condition is not met;
- CONFLICT: current evidence is contradictory;
- EXPOSED: local evidence is established but an upstream requirement remains unresolved.

EXPOSED is derived by dependency reasoning and cannot be supplied as raw evidence.
It means a downstream conclusion is exposed by an unresolved dependency; it does not
mean the machine has failed.
## Transition admission

For a matching trigger event:

- every guard VERIFIED -> transition ADMITTED;
- any guard VIOLATED -> transition REJECTED;
- any guard CONFLICT -> transition remains UNRESOLVED with conflict preserved;
- otherwise -> transition remains UNRESOLVED and the target phase is EXPOSED.

A non-matching event returns NOT_TRIGGERED and does not change phase state.

## Authority boundary

This module consumes already-classified evidence. It does not classify raw PLC values,
diagnose root cause, authorize maintenance, write to equipment, grant safety approval,
or establish verified physical state. Future historian and CADGrounded integrations
should preserve those boundaries.
## Intended next integrations

The v1 types are designed to support later bounded increments:

1. persist cycle, phase, guard, invariant, validity, and coverage evidence in the historian;
2. compare commissioned phase evidence with any later time window;
3. propagate stale evidence only through affected dependencies;
4. rank declared technician checks without inventing actions;
5. hand stable phase/relationship identifiers to CADGrounded for geometry-aware review.

operating_mode remains a longer-lived machine/profile context and is intentionally
separate from phase, which changes repeatedly inside an operating cycle.
