# Labeler OPC UA Canvas v1

Repository: `anthonyedgar30000/linealert-core`  
Base: `main@150c7d71b3d236dcf4b44bf6ac80353c680910de`  
Branch: `agent/labeler-opcua-canvas-v1`  
Tracking issue: #117

## Objective

Make the serious local Plant Canvas consume qualified read-only Labeler 2 OPC UA emulator
observations so the UI does not generate the machine evidence it later interprets.

## Repository reality inspected before implementation

- `main` resolved to merge commit `150c7d71b3d236dcf4b44bf6ac80353c680910de` (PR #116).
- No open pull requests were observed before branch creation.
- Main CI and GitHub Pages deployment for that commit were successful.
- Existing local OPC UA bridge/evidence code is read-only and preserves timestamps/status/freshness.
- Existing Microsoft OPC PLC mappings are generic proxies and are not sufficient to pretend they
  are Labeler 2 presentation/camera signals.
- Existing causal emulator precedent keeps simulator-private truth separate from observable output.
- Issue #31 remains a separate Microsoft OPC PLC + Azure IoT Operations lab workstream; this
  increment does not execute or broaden that Azure work.
- No physical Labeler 2 connection, OEM manual, commissioned machine profile, verified calibration
  package, or equipment-control path was observed.

## Permitted paths

- `.project/labeler-opcua-canvas-v1.md`
- `src/linealert_core/labeler_demo_opcua_server.py`
- `src/linealert_core/labeler_demo_bridge.py`
- `docs/triage/opcua-source-adapter.js`
- `docs/triage/index.html`
- `docs/index.html`
- `docs/opcua-labeler-canvas-demo.md`
- `tests/test_labeler_demo_opcua.py`
- `tests/test_labeler_demo_bridge.py`
- `tests/test_canvas_opcua_source.py`
- `pyproject.toml`

## Bounded behavior

- add a deterministic Labeler 2 observable OPC UA server with stable node IDs;
- add a local bridge that explicitly allow-lists those nodes and serves existing `docs/` plus
  `/api/telemetry`;
- auto-admit only the expected simulator profile, asset, simulator-only scope, read-only flag,
  semantic-admission flag, and good required signals;
- after admission, suppress browser machine telemetry and calendar machine incident generation;
- derive the synthetic concern from admitted presentation/camera evidence;
- require source-emitted diagnostic evidence for the trial result in OPC mode;
- count source-emitted qualifying batches during production verification;
- fail closed on disconnect/stale evidence and never silently fall back to browser machine evidence.

## Safety / authority limits

```text
simulator_value != verified_physical_state
telemetry != diagnosis
threshold_crossing != fault
source_mode != equipment_authority
emulator_private_truth != admitted_evidence
browser_workflow_state != machine_state
test_response != causal_proof
recommendation != authorized_action
```

No PLC write, OPC UA method call, physical equipment, production network, OEM procedure authority,
safety approval, or production authorization is introduced.

## Verification

Expected repository gates:

```text
ruff check .
pytest
```

Additional tests cover deterministic emulator phases, explicit node allow-list/type qualification,
source identity preservation on stale failure, Canvas source admission, browser-generation
suppression, fail-closed behavior, and public scenario-preview labelling.

Manual operational verification remains separate from CI:

```text
start emulator
→ start local bridge
→ open http://127.0.0.1:8775/triage/
→ observe OPC UA source banner and source-driven evidence
→ stop emulator
→ observe fail-closed stale/source-unavailable state
```

Passing CI verifies software contracts only. It does not establish a physical connection or
production readiness.

## Rollback

Close the pull request or revert these bounded files. No equipment rollback is required because the
increment is simulator-only and read-only.
