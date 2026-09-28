from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from linealert_core.service_case import (
    FirstDetectedDeparture,
    PlantContextSourceClass,
    PlantContextVerificationState,
    PlantReportedContext,
    ReportedTimeKind,
    ServiceCase,
    ServiceCaseError,
    ServiceCaseStatus,
    first_detected_departure_from_dict,
    first_detected_departure_to_dict,
    plant_reported_context_from_dict,
    plant_reported_context_to_dict,
    service_case_from_dict,
    service_case_to_dict,
    validate_plant_reported_context_binding,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_CASE_EXAMPLE = PROJECT_ROOT / "examples" / "speedway_service_case_v1.json"
PLANT_CONTEXT_EXAMPLE = PROJECT_ROOT / "examples" / "plant_reported_context_v1.json"

T0 = datetime(2026, 9, 27, 13, 0, tzinfo=UTC)
INCIDENT = T0 + timedelta(hours=3)
CALL = INCIDENT + timedelta(minutes=45)
OPENED = CALL + timedelta(minutes=10)


def departure(**overrides: object) -> FirstDetectedDeparture:
    values: dict[str, object] = {
        "departure_id": "departure-001",
        "asset_id": "LABELER-02",
        "relationship_id": "relationship:photoeye-to-label-feed",
        "observed_at": T0 + timedelta(hours=1),
        "expected_reference_id": "baseline:labeler-02:v7",
        "configuration_version": "cfg-2026-09-01",
        "clock_quality": "synchronized_cross_source_interval",
        "reason_code": "CONDITION.OUTSIDE_EXPECTED_ENVELOPE",
        "evidence_ids": ("ev-100", "ev-101"),
        "source_ids": ("plc-labeler-02", "camera-labeler-02"),
        "calibration_id": "cal-2026-08",
        "sampling_profile_id": "sampling-10hz",
    }
    values.update(overrides)
    return FirstDetectedDeparture(**values)  # type: ignore[arg-type]


def context(**overrides: object) -> PlantReportedContext:
    values: dict[str, object] = {
        "context_id": "plant-context-001",
        "service_case_id": "svc-2026-0042",
        "asset_id": "LABELER-02",
        "entered_at": OPENED + timedelta(minutes=30),
        "entered_by": "speedway-technician",
        "reported_source_class": PlantContextSourceClass.CMMS,
        "reported_source": "Plant CMMS work-order history",
        "original_wording_or_bounded_summary": (
            "Guide rail adjusted after intermittent bottle backup."
        ),
        "source_verification_state": (
            PlantContextVerificationState.TECHNICIAN_VIEWED_SOURCE
        ),
        "reported_time_kind": ReportedTimeKind.WINDOW,
        "reported_clock_quality": "unknown",
        "provenance": (
            "plant-maintenance-contact",
            "CMMS work order WO-1842 viewed by Speedway technician",
        ),
        "reported_event_start": T0 + timedelta(minutes=40),
        "reported_event_end": T0 + timedelta(minutes=55),
        "source_record_reference": "WO-1842",
        "plant_contact_role": "Plant maintenance",
    }
    values.update(overrides)
    return PlantReportedContext(**values)  # type: ignore[arg-type]

def service_case(**overrides: object) -> ServiceCase:
    values: dict[str, object] = {
        "service_case_id": "svc-2026-0042",
        "customer_id": "customer-synthetic-01",
        "site_id": "site-synthetic-01",
        "asset_id": "LABELER-02",
        "opened_at": OPENED,
        "opened_by": "speedway-technician",
        "service_call_received_at": CALL,
        "reported_symptom": "Labels intermittently skewing and bottle flow backing up.",
        "preincident_window_start": T0,
        "preincident_window_end": INCIDENT,
        "status": ServiceCaseStatus.EVIDENCE_GATHERING,
        "reported_incident_at": INCIDENT,
        "service_call_reference": "CALL-0042",
        "current_configuration_version": "cfg-2026-09-01",
        "evidence_ids": ("ev-100", "ev-101"),
        "plant_reported_context_ids": ("plant-context-001",),
        "working_explanation_ids": ("working-explanation-01",),
        "missing_evidence_request_ids": ("request-plant-window-01",),
        "first_detected_departure": departure(),
    }
    values.update(overrides)
    return ServiceCase(**values)  # type: ignore[arg-type]


def test_service_case_round_trip_preserves_bounded_departure() -> None:
    original = service_case()
    payload = service_case_to_dict(original)
    restored = service_case_from_dict(payload)

    assert restored == original
    assert payload["schema_version"] == "linealert.service-case.v1"
    assert payload["authorized_action"] is False

    departure_payload = payload["first_detected_departure"]
    assert isinstance(departure_payload, dict)
    assert departure_payload["root_cause_established"] is False
    assert departure_payload["incident_start_established"] is False
    assert departure_payload["causation_established"] is False
    assert "first_detected_departure != root_cause" in payload["claim_boundaries"]
    assert "temporal_precedence != causation" in payload["claim_boundaries"]


def test_first_detected_departure_round_trip_preserves_source_and_clock_identity() -> None:
    original = departure()
    payload = first_detected_departure_to_dict(original)

    assert first_detected_departure_from_dict(payload) == original
    assert payload["source_ids"] == ["plc-labeler-02", "camera-labeler-02"]
    assert payload["clock_quality"] == "synchronized_cross_source_interval"
    assert payload["configuration_version"] == "cfg-2026-09-01"
    assert payload["calibration_id"] == "cal-2026-08"

def test_service_case_refuses_departure_from_other_asset() -> None:
    with pytest.raises(ServiceCaseError, match="asset_id must match"):
        service_case(first_detected_departure=departure(asset_id="FILLER-01"))


def test_service_case_refuses_departure_outside_preincident_window() -> None:
    with pytest.raises(ServiceCaseError, match="preincident evidence window"):
        service_case(
            first_detected_departure=departure(
                observed_at=T0 - timedelta(seconds=1),
            )
        )


def test_service_case_refuses_departure_after_preincident_window() -> None:
    with pytest.raises(ServiceCaseError, match="preincident evidence window"):
        service_case(
            first_detected_departure=departure(
                observed_at=INCIDENT + timedelta(minutes=1),
            ),
        )


def test_service_case_requires_timezone_aware_temporal_identity() -> None:
    naive = datetime(2026, 9, 27, 13, 0)
    with pytest.raises(ServiceCaseError, match="timezone-aware"):
        service_case(preincident_window_start=naive)


def test_service_case_refuses_duplicate_evidence_identity() -> None:
    with pytest.raises(ServiceCaseError, match="must not contain duplicates"):
        service_case(evidence_ids=("ev-100", "ev-100"))


def test_service_case_refuses_preincident_window_after_service_call() -> None:
    with pytest.raises(ServiceCaseError, match="must not follow service_call_received_at"):
        service_case(preincident_window_end=CALL + timedelta(minutes=1))


def test_plant_reported_context_round_trip_never_promotes_direct_source_authority() -> None:
    original = context()
    payload = plant_reported_context_to_dict(original)
    restored = plant_reported_context_from_dict(payload)

    assert restored == original
    assert payload["schema_version"] == "linealert.plant-reported-context.v1"
    assert payload["direct_system_observation"] is False
    assert payload["verified_source_record"] is False
    assert payload["causal_claim_established"] is False
    assert payload["reported_clock_quality"] == "unknown"
    assert "plant_reported_context != verified_source_record" in payload["claim_boundaries"]

@pytest.mark.parametrize(
    ("time_kind", "start", "end"),
    [
        (ReportedTimeKind.EXACT, T0, None),
        (ReportedTimeKind.APPROXIMATE, T0, None),
        (ReportedTimeKind.WINDOW, T0, T0 + timedelta(minutes=5)),
        (ReportedTimeKind.UNKNOWN, None, None),
    ],
)
def test_reported_time_shapes_are_explicit(
    time_kind: ReportedTimeKind,
    start: datetime | None,
    end: datetime | None,
) -> None:
    record = context(
        reported_time_kind=time_kind,
        reported_event_start=start,
        reported_event_end=end,
    )
    assert record.reported_time_kind is time_kind


@pytest.mark.parametrize(
    ("time_kind", "start", "end", "message"),
    [
        (
            ReportedTimeKind.EXACT,
            T0,
            T0 + timedelta(minutes=1),
            "requires start only",
        ),
        (ReportedTimeKind.WINDOW, T0, None, "requires start and end"),
        (ReportedTimeKind.UNKNOWN, T0, None, "must not include event timestamps"),
    ],
)
def test_reported_time_shape_mismatches_fail_closed(
    time_kind: ReportedTimeKind,
    start: datetime | None,
    end: datetime | None,
    message: str,
) -> None:
    with pytest.raises(ServiceCaseError, match=message):
        context(
            reported_time_kind=time_kind,
            reported_event_start=start,
            reported_event_end=end,
        )


def test_reported_window_refuses_reverse_time() -> None:
    with pytest.raises(ServiceCaseError, match="must not precede"):
        context(
            reported_event_start=T0 + timedelta(minutes=10),
            reported_event_end=T0,
        )

def test_reported_context_requires_provenance_and_explicit_clock_quality() -> None:
    with pytest.raises(ServiceCaseError, match="provenance must contain at least one item"):
        context(provenance=())

    with pytest.raises(ServiceCaseError, match="reported_clock_quality"):
        context(reported_clock_quality=" ")


def test_reported_context_parser_refuses_direct_source_verification_value() -> None:
    payload = plant_reported_context_to_dict(context())
    payload["source_verification_state"] = "direct_source_retrieval"

    with pytest.raises(ServiceCaseError, match="unsupported source_verification_state"):
        plant_reported_context_from_dict(payload)


def test_reported_context_viewed_source_still_is_not_direct_ingestion() -> None:
    payload = plant_reported_context_to_dict(
        context(
            source_verification_state=(
                PlantContextVerificationState.TECHNICIAN_RETAINED_COPY
            )
        )
    )

    assert payload["source_verification_state"] == "technician_retained_copy"
    assert payload["verified_source_record"] is False
    assert payload["direct_system_observation"] is False


def test_service_case_parser_refuses_non_array_reference_fields() -> None:
    payload = service_case_to_dict(service_case())
    payload["evidence_ids"] = "ev-100"

    with pytest.raises(ServiceCaseError, match="evidence_ids must be an array"):
        service_case_from_dict(payload)


def test_first_departure_requires_retained_evidence_and_source_identity() -> None:
    with pytest.raises(ServiceCaseError, match="evidence_ids must contain at least one"):
        departure(evidence_ids=())

    with pytest.raises(ServiceCaseError, match="source_ids must contain at least one"):
        departure(source_ids=())

def test_canonical_service_case_example_is_executable_contract() -> None:
    payload = json.loads(SERVICE_CASE_EXAMPLE.read_text(encoding="utf-8"))
    case = service_case_from_dict(payload)
    serialized = service_case_to_dict(case)

    assert case.service_case_id == "svc-2026-0042"
    assert case.first_detected_departure is not None
    assert serialized["authorized_action"] is False
    assert serialized["first_detected_departure"]["root_cause_established"] is False


def test_canonical_plant_context_example_is_executable_contract() -> None:
    payload = json.loads(PLANT_CONTEXT_EXAMPLE.read_text(encoding="utf-8"))
    record = plant_reported_context_from_dict(payload)
    serialized = plant_reported_context_to_dict(record)

    assert record.service_case_id == "svc-2026-0042"
    assert record.reported_source_class is PlantContextSourceClass.CMMS
    assert serialized["verified_source_record"] is False
    assert serialized["direct_system_observation"] is False


def test_public_api_exports_service_case_contracts() -> None:
    import linealert_core

    assert linealert_core.ServiceCase is ServiceCase
    assert linealert_core.PlantReportedContext is PlantReportedContext
    assert linealert_core.FirstDetectedDeparture is FirstDetectedDeparture

def test_preincident_window_cannot_extend_past_known_reported_incident() -> None:
    with pytest.raises(ServiceCaseError, match="must not follow reported_incident_at"):
        service_case(preincident_window_end=INCIDENT + timedelta(minutes=1))


def test_plant_reported_context_binding_requires_case_and_asset_identity() -> None:
    case = service_case()
    record = context()

    validate_plant_reported_context_binding(case, record)

    with pytest.raises(ServiceCaseError, match="service_case_id must match"):
        validate_plant_reported_context_binding(
            case,
            context(service_case_id="svc-other"),
        )

    with pytest.raises(ServiceCaseError, match="asset_id must match"):
        validate_plant_reported_context_binding(
            case,
            context(asset_id="FILLER-01"),
        )

    with pytest.raises(ServiceCaseError, match="must be referenced"):
        validate_plant_reported_context_binding(
            case,
            context(context_id="plant-context-unreferenced"),
        )

def test_wire_parsers_require_exact_v1_schema_versions() -> None:
    service_payload = service_case_to_dict(service_case())
    service_payload["schema_version"] = "linealert.service-case.v2"
    with pytest.raises(ServiceCaseError, match="schema_version must be linealert.service-case.v1"):
        service_case_from_dict(service_payload)

    context_payload = plant_reported_context_to_dict(context())
    context_payload.pop("schema_version")
    with pytest.raises(
        ServiceCaseError,
        match="schema_version must be linealert.plant-reported-context.v1",
    ):
        plant_reported_context_from_dict(context_payload)


def test_wire_input_cannot_promote_authority_or_causal_claims() -> None:
    service_payload = service_case_to_dict(service_case())
    service_payload["authorized_action"] = True
    departure_payload = service_payload["first_detected_departure"]
    assert isinstance(departure_payload, dict)
    departure_payload["root_cause_established"] = True
    departure_payload["causation_established"] = True

    restored_case = service_case_from_dict(service_payload)
    restored_service_payload = service_case_to_dict(restored_case)
    restored_departure = restored_service_payload["first_detected_departure"]
    assert isinstance(restored_departure, dict)
    assert restored_service_payload["authorized_action"] is False
    assert restored_departure["root_cause_established"] is False
    assert restored_departure["causation_established"] is False

    context_payload = plant_reported_context_to_dict(context())
    context_payload["verified_source_record"] = True
    context_payload["direct_system_observation"] = True
    context_payload["causal_claim_established"] = True

    restored_context = plant_reported_context_from_dict(context_payload)
    restored_context_payload = plant_reported_context_to_dict(restored_context)
    assert restored_context_payload["verified_source_record"] is False
    assert restored_context_payload["direct_system_observation"] is False
    assert restored_context_payload["causal_claim_established"] is False
