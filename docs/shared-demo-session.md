# Shared synthetic demo session

## Scope

The GitHub Pages Plant Canvas and labeling troubleshooting guide are two views of one controlled synthetic demo session.

The Plant Canvas remains the source view for the synthetic plant state. It publishes a browser-local snapshot. The guide consumes that snapshot and presents the same simulated date/time, shift, active incident, evidence, ranked bounded action, latest five-container result, production-verification state, and recovery state.

This is a static-demo compatibility mechanism only. It is not the production persistence architecture.

## Browser contract

`docs/demo-session.js` stores schema version `1` under:

`linealert.synthetic.demo-session.v1`

The snapshot is classified `synthetic_demo_only` and includes:

- simulated absolute time and shift identity
- current plant posture and run mode
- current synthetic incident identity and evidence
- current recommended bounded action
- latest confirmed five-container trial
- trial-discipline state: completed trials, pending experimental change, explicit restore requirement, and retained verified intermediate changes
- production-verification streak and recovery state
- bounded workflow state needed to resume the Plant Canvas
- synthetic production counters and handled incident identities

`localStorage` preserves state across same-tab navigation. `BroadcastChannel` plus the browser `storage` event provide best-effort cross-tab refresh.

When returning to the Plant Canvas after briefly viewing the guide, the adapter advances the session by bounded wall-clock elapsed time before rendering. The static simulator therefore does not intentionally reset to 14:00 merely because the user opened the reference page.

## Trial configuration discipline

The synthetic troubleshooting loop defaults to one new material difference from the last verified intermediate state.

An unverified change is not silently stacked with another change. If a trial is ineffective, adverse, merely diagnostic, or otherwise does not earn retention, LineAlert recommends an explicit restore of that one changed setting. The operator performs the restore within the synthetic HMI workflow and a fresh five-container verification must represent the restored state before another material change is introduced.

A promising material change remains experimental until a no-change repeat reproduces the improvement. Only then can the change be classified as a retained verified intermediate state. A later stacked trial may build from that state, but it still introduces only one additional material difference at a time.

The demo never performs an automatic equipment restore. A restore recommendation is a recommendation, not an equipment command or authorization.

## Diagnostic versus maintenance response

The preserved PR #102 baseline used `mode === 'diagnostic'` as a shortcut for both a diagnostic workflow state and a zero-minute maintenance response. Its diagnostic schedule branch then rendered **MAINTENANCE · On response** even when the synthetic crew view showed no active work and no maintenance dispatch had been recorded.

`docs/triage/maintenance-response-adapter.js` separates those concepts for the public demo. Diagnostic mode no longer forces the maintenance availability estimate to zero and no longer presents maintenance as being on response. Until the demo records an explicit dispatch, the diagnostic view shows **MAINTENANCE SUPPORT · Not dispatched** while crew-derived availability remains visible in the operations context.

This is a presentation/state-model correction only. It does not assert that maintenance is unnecessary, authorize an operator action, or infer a physical machine state. A future dispatch workflow should record response ownership explicitly rather than infer it from diagnostic mode.

## Maintenance observation gate

`docs/triage/maintenance-observe-adapter.js` adds an asset-scoped interpretation gate for Labeler 2. When the synthetic CMMS schedule contains an active work order whose asset identity is exactly `Labeler 2`, LineAlert remains connected for telemetry and event capture but normal production interpretation is suspended for that asset.

While the work order is active, the public demo suppresses new normal-production concern triggering, blocks entry into new diagnostic trials, pauses production-recovery verification counting, disables incident fast-forward, and replaces the action card with **Maintenance in progress · normal recommendations paused**. The Canvas labels the state **MAINTENANCE · OBSERVE ONLY** rather than pretending that maintenance-period measurements belong to the production envelope.

An existing concern is not deleted or rewritten merely because maintenance begins. Its evidence and chronology remain preserved; LineAlert simply stops treating maintenance-period observations as ordinary production evidence. Maintenance work itself is context, not proof of the machine's physical condition or of the concern's cause.

This bounded increment does not yet commission a return-to-service verification procedure. Maintenance completion therefore does not establish a healthy machine, and a production deployment must use an explicit asset-specific return-to-service gate before normal production interpretation is treated as authoritative again.

## Post-recovery fast-forward handoff

When the configured 50-container production verification completes, the incident is closed and recovery remains visible as the just-completed episode. Any stale fast-forward target/event from the earlier incident is cleared at recovery completion.

If the user then chooses **Speed up to next incident**, the browser demo first leaves the recovered episode projection and returns the Canvas to normal monitoring before selecting the next unhandled calendar-seeded concern. The closed incident identity remains in `handledIncidentIds` and its chronology remains in history/Event Log evidence; only the live projection is cleared. This prevents a completed verification from poisoning or reusing the previous fast-forward target.

This handoff is UI/session behavior only. It does not delete plant evidence, alter equipment state, or reinterpret the completed recovery as proof of cause.

## Preserved baseline pages

The pre-sync PR #102 pages are retained as static baselines:

- `docs/triage/plant-canvas-v102.html`
- `docs/troubleshooting-guide-reference-v102.html`

The public route wrappers load those preserved pages and attach the shared-session and trial-discipline adapters. This keeps the increments bounded and avoids silently rewriting the already-demonstrated plant and troubleshooting behavior. A later runtime migration should replace this compatibility layer with application/domain state.

## Boundaries

- Browser session snapshot != plant record.
- Shared demo state != CMMS truth.
- Simulated elapsed time != verified machine chronology.
- Telemetry != diagnosis.
- Recommendation != authorization or equipment command.
- Diagnostic state != maintenance dispatch.
- Maintenance activity != normal production context.
- Maintenance completion != verified return to service.
- Restore recommendation != automatic equipment restore.
- Historical pattern != current root cause.
- Verified intermediate state != root-cause proof.
- Five-container response != safe production change.
- Production recovery criteria != proof of root cause or future reliability.

No equipment control, autonomous dispatch, safety approval, or production persistence path is introduced by this static synchronization layer.
