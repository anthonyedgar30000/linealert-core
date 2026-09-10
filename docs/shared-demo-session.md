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
- production-verification streak and recovery state
- bounded workflow state needed to resume the Plant Canvas
- synthetic production counters and handled incident identities

`localStorage` preserves state across same-tab navigation. `BroadcastChannel` plus the browser `storage` event provide best-effort cross-tab refresh.

When returning to the Plant Canvas after briefly viewing the guide, the adapter advances the session by bounded wall-clock elapsed time before rendering. The static simulator therefore does not intentionally reset to 14:00 merely because the user opened the reference page.

## Preserved baseline pages

The pre-sync PR #102 pages are retained as static baselines:

- `docs/triage/plant-canvas-v102.html`
- `docs/troubleshooting-guide-reference-v102.html`

The public route wrappers load those preserved pages and attach the shared-session adapters. This keeps the synchronization increment bounded and avoids silently rewriting the already-demonstrated plant and troubleshooting behavior. A later runtime migration should replace this compatibility layer with application/domain state.

## Boundaries

- Browser session snapshot != plant record.
- Shared demo state != CMMS truth.
- Simulated elapsed time != verified machine chronology.
- Telemetry != diagnosis.
- Recommendation != authorization or equipment command.
- Historical pattern != current root cause.
- Five-container response != safe production change.
- Production recovery criteria != proof of root cause or future reliability.

No equipment control, autonomous dispatch, safety approval, or production persistence path is introduced by this static synchronization layer.
