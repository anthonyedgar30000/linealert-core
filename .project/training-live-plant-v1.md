# LA-T01 live plant training increment

Branch: `agent/training-live-plant-v1`

Base: `main` at `bd1a92839ce0e9c9c5bf88be8dcbdd4a60783789`

## Objective

Turn the existing LA-T01 training route from a mostly textual dashboard into a plant-centered troubleshooting exercise. The increment is limited to three UX mechanics:

1. animated plant observation with pause, normal-speed, fast-forward, and next-meaningful-event controls;
2. evidence selection that produces persistent case readouts without inventing unestablished instrumentation;
3. consequential role handoff from Operator to Maintenance using an evidence package.

## File scope

- `ui/app/training/page.tsx`
- `ui/app/training/training.module.css`
- `.project/training-live-plant-v1.md`

## Equipment and evidence scope

- LA-T01 remains a field-documented training pattern, not a site-validated incident.
- The UI may animate the already-admitted pressure-sensitive label application / web-handling training scope.
- The animation is pedagogical and does not claim geometric, timing, speed, sensor, or kinematic fidelity to a specific machine.
- No numeric web-tension gauge, PLC tension tag, OEM setpoint, site-specific threshold, or undocumented sensor is added.
- Existing provenance remains `docs/training-scenario-provenance.md`.

## Role boundary

- Operator may preserve case history and recurrence evidence and then escalate.
- Maintenance may receive that evidence and perform the case's physical web-path inspection step.
- Electrical/Instrumentation, Controls, OT, and Engineering remain visible but locked in LA-T01 unless later evidence justifies their involvement.
- A successful training handoff does not authorize production intervention.

## Safety and authority

`historical_pattern != current_root_cause`

`recommendation != authorized_action`

`successful_training_case != safe_production_change`

No telemetry ingestion, deterministic diagnostic, PLC/controller, network, historian, equipment-control, or production authority path is modified by this increment.

## Verification

Required on the exact pull-request head:

1. Python 3.11 lint/tests pass.
2. Python 3.12 lint/tests pass.
3. UI ESLint passes.
4. Next.js production build passes and includes `/training`.
5. LA-T01 still hides its scripted mechanism until debrief.
6. Unestablished instrumentation remains disabled and labelled `NOT ASSUMED`.
7. Maintenance cannot be entered before the Operator evidence handoff is earned.
8. Existing Operator View, Machine Health, and Commissioning routes remain untouched by the diff.

## Rollback

Close the pull request without merge, or revert the branch commits. The increment is training UI and project-state documentation only; it does not modify runtime telemetry, diagnostics, or equipment behavior.
