# Speedway Service Workspace v1

Repository: anthonyedgar30000/linealert-core
Base: main@29072f410717cb26b266bd8387ee422c7310a3b0
Branch: agent/speedway-service-workspace-v1

## Objective

Make the Speedway service / maintenance technician workflow the primary local
LineAlert frontend while preserving the former operator-oriented Plant Canvas as
a secondary legacy synthetic surface.

## Permitted paths

- ui/app/page.tsx
- ui/app/service-workspace.module.css
- ui/app/plant-canvas/page.tsx
- ui/app/reasoning/page.tsx
- ui/app/health/page.tsx
- ui/app/evidence/page.tsx
- ui/app/commissioning/layout.tsx
- ui/app/training/page.tsx
- tests/test_speedway_service_workspace.py
- tests/test_project_state.py
- docs/architecture/speedway-service-workspace-v1.md
- .project/active-work.json
- .project/speedway-service-workspace-v1.md
- README.md

## Scope

The new root workspace presents a controlled synthetic service case and the
following bounded workflow:

- why Speedway was called;
- bounded pre-incident reconstruction;
- first detected departure;
- changed relationships;
- relationships that held;
- missing discriminating plant context;
- manual plant-reported context entry;
- working explanations;
- next bounded technician check.

The previous Plant Canvas is preserved under /plant-canvas.

## Plant context

Manual entry is browser-session only and is not persisted. Verification choices
are limited to the v1 contract states:

- plant_relay_only
- technician_viewed_source
- technician_retained_copy

The UI deliberately provides no direct_source_retrieval option.

## Equipment and authority limits

- no physical equipment connection is added;
- no controller or equipment writes are added;
- no CMMS write or direct CMMS integration is added;
- no historian write is added;
- no root-cause authority is granted;
- no safety or return-to-service authority is granted;
- the displayed technician check is not an authorized action.

## Verification

Required gates:

- ruff check .
- pytest
- npm run lint
- npm run build
- route manifest includes / and /plant-canvas
- browser smoke returns HTTP 200 for / and /plant-canvas
- historian-offline state remains fail-closed
- git diff --check

## Rollback

Revert this bounded frontend increment. The legacy Plant Canvas remains preserved
as an independent route, so rollback does not require reconstructing the old UI.
No equipment rollback is required because no physical-system behavior changes.
