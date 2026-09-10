# OPC UA Canvas render ownership v1

Repository: `anthonyedgar30000/linealert-core`  
Base: `main@f92dbf1e199e335e1206c361e39a0ff3417edffd`  
Branch: `agent/opcua-canvas-render-ownership-v1`

## Triggering observation

During localhost acceptance after PR #122, two screenshots of the same running Labeler 2 state showed Plant Canvas machine cards alternating between browser-synthetic wording (`Running`, `Running · normal`) and OPC-source wording (`Context · no mapped OPC UA signal`, `Source reports production`). The right-hand asset panel also showed `RECOVERED` while its headline was repeatedly rewritten back to `Alignment variability emerging`.

Code inspection confirmed two browser-side ownership conflicts:

1. the preserved baseline calls `updateModeLabels()` every second and writes the same machine-card DOM fields that the OPC UA source adapter refreshes every 500 ms;
2. `event-context-adapter.js` rewrites the guide incident headline every 500 ms whenever `currentIncident` exists, including after `incident` has been closed by recovery.

This is a presentation/render-state defect. No evidence observed in the screenshots establishes an OPC UA transport fault, emulator state fault, or fast-forward fault.

## Bounded change

- add `opcua-render-ownership-adapter.js` after OPC UA source admission;
- allow the baseline renderer to continue updating workflow lifecycle fields such as `assetState`, then immediately reapply source-owned machine-card and run-mode labels when the OPC source has ever been admitted;
- preserve distinct paused-source labels for connected-but-unqualified, disconnected, and bridge-unavailable states;
- keep baseline rendering unchanged before OPC UA source admission;
- guard event-context headline rewrites so they occur only while the guide incident is actively open;
- keep recent recorded context available after recovery without rewriting the recovered headline;
- add repository contract tests for load order, machine-card ownership, paused states, and recovered headline behavior.

## Ownership model

```text
calendar / staffing / work orders / workflow lifecycle
→ preserved Canvas baseline

qualified Labeler 2 machine-card state + run-mode text
→ OPC UA source render ownership

active incident vocabulary + recent recorded context
→ event-context adapter

closed/recovered headline
→ workflow recovery state; historical context must not overwrite it
```

## Boundaries

```text
browser_calendar_state != machine_state
render_refresh != new_evidence
current_incident_record != currently_open_incident
historical_context != active_concern
telemetry != diagnosis
source_connected != source_qualified
recovery_observed != root_cause_proven
```

No emulator progression, bridge behavior, OPC UA transport, source admission rule, plant-event chronology, fast-forward target selection, concern threshold, control request, physical equipment connection, PLC write, OPC UA method call, safety approval, OEM authority, or production authorization is changed.

## Verification

Repository gates remain:

```text
ruff check .
pytest
UI lint/build
```

Targeted acceptance after merge:

1. run emulator + bridge with qualified OPC UA source;
2. watch Plant Canvas machine cards for at least several baseline clock cycles;
3. verify they remain source-owned and do not alternate back to browser `Running` wording;
4. run the concern/recovery workflow;
5. verify a recovered panel keeps the recovery headline while recent recorded context may remain visible;
6. verify disconnected/unqualified/bridge-unavailable states remain fail-closed and are not overwritten by the baseline renderer.

## Rollback

Revert this increment. No equipment rollback is required because the change is browser-side rendering only in the localhost/static synthetic demo surface.
