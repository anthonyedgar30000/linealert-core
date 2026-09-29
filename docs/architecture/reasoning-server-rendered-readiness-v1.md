# Reasoning server-rendered readiness v1

## Purpose

The Reasoning Inputs route must show the current historian readiness and bounded
recent evidence even before browser-side JavaScript hydrates.

This increment was prompted by a LAN browser observation where the historian
API and emulator were healthy, but the page remained at its client-side initial
state. Subsequent runtime logging identified a blocked Next.js development/HMR
origin for the LAN host; that underlying client-runtime issue is addressed by
`docs/architecture/lan-dev-origin-v1.md`.

The visible initial state was:

- HISTORIAN: OFFLINE / FAIL CLOSED
- FUNCTIONAL / TEMPORAL: NO LIVE HISTORY
- REASON CODE: WAITING

Direct requests through the same LAN-facing Next.js origin were returning live
emulated historian data. The fault was therefore classified as presentation /
client hydration behavior, not historian unavailability.

## Delivery model

/reasoning is now a dynamic server-rendered route.

On each page request the Next.js server performs bounded read-only requests to
the loopback historian service:

- GET 127.0.0.1:8767/api/status
- GET 127.0.0.1:8767/api/history/functional-temporal?limit=8

Each request is no-store and bounded by a 1.5 second timeout.

The returned snapshot is rendered into the initial HTML and passed to the
existing client component. Historian timestamp labels use a deterministic UTC
presentation so server and browser hydration do not depend on environment
locale; see `docs/architecture/reasoning-deterministic-timestamp-rendering-v1.md`.

After hydration, the client continues polling the existing same-origin routes:

- /api/historian/status
- /api/historian/functional-temporal?limit=8

This keeps the browser isolated from loopback port 8767 while preserving live
updates when JavaScript is healthy.

## Failure behavior

If the loopback historian cannot be read during server rendering, the initial
HTML renders an explicit bounded unavailable state:

- connected = false
- source_available = false
- reason_code = EVIDENCE.HISTORIAN_UNAVAILABLE
- zero retained records

The server does not render WAITING as though readiness had not been assessed,
and it does not substitute cached or invented historian evidence.

Client polling may recover the page later if the historian becomes available.

## LAN acceptance

The acceptance condition is stronger than an API-only health check.

A direct HTTP request to the LAN-facing page itself:

http://192.168.0.242:8766/reasoning

must return initial HTML containing the current historian classification. In
emulated mode this includes:

- LIVE EMULATION
- EMULATED SOURCE LIVE
- Local emulated historian
- the SQLite emulator backend identity

This verifies that the visible page is not dependent on successful client
hydration merely to escape its placeholder state.

## Boundaries

- server_rendered_historian_snapshot != plant_history
- server_rendered_readiness != diagnosis
- rendered_emulated_history != verified_physical_state
- successful_retrieval != explanation_truth
- client_hydration_failure != historian_failure
- historian_retrieval != authorized_action

This increment adds no historian writes, inference endpoint, equipment command,
safety approval, or return-to-service authority.

## Rollback

Revert the server/client split and restore the prior client-only Reasoning Inputs
page. No historian, service-case, or equipment rollback is required.
