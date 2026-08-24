# Operator view and commissioning route boundary

LineAlert now treats the operator surface and the commissioning fault-injection lab as different products with different evidence authority.

## Primary operator route

`/` is the normal Operator View. It renders admitted condition evidence from the LineAlert condition runtime and retained history. It must not initialize a canned fault, preload a scenario conclusion, or substitute synthetic training state when evidence is unavailable.

A Machine Health handoff may add investigation context and an episode timeline to this route, but the underlying operator surface remains evidence-driven.

## Commissioning route

`/commissioning` contains the canned scenarios that were previously rendered as the default Operator View. These scenarios are controlled synthetic fault-injection fixtures for demonstration, testing, and commissioning work.

The commissioning route is explicitly labeled as synthetic. A fixture is not a diagnosis, not retained machine evidence, and not proof that the represented fault exists on physical equipment.

## Target ingestion path

The intended architecture is:

```text
commissioning fixture
      -> synthetic machine events
      -> normal LineAlert admission
      -> correlation and envelope evaluation
      -> admitted condition evidence
      -> historian
      -> Operator View
```

Until each fixture is wired into that event-level path, its generated scenario cards remain confined to `/commissioning` and do not supersede the normal operator surface.

## Evidence boundary

- operator conclusions follow admitted evidence;
- a missing live condition does not activate a canned scenario;
- commissioning fixtures are upstream test inputs, not downstream diagnoses;
- synthetic and physical evidence retain distinct provenance;
- an admitted relationship deviation does not establish physical root cause;
- historical sequence and recovery association do not by themselves establish predictive validity.
