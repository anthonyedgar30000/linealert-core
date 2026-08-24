# Commissioning fault-injection boundary

The canned Operator View scenarios are commissioning **fault-injection fixtures**. They are synthetic test inputs for exercising LineAlert, not retained machine evidence and not diagnoses for a condition that arrived from Machine Health.

## Two distinct modes

### Condition investigation

A Machine Health handoff opens the Operator View with `source=health`. In this mode the commissioning scenario workspace is not loaded. The operator sees the measured relationship, the retained historian episode, the known/unknown claim boundary, and verification of the same original relationship.

A health condition such as:

```text
LabelFeedCommand -> LabelAtPeelPoint = 550 ms
commissioned envelope = 50-350 ms
```

must not automatically select an Arrival phase, pressure, slip, tension, or sensor scenario. Those may be useful candidate checks later, but they are not explanations unless their own evidence is admitted.

### Commissioning fault-injection mode

Opening the Operator View without a Machine Health handoff keeps the existing commissioning lab available. Its scenario buttons represent controlled synthetic fixtures such as:

- arrival-phase drift;
- bottle-surface slip;
- excessive web tension;
- low contact pressure;
- gap-sensor retrigger.

The visible scenario model is therefore fixture-driven demonstration content. It must remain clearly separate from live or retained machine evidence.

## Target ingestion path

The intended architecture is:

```text
commissioning fault fixture
        -> synthetic machine events
        -> normal LineAlert admission / correlation / envelope logic
        -> admitted condition evidence
        -> Operator View
```

The conclusion must not be injected directly. The fixture should inject events; LineAlert should earn the resulting condition through the same deterministic evidence path used elsewhere.

Until each fixture has that event-level mapping, the UI must not promote the canned scenario into a Machine Health investigation. The current mode boundary enforces that separation explicitly.

## Claim boundary

A successful fault injection proves that a deterministic test fixture can exercise a configured LineAlert path. It does not establish that the same fault exists on a physical machine, that the injected fault is the root cause of a real outcome, or that a maintenance action is authorized.
