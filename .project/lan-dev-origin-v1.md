# LAN Next.js development origin v1

Repository: anthonyedgar30000/linealert-core
Base: main@7a5bac902cfb3caa60d068d1d806c834379ece4a
Branch: agent/allow-lan-dev-origin-v1

## Objective

Allow the laptop LAN origin to load the Next.js development client/HMR runtime
without broadening the loopback service network boundary.

## Permitted paths

- ui/next.config.ts
- scripts/start-hybrid.ps1
- tests/test_lan_dev_origin.py
- tests/test_project_state.py
- docs/architecture/lan-dev-origin-v1.md
- docs/architecture/reasoning-server-rendered-readiness-v1.md
- README.md
- .project/active-work.json
- .project/lan-dev-origin-v1.md

## Observed failure

Next.js runtime log:

Blocked cross-origin request to Next.js dev resource /_next/hmr from 192.168.0.242.

At the same time:

- LAN historian status through 8766 returned 200
- functional/temporal history through 8766 returned 200
- loopback historian 8767 returned 200
- emulated cycle timestamps continued advancing

This classified the visible WAITING state as a UI development-origin / hydration
problem rather than a historian failure.

## Fix

- derive one default-route IPv4 address on startup
- respect explicit LINEALERT_UI_ALLOWED_DEV_ORIGIN override
- expose only that address to Next.js allowedDevOrigins
- no wildcard origin
- no change to 8767 or 8768 loopback bindings

## Verification

- PowerShell startup script parses
- npm run lint
- npm run build
- pytest
- Next dev startup reports the allowed LAN dev origin
- no blocked-origin HMR warning after LAN access
- /reasoning initial HTML remains server-rendered with live emulation
- client polling can hydrate and continue from the same-origin API
- 8767 remains 127.0.0.1 only
- 8768 remains 127.0.0.1 only

## Boundaries

- lan_dev_origin_allowance != historian_lan_binding
- lan_dev_origin_allowance != service_case_store_lan_binding
- browser_hmr_access != equipment_access
- browser_client_polling != historian_authority
- network_reachability != production_authorization

## Rollback

Revert this LAN development-origin increment. No historian, service-case data,
or equipment rollback is required.
