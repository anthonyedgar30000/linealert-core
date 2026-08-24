# Operator view and commissioning route boundary

LineAlert now treats the operator surface and the commissioning fault-injection lab as different products with different evidence authority.

## Primary operator route

`/` is the normal Operator View. It renders admitted condition evidence from the LineAlert condition runtime and retained history. It must not initialize a canned fault, preload a scenario conclusion, or substitute synthetic training state when evidence is unavailable.

A Machine Health handoff may add investigation context and an episode timeline to this route, but the underlying operator surface remains evidence-driven.

## Bounded operator actions

When an admitted relationship is outside its commissioned envelope, the Operator View exposes a bounded action sequence:

```text
inspect allowed physical checks
      -> record what was actually observed
      -> perform only site/OEM-authorized simple recovery or escalate
      -> verify the same original relationship
```

For the label-presentation relationship, the first checks are deliberately physical and low-authority: visible label-web drag or snagging, peel-point or sensor obstruction/contamination, and recipe/job/label-stock confirmation.

The condition evidence does not authorize servo tuning, PLC logic changes, timing changes, hidden-parameter edits, or bypasses. If a simple obstruction may be cleared under explicit site/OEM procedure, the operator may follow that procedure and then remeasure the original relationship. Otherwise the operator escalates.

Operator observations, escalation records, and condition verifications are appended to the shared historian episode when the historian is available. An escalation record does not claim that a maintenance dispatch connector delivered a notification; dispatch/ticket integration remains a separate concern.

Verification must re-read the same admitted relationship. Recovery means that relationship has returned inside its commissioned envelope. Persistence means it remains outside. Neither result by itself establishes physical root cause.

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
- operator action guidance does not create authority beyond site/OEM procedure;
- an escalation record does not prove dispatch delivery;
- historical sequence and recovery association do not by themselves establish predictive validity.
