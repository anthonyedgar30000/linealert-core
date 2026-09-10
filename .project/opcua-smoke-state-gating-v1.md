# OPC UA smoke-test state gating v1

Repository: `anthonyedgar30000/linealert-core`  
Base: `main@adc77f2876a6f8367ca506ef88794e745322b830`  
Branch: `agent/opcua-smoke-state-gating-v1`  
Tracking issue: #117

## Objective

Resolve two defects exposed by the first localhost OPC UA smoke test:

1. Plant Canvas offered the guide/spacing observation while qualified OPC UA still reported
   production running.
2. The emulator's scenario sequence continued advancing while the synthetic machine was stopped,
   allowing scenario context such as `roll_change_recent` to change underneath a stationary
   diagnostic state.

## Repository reality inspected before implementation

- `main` resolved to merge commit `adc77f2876a6f8367ca506ef88794e745322b830` (PR #119).
- No open pull requests were observed before branch creation.
- Main CI and GitHub Pages deployment for that merge commit were successful.
- Issue #117 remained open for localhost operational verification.
- Existing Labeler 2 source and control paths remained simulator-only and localhost-only.
- No physical Labeler 2 connection, OEM manual, commissioned machine profile, verified calibration
  package, production network path, or equipment-control authority was observed.
- `.project/active-work.json` remains a historical coordination snapshot whose own policy states
  that live repository, deployment, equipment, and issue evidence supersede cached current claims.

## Operator-provided localhost smoke evidence

The user supplied direct localhost outputs showing:

- simulator control health returned `status: ready`, `source_scope: simulator_only`, and
  `equipment_control: false`;
- `/api/telemetry` returned a connected, semantically admitted, read-only Labeler 2 simulator source;
- before stop, qualified OPC UA reported `run_state_code: 1` with degraded presentation/camera
  evidence;
- after a manual `stop_for_diagnostic` control request, qualified OPC UA reported
  `run_state_code: 0` and `line_speed_cpm: 0.0`;
- the scenario sequence had nevertheless continued advancing while stopped, and
  `roll_change_recent` had changed;
- a Canvas screenshot showed `Source reports production` while the main workflow button already
  offered `Record simulated guide / spacing observation`.

These are operator-provided localhost smoke observations. They are useful operational evidence but
are not physical-machine evidence and do not establish production readiness.

## Permitted paths

- `.project/opcua-smoke-state-gating-v1.md`
- `src/linealert_core/labeler_demo_opcua_server.py`
- `docs/triage/opcua-source-adapter.js`
- `docs/triage/guide-control-adapter.js`
- `tests/test_labeler_demo_opcua.py`
- `tests/test_canvas_opcua_source.py`

## Bounded change

- expose the qualified OPC UA `run_state_code` and current source sequence through the existing
  `LineAlertOpcuaSource.status()` browser boundary;
- make the guide workflow use that qualified source run state instead of the legacy browser `mode`
  variable for stop/inspect/restore/diagnostic/resume gating;
- treat a simulator control acknowledgment as a request acknowledgment, not proof that the source
  has reached the requested machine state;
- after a stop request, wait for fresh qualified OPC UA `run_state_code == 0` before enabling guide
  inspection;
- after a resume request, wait for fresh qualified OPC UA `run_state_code == 1` before beginning
  production verification;
- keep the emulator scenario/production sequence frozen while stopped;
- advance scenario progression for production and explicit diagnostic batches only;
- continue publishing fresh OPC UA snapshots while stopped, so source timestamps/freshness can
  advance even though scenario progression does not.

## Boundaries

```text
control_acknowledgment != verified_source_state
browser_workflow_state != machine_state
simulator_sequence != wall_clock_time
simulator_value != verified_physical_state
telemetry != diagnosis
simulated_human_observation != verified_physical_state
recommendation != authorized_action
intervention_followed_by_improvement != proof_of_mechanism
```

No PLC write, OPC UA method call, physical equipment connection, production-network access, OEM
procedure authority, safety approval, or production authorization is introduced.

## Expected verification

Repository gates:

```text
ruff check .
pytest
```

Targeted behavior:

```text
qualified OPC run state 1
→ guide observation blocked
→ stop control request
→ wait for qualified OPC run state 0
→ guide observation enabled

stopped source
→ fresh OPC UA snapshots continue
→ emulator scenario sequence remains unchanged
→ diagnostic batch or resume
→ scenario sequence advances again
```

Manual localhost verification remains required after merge. Passing CI establishes software
contracts only.

## Rollback

Revert the bounded files above. No equipment rollback is required because the change remains
simulator-only, localhost-only, and read-only on the OPC UA evidence surface.
