# Speedway Service Workspace v1

## Purpose

The root LineAlert frontend is now centered on the initial commercial user:
the Speedway service / maintenance technician responding to an equipment
service call.

The workspace answers a service-oriented sequence rather than an operator
workflow:

1. Why was Speedway called?
2. What retained evidence exists before the reported incident?
3. What is the earliest defensible departure from expected behavior?
4. Which relationships changed?
5. Which relationships continued to hold?
6. What missing plant context would best discriminate the remaining explanations?
7. What plant-reported context did the technician receive?
8. What bounded technician check should come next?

## Primary and legacy surfaces

Primary route:

- `/` — Speedway Service Workspace

Preserved secondary route:

- `/plant-canvas` — legacy synthetic operator / shift-supervisor Plant Canvas

The legacy route is intentionally preserved as design history and potential
future customer-facing work. It is not the initial commercial workflow.

## Service-case display

The current v1 UI uses a controlled synthetic browser fixture aligned to the
`linealert.service-case.v1` and `linealert.plant-reported-context.v1`
contracts. It displays:

- service-case identity;
- customer/site/asset identity;
- reported incident and service-call time;
- bounded pre-incident evidence window;
- first detected departure;
- expected-reference identity and clock quality;
- evidence identifiers;
- changed relationships;
- relationships that held;
- working explanations and their qualitative standing;
- one low-disturbance bounded technician check.

The display is not persistence. The synthetic workspace is not a production
service record.

## Plant-context entry

The technician can enter returned plant context in the browser session.

The form preserves:

- reported source class;
- reported source identity;
- reported event time or window;
- reported clock quality;
- one of the bounded manual source-verification states;
- original wording or a bounded summary.

Allowed manual verification states remain exactly:

- `plant_relay_only`
- `technician_viewed_source`
- `technician_retained_copy`

There is no `direct_source_retrieval` option. A technician viewing a CMMS
record still does not transform the manual entry into a directly ingested
verified source record.

Browser-session entries are not yet persisted or sent to an API.

## Historian relationship

The workspace only reads the existing same-origin historian status endpoint to
show whether the local historian is available. Historian unavailability remains
fail-closed. The workspace does not substitute cached history, write historian
records, or claim that historian availability establishes a diagnosis.

## Epistemic and authority boundaries

- first_detected_departure != root_cause
- temporal_precedence != causation
- plant_reported_context != verified_source_record
- technician_entry != direct_system_observation
- browser_session_entry != persisted_service_record
- service_workspace_display != production_service_case
- recommendation != authorized_action

The displayed next technician check is a troubleshooting recommendation only.
It does not authorize adjustment, bypass OEM or plant requirements, approve
safety, or authorize return to service.

## Deferred

This increment does not add:

- service-case persistence;
- plant-context persistence;
- service-case API endpoints;
- direct customer CMMS access;
- automatic first-departure selection;
- automatic ingestion of plant reports into reasoning context;
- equipment control;
- safety or return-to-service authority.
