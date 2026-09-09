# LineAlert Triage Board v1

## Purpose

This bounded UX increment tests a narrower LineAlert product interaction model:

`intake -> triage -> assigned -> responding -> verify`

The primary question is not "what can LineAlert reconstruct about the incident?" It is:

> What deserves attention now, who owns the next step, and does the current operating plan still hold?

## Primary surface

The root route (`/`) is a shared plant triage board built for feedback. It intentionally favors current operational orientation over event archaeology.

The board shows:

- overall plant posture
- active triage items
- workflow stage
- current owner
- bounded next step
- response runway and response ETA when the synthetic scenario supplies them
- whether the current plan is represented as holding, being watched, or requiring adaptation

The board is deliberately sparse. Empty columns are useful information.

## Quick Update

The v1 Quick Update field demonstrates low-friction intake. A submitted observation:

- preserves the operator's entered wording
- enters the `INTAKE` stage
- is explicitly labeled `Operator observation — unverified`
- receives no inferred machine identity, root cause, or equipment authority
- exists only in the current browser session

This increment does not add persistence, speech transcription, automatic asset resolution, CMMS dispatch, or workflow integration.

## Evidence is demoted, not deleted

The previous evidence-first Operator View is preserved at `/evidence`.

This establishes a UX boundary:

- triage board = operational posture, ownership and next step
- evidence view / Machine Health = supporting machine evidence and retained history
- training = field-grounded learning path
- commissioning = synthetic commissioning/test path

Detailed chronology, historical comparison and relationship evidence are supporting investigation tools rather than the default user experience.

## Claim and authority boundaries

This v1 is a synthetic feedback surface.

- triage != diagnosis
- anomaly != fault
- recommendation != authorized action
- historical evidence != current root cause
- operator observation != verified physical state
- demo runway/ETA values != commissioned production limits
- browser-session intake != durable system-of-record workflow

No telemetry ingestion, deterministic diagnostic, controller, historian, network, PLC, SCADA, MES, CMMS, safety-control, or equipment-control behavior is changed by this increment.

## Feedback questions

Use the prototype to answer:

1. Can someone understand plant posture from across the room?
2. Is it obvious which items can wait and which need attention?
3. Does every card make ownership and the next bounded step clear?
4. Does Quick Update feel easier than filing a report?
5. Is evidence available without dominating the workflow?
6. Does the board feel calm when no adaptation is required?
7. Does `runway vs response ETA` help explain why an item is or is not urgent?

## Deliberately not in v1

- root-cause workflow
- incident archaeology as a primary view
- probabilistic confidence scores
- autonomous equipment action
- automatic maintenance authorization
- OEM-specific claims
- production-safe adaptation authorization
- persistent workflow engine
- live staffing/CMMS integration
- live plan-validity engine

Those should be considered only after the interaction model is validated.
