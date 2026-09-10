# OPC UA connection / evidence-admission state v1

Repository: `anthonyedgar30000/linealert-core`  
Base: `main@2e2896989452fbfb5de874b1d94e9fcef4400759`  
Branch: `agent/opcua-connection-admission-state-v1`

## Objective

Correct the localhost Plant Canvas source-status model so an OPC UA transport disconnect, a connected-but-unqualified evidence sample, and an unavailable browser-to-bridge telemetry path are represented as different states while all non-qualified states continue to fail closed for machine interpretation.

## Repository reality inspected before implementation

- `main` resolved to `2e2896989452fbfb5de874b1d94e9fcef4400759`, the merge commit for PR #121.
- No open pull requests were observed before branch creation.
- Issue #31 remains the only open issue and is unrelated to this localhost Labeler demo repair.
- Post-merge CI run `34475677933` completed successfully on the exact current `main` commit.
- Post-merge GitHub Pages run `34475677979` completed successfully on the exact current `main` commit.
- `.project/active-work.json` remains an older coordination snapshot and explicitly defers to live GitHub lifecycle and exact-head evidence.
- `docs/opcua-labeler-canvas-demo.md` defines a true emulator disconnect as bridge `connected:false` and requires fail-closed browser behavior.
- No physical Labeler 2 connection, OEM manual, commissioned machine profile, verified calibration package, production-network path, or equipment-control authority was observed.

## Triggering observation

During the PR #121 localhost acceptance test, the operator reported that the OPC UA emulator appeared to connect and disconnect repeatedly in Plant Canvas. A subsequent 30-sample PowerShell check of `/api/telemetry` over roughly fifteen seconds showed every sampled payload as:

```text
connected=True
reason=EVIDENCE.OPCUA_SAMPLE_QUALIFIED
run_state_code=1
emulator_sequence advancing normally
```

That sample establishes that the bridge reported a continuously connected, qualified source during the captured interval. It does not prove that no transient condition occurred outside that interval.

Code inspection found that, after initial source admission, the browser mapped **every** non-qualified telemetry payload to the same `UNAVAILABLE` presentation even when `payload.connected === true`. Browser fetch failures were also presented as source unavailable, which inferred an OPC UA connection state that the browser did not actually know.

## Bounded change

Only the browser source-state classification, its contract tests, and its local demo documentation are changed.

The Canvas now distinguishes:

```text
qualified
connected_unqualified
disconnected
bridge_unavailable
```

Semantics:

- `qualified`: `connected:true`, expected source identity/scope, semantic admission true, and all required signals good;
- `connected_unqualified`: bridge payload explicitly reports `connected:true`, but source identity/admission/signal qualification does not satisfy the LineAlert evidence gate;
- `disconnected`: bridge payload explicitly reports `connected:false`;
- `bridge_unavailable`: the browser cannot obtain a usable telemetry payload, so OPC UA connection state is unknown.

All states except `qualified` suspend machine interpretation, disable bounded workflow controls, and preserve the existing no-browser-fallback rule.

## Operator-facing expected observations

```text
normal admitted source
→ SOURCE · LABELER 2 OPC UA EMULATOR · CONNECTED
→ connected · qualified

connected source with unqualified evidence
→ SOURCE · LABELER 2 OPC UA EMULATOR · CONNECTED
→ connected · evidence unqualified
→ EVIDENCE UNQUALIFIED · INTERPRETATION PAUSED

confirmed OPC UA disconnect
→ SOURCE · LABELER 2 OPC UA EMULATOR · DISCONNECTED
→ SOURCE DISCONNECTED · FAIL CLOSED

browser/bridge telemetry failure
→ SOURCE · LOCAL OPC UA BRIDGE · UNAVAILABLE
→ BRIDGE UNAVAILABLE · FAIL CLOSED
→ OPC UA connection state unknown
```

The asset run-state wording is also normalized to `LABELER 2 ... · OPC UA CONNECTED` when qualified evidence supplies a run-state code.

## Boundaries

```text
connection_state != evidence_admission_state
unqualified_sample != disconnected_source
bridge_unavailable != proven_opcua_disconnect
connected != evidence_qualified
evidence_qualified != physical_state_verified
telemetry != diagnosis
recommendation != authorized_action
browser_workflow_state != machine_state
```

No emulator progression, OPC UA server behavior, bridge polling, simulator control, plant-event chronology, evidence threshold, PLC write, OPC UA method call, physical equipment connection, OEM authority, safety approval, or production authorization is changed.

## Tests

Repository gates:

```text
ruff check .
pytest
UI lint/build
```

Targeted assertions verify that:

- connected-but-unqualified payloads use `markConnectedUnqualified`;
- explicit `connected:false` payloads use `markDisconnected`;
- browser telemetry errors use `markBridgeUnavailable` without claiming OPC UA disconnected;
- status exposes separate `availabilityState`, `connected`, and `admitted` fields;
- browser machine generation remains suppressed after OPC UA admission;
- confirmed disconnect still fails closed;
- source-side orchestration and guide workflow contracts remain unchanged.

## Local verification after merge

1. Run the emulator and bridge normally and confirm stable `connected · qualified` presentation.
2. Stop only the emulator while leaving the bridge running; expect `SOURCE DISCONNECTED · FAIL CLOSED`.
3. Restart the emulator; expect recovery to `connected · qualified` without browser machine-evidence fallback.
4. If an evidence-admission transient occurs while bridge payloads still report `connected:true`, expect `connected · evidence unqualified`, not a disconnect claim.
5. If practical, stop only the local bridge while leaving the emulator running; expect `LOCAL OPC UA BRIDGE · UNAVAILABLE` and an unknown OPC UA connection state.

## Failure modes

- A real source disconnect may still occur; this change does not mask `connected:false`.
- A connected source may produce repeated unqualified evidence; the UI will remain fail closed and expose that as an evidence-admission problem rather than a transport disconnect.
- A browser or bridge failure may prevent any source-state determination; the UI reports that uncertainty explicitly.
- This change does not identify the cause of any future unqualified sample. Signal reason codes and bridge/emulator evidence remain required for that diagnosis.

## Rollback

Revert the files in this increment. No equipment rollback is required because the change is browser presentation/state classification only and does not modify simulator or equipment behavior.
