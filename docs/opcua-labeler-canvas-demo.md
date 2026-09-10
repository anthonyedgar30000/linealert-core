# OPC UA-driven Labeler 2 Plant Canvas

This is the serious local synthetic demo path for Plant Canvas. The browser does **not** generate
the Labeler 2 machine observations after the qualified OPC UA source is admitted.

The local path is:

```text
shared deterministic Labeler 2 plant-event model
        ├─ recorded changeover / CMMS-style events
        └─ private simulator setup outcome
                    ↓
         Labeler 2 emulator state
                    ↓ observable-only read-only OPC UA
         local Labeler evidence bridge
                    ↓ qualified /api/telemetry
              Plant Canvas
                    ↓
         Event Log + Investigation
```

The work record and the later machine behavior can therefore originate from the same simulated
plant event without making the work record a diagnosis. A recorded roll change can precede healthy
operation, a deviation corrected during first-off checks, or an escaped setup deviation. LineAlert
still has to interpret the subsequently observed evidence.

## Run locally

From the repository root on Windows PowerShell:

```powershell
python -m pip install -e ".[opcua]"
```

Terminal 1:

```powershell
python -m linealert_core.labeler_demo_opcua_server --loop
```

Terminal 2:

```powershell
python -m linealert_core.labeler_demo_bridge
```

Then open:

```text
http://127.0.0.1:8775/triage/
```

Local endpoints:

```text
OPC UA evidence:       opc.tcp://127.0.0.1:4841/linealert/labeler2/
simulator controls:    http://127.0.0.1:4842
Canvas + bridge:       http://127.0.0.1:8775/triage/
qualified telemetry:   http://127.0.0.1:8775/api/telemetry
plant event feed:      http://127.0.0.1:8775/api/plant-events
```

## Deterministic roll-change population

The demo uses a fixed seed and the following **synthetic demo prior** for roll-change execution:

```text
92% clean
 4% deviation caught / corrected during first-off checks
 4% escaped setup deviation that can later produce observable instability
```

This is a scenario-design prior, not a measured Speedway, OEM, site, technician, or industry failure
rate. The fixed seed makes the same cycles reproduce the same outcomes. Most roll changes are
therefore deliberately boring.

Every cycle can publish the same outward record:

```text
Labeler 2 stopped for scheduled label roll change
Label roll change completed
Labeler 2 resumed after recorded roll change
```

The ordinary completion record does not contain the private outcome. If a deviation is caught, an
additional first-off correction record is allowed because that correction is itself an observed /
recorded plant action. If the deviation escapes, there is no event saying “bad roll change”; only
later observable machine behavior can make the episode interesting.

## Source-side fast-forward

When the OPC UA source is active and there is no open workflow, Plant Canvas offers:

```text
Fast-forward to next concern precursor
```

That button does not manufacture a concern in the browser. It asks the simulator control API to
advance the **source timeline** to just before the next deterministic escaped-changeover episode.
The emulator then continues normally through the scheduled changeover, private state transition,
OPC UA observations, and concern gate.

The current source model uses ten synthetic seconds per scenario sequence. Fast-forward lands two
steps (twenty synthetic seconds) before the consequential roll-change completion when approaching a
future affected cycle. If the affected changeover is already unfolding, it may instead advance to
the later concern precursor without moving backward.

Plant Canvas follows the source sequence for accelerated plant-time progression and ingests the
emulator-owned plant event feed into the shared Event Log. Skipped public events are preserved by
the source event ledger rather than silently disappearing.

```text
fast-forward request != concern injection
source event chronology != causal proof
recorded roll change != failed roll change
recent change != current root cause
```

## Guide verification / restoration flow

The guide path remains verify-first:

```text
OPC UA concern evidence
→ Stop Labeler 2 for bounded diagnostic
→ wait for qualified OPC UA to report Labeler 2 stopped
→ Verify guide / spacing against approved setup reference
→ simulated operator observation recorded with its own source identity
→ if within reference: do not offer a guide correction
→ if outside reference and demo authority permits: restore to approved reference
→ arm diagnostic trial
→ simulator emits the test result through OPC UA
→ LineAlert evaluates fresh evidence
```

The running emulator carries a private synthetic guide-offset state. That mechanism variable is
**not** an OPC UA node. The operator only learns the guide/reference relationship by performing the
simulated verification action.

After restoration, LineAlert does not directly set presentation variability, camera alignment, or
quality values. The emulator changes its own state and subsequent observations arrive through OPC
UA. Improvement after the intervention supports the tested action under the synthetic conditions;
it does not prove the mechanism.

## What changes in OPC UA mode

Once a qualified Labeler 2 source has been admitted:

- calendar-seeded browser machine incidents and Labeler telemetry are suppressed;
- the old browser-calendar fast-forward is replaced by source-side simulator fast-forward;
- emulator-owned roll-change / CMMS-style records are ingested into the shared Event Log;
- recent-recorded-context for an OPC concern prefers the source-owned roll-change record;
- concern opening is driven by the admitted presentation/camera evidence gate;
- guide verification is a simulated human observation separate from OPC UA evidence;
- guide restoration is unavailable until a current out-of-reference observation exists;
- diagnostic test results return through OPC UA instead of being manufactured in the browser;
- production verification counts qualifying source batches;
- source disconnect fails closed without browser machine-evidence fallback.

## Connection state and evidence admission

OPC UA transport state and LineAlert evidence admission are separate dimensions. The Canvas must not
claim the source disconnected merely because one telemetry snapshot is not admissible.

The local UI classifies source state as:

```text
bridge connected + payload connected:true + evidence admitted
→ SOURCE CONNECTED · QUALIFIED

bridge connected + payload connected:true + evidence not admitted
→ SOURCE CONNECTED · EVIDENCE UNQUALIFIED
→ machine interpretation paused

bridge connected + payload connected:false
→ SOURCE DISCONNECTED · FAIL CLOSED
→ machine interpretation paused

browser cannot read /api/telemetry
→ LOCAL BRIDGE UNAVAILABLE · FAIL CLOSED
→ OPC UA connection state unknown
→ machine interpretation paused
```

Every non-qualified state still fails closed for machine interpretation and never re-enables browser
generated machine evidence. The distinction is about preserving source truth: an evidence-quality
problem, a confirmed OPC UA disconnect, and a browser-to-bridge failure are not the same condition.

```text
connection_state != evidence_admission_state
bridge_unavailable != proven_opcua_disconnect
unqualified_sample != disconnected_source
```

## Observable source contract

The OPC UA emulator exposes only:

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

There is deliberately no `GuideOffset`, `FaultTruth`, `RootCause`, roll-change outcome, or hidden
mechanism OPC UA node.

`RunStateCode` is a synthetic HMI/MES-style context code:

```text
0 = stopped
1 = production
2 = diagnostic run
```

A scheduled roll-change stop may report `0` while source scenario time continues through the planned
changeover. An explicit bounded diagnostic stop freezes production/scenario sequence until a trial
or resume action. These are different simulator states.

The concern gate remains synthetic and demo-only: presentation variability at or above 16 ms with
at least five camera observations and aligned fraction at or below 0.8.

## Failure test

With the Canvas showing the connected OPC UA source, stop the emulator process while leaving the
bridge running. Expected result:

```text
OPC UA disconnect
→ bridge connected:false
→ retained observations marked stale
→ Canvas SOURCE DISCONNECTED · FAIL CLOSED
→ machine interpretation paused
→ no browser telemetry fallback
```

A separate admission test should keep the bridge and OPC UA connection alive while returning an
unqualified required signal or semantic admission result. Expected result:

```text
bridge connected:true
→ OPC UA connection remains reported connected
→ evidence is not admitted
→ Canvas SOURCE CONNECTED · EVIDENCE UNQUALIFIED
→ machine interpretation paused
→ no browser telemetry fallback
```

If the browser cannot read `/api/telemetry`, the Canvas reports the local bridge unavailable and does
not infer that OPC UA itself disconnected.

## Boundaries

```text
simulator_value != verified_physical_state
telemetry != diagnosis
threshold_crossing != fault
work_record != causal_proof
historical_pattern != current_root_cause
control_acknowledgment != verified_source_state
simulated_human_observation != verified_physical_state
verification_only != authorization_to_adjust
simulator_control != equipment_control
browser_workflow_state != machine_state
connection_state != evidence_admission_state
bridge_unavailable != proven_opcua_disconnect
test_response != causal_proof
recommendation != authorized_action
successful_test != safe_production_change
```

This path is localhost-only and simulator-only. OPC UA remains read-only. The public GitHub Pages
build cannot consume the localhost bridge and remains an explicitly labelled scenario preview.
