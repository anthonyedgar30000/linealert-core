# Reasoning server-rendered readiness v1

Repository: anthonyedgar30000/linealert-core
Base: main@17bc6abbf402a2532b64a58f701f707833b4d671
Branch: agent/reasoning-ssr-fallback-v1

## Objective

Ensure the Reasoning Inputs page renders current historian readiness and bounded
history in the initial HTML, so a browser hydration problem cannot leave the UI
stuck at WAITING while the LAN-facing historian API is healthy.

## Permitted paths

- ui/app/reasoning/page.tsx
- ui/app/reasoning/reasoning-client.tsx
- tests/test_reasoning_inputs_emulation.py
- tests/test_project_state.py
- docs/architecture/reasoning-server-rendered-readiness-v1.md
- docs/architecture/live-emulated-historian-v1.md
- README.md
- .project/active-work.json
- .project/reasoning-server-rendered-readiness-v1.md

## Scope

- /reasoning becomes dynamic server-rendered.
- Initial historian status and functional/temporal history are read directly
  from loopback 127.0.0.1:8767 by the Next.js server.
- Each server read is no-store and has a 1.5 second timeout.
- Existing client polling remains unchanged in authority and continues through
  same-origin /api/historian routes after hydration.
- Server failure renders explicit EVIDENCE.HISTORIAN_UNAVAILABLE rather than
  an unassessed WAITING placeholder.

## Acceptance

- LAN historian status endpoint returns 200 with emulated=true.
- LAN functional/temporal endpoint returns 200 with retained records.
- Raw initial HTML from http://192.168.0.242:8766/reasoning contains
  LIVE EMULATION, EMULATED SOURCE LIVE, and Local emulated historian.
- Raw initial HTML does not contain OFFLINE / FAIL CLOSED or WAITING while
  the emulator is healthy.
- npm run lint and npm run build pass.
- /reasoning is reported as a dynamic server-rendered route.
- ruff and pytest pass.

## Authority limits

- no historian writes
- no inference endpoint
- no equipment command path
- no safety approval
- no return-to-service authority

## Boundaries

- server_rendered_historian_snapshot != plant_history
- server_rendered_readiness != diagnosis
- rendered_emulated_history != verified_physical_state
- successful_retrieval != explanation_truth
- client_hydration_failure != historian_failure
- historian_retrieval != authorized_action

## Rollback

Revert this frontend delivery increment. No historian database, service-case
store, or equipment rollback is required.
