# Speedway service workflow scope v1

## Purpose

LineAlert's initial commercial workflow is centered on a Speedway service or
maintenance technician responding to an equipment service call. Plant operators
and the plant's internal maintenance staff are not required LineAlert users in
this initial scope.

The product goal is to help the technician reconstruct what changed before the
incident, identify the earliest defensible departure from expected behavior,
preserve evidence provenance, and identify useful missing context before a
bounded troubleshooting action is chosen.

## Initial user and system boundary

Primary LineAlert user:

- Speedway service / maintenance technician.

External evidence and context sources:

- machine telemetry and controller-derived observations when admitted;
- historian records when available and qualified;
- plant CMMS records;
- plant operator observations;
- plant internal-maintenance observations;
- OEM documentation and commissioned references when available.
Plant personnel may supply context without operating LineAlert directly.
LineAlert does not require a direct CMMS integration for v1. A Speedway
technician may ask the plant to check a targeted time window and then record
the returned information with explicit provenance and source-verification state.

## Service-case sequence

The intended initial workflow is:

1. Speedway receives a service call and binds the customer site, asset, and
   reported symptom.
2. LineAlert reconstructs the available pre-incident evidence window.
3. LineAlert identifies the earliest defensible departure from an expected
   relationship, if retained evidence supports one.
4. Relationships that changed are separated from relationships that continued
   to hold.
5. Missing evidence that could discriminate among working explanations is made
   explicit.
6. The technician can ask the plant for targeted context around that time.
7. Returned plant context is recorded with provenance; it is not silently
   promoted to direct machine evidence.
8. The technician performs bounded, reversible checks or tests within applicable
   authority.
9. Working explanations are updated from fresh evidence.
10. A bounded service evidence package records what was observed, tested, and
    concluded without claiming more authority than the evidence supports.
## First detected departure

"First detected departure" is a temporal evidence concept. It means the earliest
retained observation that can defensibly be shown to have moved outside the
applicable expected model or operating envelope.

It is not automatically:

- the root cause;
- the first physical fault;
- the incident start;
- the first alarm;
- proof that the earlier departure caused the later incident.

Temporal precedence is useful for investigation ordering but does not establish
causation.

## Plant-reported context

Until a plant source record is directly retrieved and admitted under an
appropriate source contract, technician-entered plant information remains
plant_reported_context.

A manual record must preserve, where available:

- reported event time or time window;
- entry time;
- technician identity or role;
- reported source, such as CMMS, shift log, or operator statement;
- original wording or a bounded summary;
- source-verification state;
- relevant asset or process scope.

plant_reported_context != verified_source_record.
## Deferred scope

The initial commercial workflow does not require:

- a plant-operator LineAlert interface;
- a plant internal-maintenance LineAlert interface;
- direct customer CMMS integration;
- unrestricted autonomous diagnosis;
- equipment control;
- safety approval or return-to-service authority.

Existing operator-oriented Plant Canvas behavior remains useful synthetic design
history and may support future customer-facing modules. It is not the primary v1
commercial workflow after this scope reset.

## Canonical boundaries

- first_detected_departure != root_cause
- first_detected_departure != incident_start
- plant_reported_context != verified_source_record
- technician_entry != direct_system_observation
- temporal_precedence != causation
- recommendation != authorized_action

This scope change is a product and workflow contract only. It introduces no
runtime behavior, equipment connection, equipment command, or production
authority.
