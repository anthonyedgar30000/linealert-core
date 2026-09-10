# OPC UA-driven Labeler 2 Plant Canvas

This is the serious local synthetic demo path for Plant Canvas. The browser does **not** generate
the Labeler 2 machine observations after the qualified OPC UA source is admitted.

The data path is:

```text
deterministic Labeler 2 observable emulator
        ↓ read-only OPC UA
local Labeler evidence bridge
        ↓ qualified /api/telemetry
Plant Canvas
        ↓
Event Log + Evolving Investigation
```

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

The source banner should change from:

```text
SOURCE · SCENARIO PREVIEW
```

to:

```text
SOURCE · LABELER 2 OPC UA EMULATOR · CONNECTED
```

The bridge exposes the current admitted snapshot at:

```text
http://127.0.0.1:8775/api/telemetry
```

## What changes in OPC UA mode

Once a qualified Labeler 2 source has been admitted:

- calendar-seeded machine incidents are suppressed;
- browser-generated Labeler 2 telemetry is suppressed;
- the synthetic incident fast-forward control is disabled;
- concern opening is driven by the admitted presentation/camera evidence gate;
- trial result capture waits for an externally emitted diagnostic batch instead of manufacturing
  a result in the browser;
- production verification counts qualifying source batches;
- stopping the emulator makes the bridge retain the last values only as stale evidence and makes
  the Canvas suspend machine interpretation.

The Canvas does **not** silently fall back to browser-generated machine evidence after a live
emulator source has been admitted.

## Observable source contract

The emulator exposes only the initial bounded set required by this vertical slice:

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

These are synthetic observable values. The emulator's internal phase selection is not published as
a causal answer and there is no hidden fault/root-cause node.

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
browser_workflow_state != machine_state
test_response != causal_proof
recommendation != authorized_action
successful_test != safe_production_change
```

This path is localhost-only, simulator-only, and read-only. It adds no physical equipment
connection, PLC write, OPC UA method call, production-network access, OEM procedure authority,
safety approval, or production authorization.

The public GitHub Pages build cannot consume the localhost bridge and therefore remains an
explicitly labelled scenario preview.
