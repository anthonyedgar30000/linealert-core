# Service case local persistence v1

Repository: anthonyedgar30000/linealert-core
Base: main@741790bec2179b4e6ba09f54d1e9d65d22345809
Branch: agent/service-case-local-persistence-v1

## Objective

Persist the Speedway Service Workspace service case and technician-entered
plant-reported context across refresh/restart on the local LineAlert host.

## Permitted paths

- src/linealert_core/service_case_store.py
- src/linealert_core/service_case_service.py
- pyproject.toml
- scripts/start-hybrid.ps1
- examples/speedway_service_case_workspace_seed_v1.json
- ui/app/page.tsx
- ui/app/service-workspace.module.css
- ui/app/api/service-cases/**
- tests/test_service_case_store.py
- tests/test_speedway_service_workspace.py
- tests/test_project_state.py
- docs/architecture/service-case-local-persistence-v1.md
- docs/architecture/speedway-service-workspace-v1.md
- docs/architecture/service-case-data-contract-v1.md
- README.md
- .gitignore
- .project/active-work.json
- .project/service-case-local-persistence-v1.md

## Storage boundary

- loopback persistence service: 127.0.0.1:8768
- default Windows data path: %LOCALAPPDATA%\LineAlert\service-cases-v1
- one validated JSON bundle per service-case identity
- atomic temp-file + fsync + replace writes
- single-process in-memory lock
- plaintext local data
- no production database claim
- no direct CMMS access
- no equipment path

## Failure behavior

If the local store is unavailable, plant-context entry is disabled. The UI does
not treat an in-memory value as successfully persisted.

Malformed retained records fail closed on read.

## Authority limits

- local_persistence != plant_cmms_record
- local_persistence != production_service_database
- persisted_technician_entry != direct_system_observation
- persisted_plant_reported_context != verified_source_record
- single_process_atomic_replace != distributed_transaction
- service_case_persistence != equipment_authority
- service_case_persistence != return_to_service_authority

## Verification

Required gates:

- ruff check .
- pytest
- npm run lint
- npm run build
- PowerShell startup script parses
- local service status returns 200
- seeded service case survives service restart
- plant context written through the Next proxy survives service restart
- duplicate/cross-identity/context-contract violations are refused
- historian-offline behavior remains independent and fail-closed
- git diff --check

## Rollback

Revert this increment and stop the service on port 8768. Existing local retained
JSON files may remain as inert user data; deleting them is a separate explicit
data-removal action and is not required for code rollback. No equipment rollback
is required.
