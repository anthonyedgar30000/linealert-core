# Plant-event orchestration + source fast-forward v1

Repository: `anthonyedgar30000/linealert-core`  
Base: `main@efcf57809026e6357e62677dd9b9033e6a3f35c6`  
Branch: `agent/plant-event-orchestration-fast-forward-v1`

## Objective

Move Labeler 2 demo event timing and consequential roll-change behavior into the localhost simulator so Plant Canvas consumes one source-owned synthetic plant chronology instead of combining an OPC UA machine source with browser-owned machine incidents.

## Repository reality inspected before implementation

- `main` resolved to `efcf57809026e6357e62677dd9b9033e6a3f35c6` after PR #120.
- No open pull requests were observed before branch creation.
- PR #120 CI and Pages deployment were successful.
- Issue #117 was closed after the operator reported the full localhost stop/inspect/restore/diagnostic/resume smoke test worked successfully.
- Issue #31 remains open and unrelated; it tracks the Microsoft OPC PLC + Azure IoT Operations lab.
- Existing Labeler 2 OPC UA evidence remained read-only and simulator-only; bounded demo controls remained loopback-only.
- No physical Labeler 2 connection, OEM manual, commissioned machine profile, verified calibration package, production-network path, or equipment-control authority was observed.
- `.project/active-work.json` is a historical coordination snapshot; live GitHub lifecycle and current branch evidence supersede cached current claims.

## Bounded change

- add a deterministic simulator-owned plant-event model for Labeler 2 roll changes;
- use a declared seeded demo prior of 92% clean, 4% caught during first-off verification, and 4% escaped setup deviation over the reference window;
- keep the private changeover outcome inside the simulator and never publish it as OPC UA evidence or CMMS truth;
- emit outwardly recordable synthetic HMI/CMMS chronology separately from private mechanism state;
- make clean roll changes remain healthy, caught deviations return to reference during first-off, and escaped deviations become observable only through later machine evidence;
- add a loopback simulator event feed and proxy it through the existing local bridge;
- ingest source-owned plant events into the shared Event Log without replacing source identity or clock-quality classification;
- add source-side fast-forward that advances the simulator to just before the next consequential escaped-changeover precursor rather than manufacturing a concern in the browser;
- preserve crossed public plant events during fast-forward;
- keep Canvas concern opening driven by qualified OPC UA presentation/camera evidence;
- use asset-centric workflow text such as `Stop Labeler 2 for bounded diagnostic` and make source connection/state wording unambiguous.

## Demo-prior boundary

The 92/4/4 distribution is a deterministic **synthetic demo prior** selected to provide many normal changeovers plus occasional caught and escaped examples. It is not a measured Speedway, OEM, packaging-industry, operator, or maintenance failure rate and must not be promoted as one.

## Expected source chronology

```text
normal production
→ scheduled Labeler 2 roll-change stop
→ CMMS-style `Label roll change completed`
→ production resumes
→ clean/caught outcomes remain healthy OR escaped private deviation persists
→ observable OPC UA behavior evolves
→ LineAlert concern opens only if the admitted evidence crosses its synthetic gate
```

Fast-forward changes source pacing only:

```text
Canvas pacing request
→ loopback simulator control
→ simulator advances its own plant sequence
→ crossed public plant events are retained
→ target lands before the next consequential changeover/concern precursor
→ normal source cadence resumes
→ OPC UA observations unfold naturally
```

## Boundaries

```text
plant_event != diagnosis
cmms_record != causal_proof
private_simulator_outcome != published_evidence
historical_pattern != current_root_cause
fast_forward != fault_injection
control_acknowledgment != verified_source_state
telemetry != diagnosis
model_match != proof
simulator_control != equipment_control
synthetic_demo_prior != measured_failure_rate
```

No PLC write, OPC UA method call, physical equipment connection, production-network access, OEM procedure authority, safety approval, or production authorization is introduced.

## Verification

Repository gates:

```text
ruff check .
pytest
UI lint/build
```

Targeted contracts include:

- deterministic 92/4/4 seeded reference distribution;
- public roll-change records do not reveal private simulator outcome;
- clean and caught changeovers remain healthy at the concern window;
- escaped changeovers degrade only through observable machine evidence;
- source fast-forward selects the next escaped-changeover precursor and preserves crossed public events;
- explicit diagnostic stop still blocks source fast-forward;
- bridge control allow-list and event proxy remain loopback-only;
- Canvas loads the orchestration adapter after the OPC UA source adapter;
- browser machine incident generation remains suppressed after OPC UA source admission;
- source-owned events retain source identity and deterministic simulator clock-quality metadata.

Passing CI establishes software contracts only. A fresh localhost run after merge should verify the visible sequence from fast-forward through changeover, OPC UA evidence evolution, concern opening, and the existing bounded diagnostic workflow.

## Rollback

Revert the files in this increment. No equipment rollback is required because all new behavior remains simulator-only, localhost-only, and read-only at the OPC UA evidence surface.
