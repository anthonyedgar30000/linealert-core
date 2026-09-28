# Service case data contract v1

Repository: anthonyedgar30000/linealert-core
Base: main@e22ca7cc404b9040c0c2a48eabe6fa442d75dfe5
Branch: agent/service-case-contracts-v1

## Objective

Define executable v1 contracts for the Speedway service case, the evidence-backed
first detected departure, and provenance-preserving plant-reported context before
the Speedway Service Workspace is implemented.

## Permitted paths

- src/linealert_core/service_case.py
- src/linealert_core/__init__.py
- tests/test_service_case.py
- tests/test_project_state.py
- examples/speedway_service_case_v1.json
- examples/plant_reported_context_v1.json
- docs/architecture/service-case-data-contract-v1.md
- .project/active-work.json
- .project/service-case-data-contract-v1.md
- README.md

## Equipment and authority scope

- Physical equipment connection: not introduced.
- Equipment write/control path: not introduced.
- Direct plant CMMS connection: not introduced.
- Historian persistence or writes: not introduced.
- Safety or return-to-service authority: not granted.
## Contract boundaries

ServiceCase preserves customer/site/asset identity, service-call timing,
pre-incident evidence-window timing, evidence references, context references,
and an optional bounded first-detected-departure record.

FirstDetectedDeparture requires retained evidence IDs, source IDs, expected
reference identity, configuration version, clock quality, and a timezone-aware
observation time. Its serialized form explicitly refuses root-cause, incident
start, and causation claims.

PlantReportedContext preserves the original/bounded report, the technician who
entered it, source identity/class, source-verification state, reported time shape,
reported clock quality, source record reference when available, and provenance.

Manual source-verification states intentionally stop at:

- plant_relay_only
- technician_viewed_source
- technician_retained_copy

There is no direct-source-ingestion state in this contract.

## Verification

Required gates:

- ruff check .
- pytest
- npm run lint
- npm run build
- git diff --check

Focused tests cover round trips, timestamp awareness, event-time shapes,
cross-asset departure refusal, evidence identity, source identity, and the rule
that a manually viewed or retained plant source is still not direct system
evidence.

## Rollback

Revert this bounded data-contract increment. No equipment rollback is required.
