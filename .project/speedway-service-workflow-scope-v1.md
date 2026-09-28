# Speedway service workflow scope v1

Repository: anthonyedgar30000/linealert-core
Base: main@13d57e81164c28918d9959874348b498cb3b45e2
Branch: agent/speedway-service-scope-v1

## Objective

Reset the authoritative initial commercial LineAlert workflow around Speedway
service / maintenance technicians before additional runtime or frontend work.

## Permitted paths

- .project/active-work.json
- .project/speedway-service-workflow-scope-v1.md
- docs/architecture/speedway-service-workflow-scope-v1.md
- README.md
- tests/test_project_state.py

## Scope decision

- Primary initial user: Speedway service / maintenance technician.
- Plant operators and plant internal maintenance are not required LineAlert v1 users.
- Plant people, CMMS, historian, and other plant records remain evidence/context sources.
- Direct customer CMMS integration is not required for v1.
- Technician-entered plant context must retain provenance and remain distinct from
  directly verified source records.
- The investigation should seek the earliest defensible departure from expected
  behavior before the incident that triggered the service call.
- First detected departure is not root-cause proof and temporal precedence is not causation.
- Existing operator-oriented Plant Canvas behavior is preserved as synthetic design
  history, not deleted or silently reclassified as the current commercial workflow.
- The target future primary surface is a Speedway Service Workspace.

## Safety and authority limits

This increment adds no:

- runtime behavior;
- physical equipment connection;
- equipment command or write path;
- safety approval;
- production or return-to-service authority;
- autonomous diagnosis.

## Verification

Expected repository gates:

- ruff check .
- pytest
- npm run lint
- npm run build

Contract tests must prove the new product scope, manual plant-context provenance
requirements, deferred customer-facing workflow, and first-detected-departure
epistemic boundaries.

## Rollback

Revert this documentation/state increment. No equipment rollback is required
because the increment changes no runtime or physical system.
