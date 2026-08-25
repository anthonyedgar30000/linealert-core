# LA-T01 deterministic event pacing increment

Branch: `agent/training-event-pacing-v2`

Base: `main` at `ba27b1e8dedc6a4d56911e713198d2de9c2b3974`

## Objective

Make the merged LA-T01 plant exercise behave like a paced scenario rather than a manually advanced slide deck.

The increment is limited to:

1. a deterministic browser-side training clock;
2. automatic onset of the already-admitted first jam and recurrence events;
3. pause, normal-speed, and 3x playback that affect event pacing as well as animation;
4. skip-to-next-event as a pacing shortcut rather than a fault creation control;
5. explicit provenance text that training timestamps are pedagogical and not machine timing evidence.

## Equipment and evidence scope

- LA-T01 remains a field-documented pattern, not a site-validated incident.
- No new failure mechanism is added.
- No pre-fault numeric drift is invented.
- No PLC tag, tension sensor, OEM threshold, setpoint, cycle time, commissioned limit, or site-specific timing is introduced.
- The browser event times are scenario pacing only and must not be interpreted as physical machine timing.

## Interaction sequence

- Start case -> baseline runs on the training clock.
- First documented symptom appears automatically.
- Player records the event before the scenario continues.
- The line resumes under training orchestration.
- Recurrence appears automatically later in the same deterministic exercise.
- Operator packages event history + recurrence evidence.
- Maintenance handoff and physical web-path inspection remain evidence-gated.
- Debrief reveals the admitted training mechanism only after the handoff path is completed.

## Authority and safety

`telemetry != diagnosis`

`historical_pattern != current_root_cause`

`recommendation != authorized_action`

`successful_training_case != safe_production_change`

The training clock is not a controller clock, historian timestamp, production sample interval, or verified machine timing source.

## File scope

- `ui/app/training/page.tsx`
- `docs/training-scenario-provenance.md`
- `.project/training-event-pacing-v2.md`

No telemetry ingestion, deterministic diagnostic, PLC/controller, historian, network, equipment-control, or production-authority path is modified.

## Verification

Required on the exact pull-request head:

1. Python 3.11 lint/tests pass.
2. Python 3.12 lint/tests pass.
3. UI ESLint passes.
4. Next.js production build passes and includes `/training`.
5. Starting the case allows the first event to arrive without pressing a fault/event injection control.
6. Pause stops the training clock.
7. 3x playback advances the training clock faster.
8. Skip-to-next-event advances deterministic pacing only.
9. The first event must be recorded before the scenario continues toward recurrence.
10. LA-T01 mechanism stays hidden until debrief.
11. Operator -> Maintenance handoff remains evidence-gated.
12. Unestablished instrumentation remains `NOT ASSUMED`.

## Rollback

Close the pull request without merge or revert the branch commits. This increment changes training UI pacing and documentation only.
