# Verify then restore guide / spacing through the Labeler OPC UA demo

Repository: `anthonyedgar30000/linealert-core`  
Base: `main@4148b6e30d411c705ea794ffa7c4d60f5d19f2bb`  
Branch: `agent/verify-restore-guide-opcua-v1`  
Tracking issue: #117

## Objective

Replace the OPC-UA demo's implicit "restore guide and numbers improve" behavior with a bounded
verify-first workflow in which a simulated operator observation may justify one simulator-only
restoration, after which the emulator itself produces the fresh machine evidence through OPC UA.

## Repository reality inspected before implementation

- Resolved repository: `anthonyedgar30000/linealert-core`, public, default branch `main`.
- Current `main` is merge commit `4148b6e30d411c705ea794ffa7c4d60f5d19f2bb` (PR #118).
- No open pull requests were observed before branch creation.
- Current-main CI and GitHub Pages deployment for PR #118's merge were observed successful.
- Issue #117 remains open because localhost operational smoke verification is still required.
- `.project/active-work.json` is a time-bounded older snapshot; live GitHub supersedes its stale
  PR #115-era active-work fields.
- Existing Labeler 2 OPC UA surface is read-only and explicitly allow-listed.
- Existing action authority separates `verify-guide-spacing` as verification-only.
- Existing synthetic Speedway route already names guide verification before its default
  intervention, but the intervention wording is not yet conditional enough.
- No physical Labeler 2 connection, OEM manual, commissioned machine profile, calibration package,
  production control path, or equipment authority was observed.

## Permitted paths

- `.project/verify-restore-guide-opcua-v1.md`
- `src/linealert_core/labeler_demo_opcua_server.py`
- `src/linealert_core/labeler_demo_bridge.py`
- `docs/triage/guide-control-adapter.js`
- `docs/triage/index.html`
- `docs/opcua-labeler-canvas-demo.md`
- `profiles/synthetic-labeler2-action-authority-v1.json`
- `profiles/speedway-labeler-troubleshooting-v1.routes.json`
- `tests/test_labeler_demo_opcua.py`
- `tests/test_labeler_demo_bridge.py`
- `tests/test_canvas_opcua_source.py`
- `tests/test_guide_action_authority.py`

## Bounded behavior

- keep the OPC UA node surface observable-only; do not expose private guide offset;
- introduce private synthetic guide/reference state in the emulator;
- introduce a localhost-only simulator-control channel separate from OPC UA;
- require stopped diagnostic state before simulated guide inspection;
- classify the inspection result as a synthetic human observation with source identity;
- refuse guide restoration unless the latest matching observation is out of reference;
- keep restoration a synthetic bounded material change, not a machine command;
- make diagnostic-batch and later production observations depend on emulator state rather than UI
  result injection;
- route HMI demo actions to the emulator control channel and receive results back only through OPC
  UA machine evidence;
- preserve fail-closed OPC UA source behavior from PR #118.

## Safety / authority limits

```text
simulator_value != verified_physical_state
simulated_human_observation != verified_physical_state
verification_only != authorization_to_adjust
simulator_control != equipment_control
telemetry != diagnosis
threshold_crossing != fault
intervention_followed_by_improvement != proof_of_mechanism
recommendation != authorized_action
successful_test != safe_production_change
```

The simulator-control channel is loopback-only and uses HTTP specifically to keep it separate from
the read-only OPC UA evidence contract. No OPC UA write, method call, physical equipment action,
production-network access, OEM procedure claim, safety approval, or production authorization is
introduced.

## Verification

Repository gates:

```text
ruff check .
pytest
```

Targeted contracts additionally verify:

- private guide state never appears in `NODE_IDS`;
- restore is rejected before a matching out-of-reference inspection;
- unchanged guide state keeps a diagnostic batch degraded;
- restored guide state changes later observable diagnostic evidence;
- simulator controls are explicit allow-list entries and loopback-only;
- Canvas loads the guide-control adapter after OPC source admission support;
- guide UI performs stop -> inspect -> conditional restore -> diagnostic batch -> OPC evidence;
- authority profile separates verification-only from bounded restoration.

Operational verification remains separate from CI and requires the local two-process emulator /
bridge smoke test. Passing CI does not establish physical-machine truth or production readiness.

## Rollback

Revert this bounded increment. No equipment rollback is required because all new action effects are
simulator-only and the OPC UA evidence path remains read-only.
