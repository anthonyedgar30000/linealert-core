# Service case data contract v1

## Purpose

This contract defines the first executable data model for the Speedway-centered
LineAlert service workflow. It gives the future Speedway Service Workspace stable
objects for a service case, an evidence-supported first detected departure, and
plant context relayed through a Speedway technician.

This increment is a data-contract boundary only. It does not add CMMS access,
historian writes, inference, equipment connectivity, equipment control, safety
approval, or return-to-service authority.

## ServiceCase

A ServiceCase binds the operational investigation to explicit identity and time
scope:

- service_case_id
- customer_id
- site_id
- asset_id
- opened_at / opened_by
- service_call_received_at
- reported_symptom
- optional reported_incident_at and service_call_reference
- preincident_window_start / preincident_window_end
- optional current_configuration_version
- status
- references to retained evidence, plant-reported context, working explanations,
  and missing-evidence requests
- optional first_detected_departure

The contract rejects naive timestamps, reverse evidence windows, a pre-incident
window ending after the service call or after a known reported incident, duplicate
reference identities, and a first detected departure bound to another asset.

When a reported incident timestamp is available, a first detected departure
cannot be later than that reported incident. When incident time is not available,
the contract retains the departure only as an evidence-window observation and
does not invent an incident boundary.

## FirstDetectedDeparture

FirstDetectedDeparture is not a causal conclusion. It records the earliest
retained departure that another bounded analysis has already supported.

Required provenance includes:

- departure_id
- asset_id
- relationship_id
- observed_at
- expected_reference_id
- configuration_version
- clock_quality
- reason_code
- one or more evidence_ids
- one or more source_ids
- optional calibration_id
- optional sampling_profile_id

The serialized contract always emits:

- root_cause_established = false
- incident_start_established = false
- causation_established = false

The object therefore cannot silently turn temporal ordering into a causal claim.
## PlantReportedContext

PlantReportedContext represents information a Speedway technician receives from
plant personnel or inspects manually in a plant-owned source. It remains a
reported-context record even when the technician views or retains a copy of the
source record.

Source classes in v1:

- cmms
- shift_log
- operator_statement
- maintenance_statement
- other

Source-verification states in v1:

- plant_relay_only
- technician_viewed_source
- technician_retained_copy

There is intentionally no direct_source_retrieval state. Direct source ingestion
requires a different admitted source contract and must not be simulated by a
manual entry.

Every plant-reported context record preserves:

- context_id
- service_case_id
- asset_id
- entered_at / entered_by
- reported source class and source identity
- original wording or bounded summary
- source-verification state
- reported time kind
- reported clock quality, including explicit unknown
- provenance
- optional source-record reference and plant contact role
## Reported event time

Plant context can preserve imperfect historical time without pretending it is a
verified machine timestamp.

Supported time shapes are:

- exact: start timestamp only
- approximate: start timestamp only
- window: start and end timestamps
- unknown: no event timestamp

All supplied timestamps must be timezone-aware. A window cannot run backward.
The separate reported_clock_quality field prevents a timestamp from implicitly
claiming synchronized machine-clock authority.

## Wire contracts

Canonical JSON examples:

- examples/speedway_service_case_v1.json
- examples/plant_reported_context_v1.json

Executable parsers and serializers:

- service_case_from_dict / service_case_to_dict
- plant_reported_context_from_dict / plant_reported_context_to_dict
- first_detected_departure_from_dict / first_detected_departure_to_dict
- validate_plant_reported_context_binding

The binding validator requires service-case identity, asset identity, and the
context reference on the ServiceCase to agree before the reported context is
treated as belonging to that case.

Schema versions:

- linealert.service-case.v1
- linealert.plant-reported-context.v1

The v1 wire parsers require the exact schema version. Authority and causal flags
are contract-derived outputs rather than trusted input: supplying
authorized_action, verified_source_record, direct_system_observation, or causal
claim booleans does not promote those claims on round-trip.

## Claim boundaries

- first_detected_departure != root_cause
- first_detected_departure != incident_start
- temporal_precedence != causation
- plant_reported_context != verified_source_record
- technician_entry != direct_system_observation
- reported_event_time != verified_machine_timestamp
- recommendation != authorized_action

## Deferred from this increment

The contract does not yet implement:

- persistence for service cases or plant-reported context
- an API endpoint
- the Speedway Service Workspace
- plant-context request workflow objects
- working-explanation objects
- direct CMMS or document retrieval
- automatic first-departure selection
- reasoning-node consumption of plant-reported context
- service-report generation

Those are separate bounded increments. The data contracts here establish the
identity, provenance, timing, and epistemic rules they must preserve.
