# Running guide adjustment v1

## Scope

Change the synthetic Labeler 2 guide / spacing path from a forced diagnostic stop to the explicitly commissioned demo assumption that the guide can be inspected and restored through an external adjustment while ordinary production continues.

## Repository baseline

- Base branch: `main`
- Base commit: `44294386cf1f6f8bb0db10008d421a45ba2818ec`
- Prior increment: PR #125, preserve guide observation / restore / verification context on the Labeler 2 card
- Open pull requests before branch creation: none
- Unrelated issue #31 remains outside this increment
- No OEM Labeler 2 manual, commissioned physical-machine package, verified calibration package, or physical equipment connection was observed

## Synthetic commissioning assumption

For this demo profile only, the Labeler 2 guide / spacing reference is treated as externally accessible and commissioned for operator inspection and bounded restoration while the machine remains in ordinary production.

```text
commissioned_demo_permission != real_machine_permission
operator_authorized_in_demo != universally_operator_authorized
```

A real deployment must commission the action against the actual machine safeguarding, OEM procedure, plant rules, operator authority, operating state, limits, verification, and rollback.

## Workflow

```text
qualified OPC UA concern while run_state_code = 1
→ inspect guide / spacing against marked reference
→ record synthetic human observation
→ if outside reference, restore the one commissioned guide setting
→ keep Labeler 2 in production
→ wait for a later qualified production observation
→ start production verification
→ close only after the configured healthy production streak
```

If the simulator is already stopped, the existing stopped diagnostic-batch path remains available as a fallback. Guide actions are blocked during diagnostic-batch motion (`run_state_code = 2`).

## Source and evidence boundaries

- Guide offset remains private simulator state and is not published through OPC UA.
- `inspect_guide` remains a synthetic human observation with source identity.
- `restore_guide` remains a simulator-control receipt, not evidence of effect.
- The first later qualified production source sequence establishes that fresh post-action evidence exists.
- Subsequent production observations drive the existing production-verification streak.

```text
human_observation != OPC_UA_machine_state
recorded_adjustment != verified_effect
intervention_followed_by_improvement != proof_of_mechanism
telemetry != diagnosis
recommendation != authorized_action
```

## Configuration changes

- `synthetic-labeler2-action-authority-v1.json` explicitly permits guide inspection and bounded restore during ordinary production or an approved stopped state, never during diagnostic-batch motion.
- `speedway-labeler-troubleshooting-v1.routes.json` is bumped from profile version 3 to 4 because its operating-state / verification semantics changed.
- The emulator health surface exposes the synthetic running-guide commission flag.

## Not changed

No OPC UA writable node, PLC write, physical equipment connection, source-admission rule, concern threshold, plant-event prior, fast-forward target, CMMS chronology, diagnostic batch mechanics, OEM authority, safety approval, or production authorization is introduced.

## Verification

CI must pass on the exact pull-request head for Python 3.11, Python 3.12, Ruff, UI lint, and UI build. Local acceptance after merge should verify that inspect and restore both occur with `run_state_code = 1`, the Labeler card preserves OBSERVED + ACTION, `VERIFY EFFECT` waits for fresh production evidence, and the source remains in production while later OPC UA observations drive recovery verification.
