# Guide observation UX v1

## Scope

Clarify the localhost Labeler 2 guide / spacing inspection step so the operator-facing action names the physical check and the resulting human observation is immediately visible in the same workflow card.

Base repository state at branch creation:

```text
main: f1e0d96470e312b1e1a3a1ad9f329a6dfb405c42
latest merged PR: #123
open PRs observed: none
open issues observed: #31 only
post-merge CI: success
post-merge Pages: success
physical Labeler 2 connection: not observed
OEM / commissioned Labeler 2 package: not observed
```

`.project/active-work.json` is an older coordination snapshot and explicitly yields to current live GitHub and equipment evidence.

## Change

The existing verify-first control path is unchanged. Only operator-facing wording and immediate observation presentation change:

```text
before:
Record simulated guide / spacing observation

after:
Inspect guide / spacing against marked reference
```

After the simulator returns the existing `inspect_guide` result, the hero card now reports one of the bounded human observations explicitly:

```text
Observed: guide / spacing matches the marked reference.

or

Observed: guide / spacing <offset> mm outside the marked reference.
```

The production-running action is also normalized to the already-established asset-centric wording:

```text
Stop Labeler 2 for bounded diagnostic
```

No new measurement, sensor, authority, or mechanism is introduced. The displayed relation comes from the existing simulator-control observation fields `within_reference` and `observed_offset_mm`.

## Preserved boundaries

```text
simulated_human_observation != verified_physical_state
observation != diagnosis
observation != causal_proof
inspection != authorization_to_adjust
control_acknowledgment != verified_source_state
telemetry != diagnosis
recommendation != authorized_action
```

No emulator progression, OPC UA transport, bridge behavior, source admission, fast-forward, concern threshold, restoration prerequisite, diagnostic batch, production verification, PLC write, OPC UA method call, physical equipment connection, OEM authority, safety approval, or production authorization is changed.

## Verification

Repository contract tests assert:

- the inspection action names the physical guide / spacing check;
- the asset-centric stop action remains present;
- both within-reference and outside-reference outcomes are rendered as explicit observations;
- the existing verify-before-restore and qualified OPC UA run-state gates remain intact.

CI is the software verification gate. Localhost acceptance should confirm the new wording appears after pulling the merged browser-side change and that the resulting observation is visible immediately after inspection.
