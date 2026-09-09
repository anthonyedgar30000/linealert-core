# Operator single-step interaction contract

## Purpose

The Operator View must not expose LineAlert's internal diagnostic or historical reasoning model just because that information exists.

The operator interaction contract is:

> one question, one reason, one safe response

For an admitted condition that requires an operator-visible check, LineAlert should present only the next justified inspection that can be answered from the approved operating position.

## Screen contract

At any one time the operator sees:

1. one bounded question
2. one short explanation of why that check is relevant
3. a small set of observation responses that describe only what the operator can actually see or safely verify

The screen must not simultaneously expose:

- a diagnostic tree
- multiple possible corrective actions
- historical incident archaeology
- fault-domain scoring
- root-cause ranking
- hidden HMI or controller fields
- settings changes that have not been separately authorized
- verification controls before an authorized intervention has occurred

## Progressive flow

A healthy/clear observation may advance to the next already-admitted check.

An observed issue or an inability to verify safely stops the operator inspection sequence and prepares a handoff to the next qualified owner.

If all bounded operator checks are clear while the admitted condition still requires investigation, LineAlert records that result and hands the condition off rather than inventing another operator action.

## Evidence preservation

The simplified screen does not discard evidence. It may still preserve, when the historian is available:

- source identity
- asset identity
- relationship identity
- observation identifier
- correlation identifier
- operator response
- timestamp supplied by the persistence layer
- source mode

The operator does not need to see all of those fields while performing the check.

## Authority boundary

Operator observation != verified physical state.

A clear visual check != proof that the mechanism is healthy.

A stopped inspection sequence != diagnosis.

An escalation record != proof that a dispatch connector delivered a maintenance notification.

Recommendation != authorized action.

Verification belongs to the responding role after an authorized intervention or to a deterministic reread of the original relationship when that workflow is explicitly commissioned.

## Equipment scope

The current bounded checks are generic demo/operator checks already present in LineAlert Core. The repository does not contain sufficient commissioned OEM/site evidence to promote them into machine-specific procedures. The Speedway troubleshooting route profile remains `synthetic_demo` scope.
