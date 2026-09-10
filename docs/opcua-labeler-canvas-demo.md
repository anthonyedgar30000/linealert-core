# OPC UA-driven Labeler 2 Plant Canvas

This is the serious local synthetic demo path for Plant Canvas. The browser does **not** generate
the Labeler 2 machine observations after the qualified OPC UA source is admitted.

The evidence path is:

```text
deterministic Labeler 2 emulator private state
        ↓ observable-only read-only OPC UA
local Labeler evidence bridge
        ↓ qualified /api/telemetry
Plant Canvas
        ↓
Event Log + Evolving Investigation
```

A separate localhost-only **simulator control channel** exists for demo actions such as stopping the
synthetic machine, recording a simulated operator guide observation, restoring the synthetic guide
to its reference, executing a diagnostic batch, and resuming synthetic production. Those controls
change only emulator state. They are not OPC UA writes and establish no equipment-control precedent.

The plant schedule, staffing, CMMS-style queue, operator workflow, and authority examples remain
synthetic context. Machine evidence in this mode comes from the OPC UA source.

## Run locally

From the repository root on Windows PowerShell:

```powershell
python -m pip install -e ".[opcua]"
```

Terminal 1:

```powershell
linealert-labeler-opcua-emulator --loop
```

Terminal 2:

```powershell
linealert-labeler-opcua-bridge
```

Then open:

```text
http://127.0.0.1:8775/triage/
```

The source banner should change from `SOURCE · SCENARIO PREVIEW` to
`SOURCE · LABELER 2 OPC UA EMULATOR · CONNECTED`.

The emulator defaults to:

```text
OPC UA evidence:       opc.tcp://127.0.0.1:4841/linealert/labeler2/
simulator controls:    http://127.0.0.1:4842
Canvas + bridge:       http://127.0.0.1:8775/triage/
qualified telemetry:   http://127.0.0.1:8775/api/telemetry
```

The bridge only forwards an explicit simulator-control allow-list to loopback HTTP. The browser
never receives an endpoint that can control physical equipment.

## Guide verification / restoration flow

The guide path is intentionally **verify first**:

```text
OPC UA concern evidence
→ enter stopped bounded diagnostic state in the simulator
→ Verify guide / spacing against approved setup reference
→ simulated operator observation is recorded with its own source identity
→ if within reference: do not offer a guide correction
→ if outside reference and demo authority permits: restore to approved reference
→ arm diagnostic trial
→ simulator emits the test result through OPC UA
→ LineAlert evaluates fresh evidence
```

The running emulator carries a private synthetic guide-offset state. A roll-change phase can place
the guide outside the synthetic reference. That private mechanism variable is **not** an OPC UA
node. The operator only learns the relationship by performing the simulated verification action.

The resulting guide observation is classified as `synthetic_human_observation`, not machine
telemetry. A restoration is classified as `simulator_control_only`. After restoration, LineAlert
does not directly set presentation variability, camera alignment, or quality values. The emulator
changes its own state and subsequent machine observations arrive through OPC UA.

If the guide is not restored, the diagnostic batch remains inconsistent with healthy behavior. If
the guide is restored in this bounded scenario, the emulator produces improved observable behavior.
That response supports the tested intervention under the synthetic conditions; it does not prove a
root cause or mechanism.

## What changes in OPC UA mode

Once a qualified Labeler 2 source has been admitted:

- calendar-seeded machine incidents are suppressed;
- browser-generated Labeler 2 telemetry is suppressed;
- the browser calendar incident fast-forward control is disabled;
- concern opening is driven by the admitted presentation/camera evidence gate;
- guide verification is a simulated human observation separate from OPC UA evidence;
- guide restoration is unavailable until a current out-of-reference observation exists;
- the HMI demo button asks the emulator to execute a diagnostic batch, whose result returns through
  OPC UA instead of being manufactured in the browser;
- production verification counts qualifying source batches;
- stopping the emulator makes the bridge retain the last values only as stale evidence and makes
  the Canvas suspend machine interpretation.

The Canvas does **not** silently fall back to browser-generated machine evidence after a live
emulator source has been admitted.

## Observable source contract

The emulator exposes only the bounded evidence set:

```text
EmulatorSequence
RunStateCode
LineSpeedCpm
PresentationIntervalStddevMs
CameraObservedContainers
CameraAlignedContainers
ApparentSkewEvents
MaxAbsAlignmentOffsetMm
AcceptedContainers
RejectCandidates
RollChangeRecent
```

There is deliberately no `GuideOffset`, `FaultTruth`, `RootCause`, or hidden-mechanism OPC UA node.
The current guide relationship becomes available only through the separate simulated operator
observation action.

`RunStateCode` is a synthetic HMI/MES-style context code:

```text
0 = stopped
1 = production
2 = diagnostic run
```

The initial concern gate is intentionally synthetic and demo-only: presentation variability at or
above 16 ms with at least five camera observations and aligned fraction at or below 0.8. It is not
an OEM threshold or production limit.

## Failure test

With the Canvas showing the connected OPC UA source, stop the emulator process while leaving the
bridge running.

Expected result:

```text
OPC UA disconnect
→ bridge connected:false
→ retained observations marked stale
→ Canvas SOURCE UNAVAILABLE · FAIL CLOSED
→ machine interpretation paused
→ no browser telemetry fallback
```

Restart the emulator. The bridge may reconnect and the Canvas can resume consuming new qualified
simulator evidence.

## Boundaries

```text
simulator_value != verified_physical_state
telemetry != diagnosis
threshold_crossing != fault
simulated_human_observation != verified_physical_state
verification_only != authorization_to_adjust
simulator_control != equipment_control
browser_workflow_state != machine_state
test_response != causal_proof
recommendation != authorized_action
successful_test != safe_production_change
```

This path is localhost-only and simulator-only. OPC UA remains read-only. The separate demo-control
channel is explicitly restricted to loopback and synthetic state. It adds no physical equipment
connection, PLC write, OPC UA method call, production-network access, OEM procedure authority,
safety approval, or production authorization.

The public GitHub Pages build cannot consume the localhost bridge and therefore remains an
explicitly labelled scenario preview.
