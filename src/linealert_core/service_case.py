"""Bounded service-case and plant-reported-context contracts for LineAlert."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ServiceCaseError(ValueError):
    """Raised when a service-case contract is malformed or overclaims evidence."""


class ServiceCaseStatus(StrEnum):
    OPEN = "open"
    EVIDENCE_GATHERING = "evidence_gathering"
    TECHNICIAN_INVESTIGATION = "technician_investigation"
    CLOSED = "closed"


class ReportedTimeKind(StrEnum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    WINDOW = "window"
    UNKNOWN = "unknown"


class PlantContextSourceClass(StrEnum):
    CMMS = "cmms"
    SHIFT_LOG = "shift_log"
    OPERATOR_STATEMENT = "operator_statement"
    MAINTENANCE_STATEMENT = "maintenance_statement"
    OTHER = "other"


class PlantContextVerificationState(StrEnum):
    PLANT_RELAY_ONLY = "plant_relay_only"
    TECHNICIAN_VIEWED_SOURCE = "technician_viewed_source"
    TECHNICIAN_RETAINED_COPY = "technician_retained_copy"

SERVICE_CASE_CLAIM_BOUNDARIES = (
    "first_detected_departure != root_cause",
    "first_detected_departure != incident_start",
    "temporal_precedence != causation",
    "plant_reported_context != verified_source_record",
    "technician_entry != direct_system_observation",
    "recommendation != authorized_action",
)

PLANT_CONTEXT_CLAIM_BOUNDARIES = (
    "plant_reported_context != verified_source_record",
    "technician_entry != direct_system_observation",
    "reported_event_time != verified_machine_timestamp",
    "temporal_proximity != causation",
)


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceCaseError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_text(name: str, value: object | None) -> str | None:
    if value is None:
        return None
    return _required_text(name, value)


def _require_aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime):
        raise ServiceCaseError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ServiceCaseError(f"{name} must be timezone-aware")


def _parse_datetime(name: str, value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ServiceCaseError(f"{name} must be an ISO 8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ServiceCaseError(f"{name} must be ISO 8601") from exc
    _require_aware(parsed, name)
    return parsed

def _optional_datetime(name: str, value: object | None) -> datetime | None:
    if value is None:
        return None
    return _parse_datetime(name, value)


def _text_tuple(
    name: str,
    values: Sequence[object],
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ServiceCaseError(f"{name} must be an array of strings")
    normalized = tuple(_required_text(f"{name} item", item) for item in values)
    if not normalized and not allow_empty:
        raise ServiceCaseError(f"{name} must contain at least one item")
    if len(normalized) != len(set(normalized)):
        raise ServiceCaseError(f"{name} must not contain duplicates")
    return normalized


def _enum_value(enum_type: type[StrEnum], name: str, value: object) -> StrEnum:
    if not isinstance(value, str):
        raise ServiceCaseError(f"{name} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ServiceCaseError(f"unsupported {name}: {value}") from exc


@dataclass(frozen=True, slots=True)
class FirstDetectedDeparture:
    """Earliest retained departure supported by admitted evidence for one service case."""

    departure_id: str
    asset_id: str
    relationship_id: str
    observed_at: datetime
    expected_reference_id: str
    configuration_version: str
    clock_quality: str
    reason_code: str
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    calibration_id: str | None = None
    sampling_profile_id: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "departure_id",
            "asset_id",
            "relationship_id",
            "expected_reference_id",
            "configuration_version",
            "clock_quality",
            "reason_code",
        ):
            object.__setattr__(self, name, _required_text(name, getattr(self, name)))
        _require_aware(self.observed_at, "observed_at")
        object.__setattr__(self, "evidence_ids", _text_tuple("evidence_ids", self.evidence_ids))
        object.__setattr__(self, "source_ids", _text_tuple("source_ids", self.source_ids))
        object.__setattr__(
            self,
            "calibration_id",
            _optional_text("calibration_id", self.calibration_id),
        )
        object.__setattr__(
            self,
            "sampling_profile_id",
            _optional_text("sampling_profile_id", self.sampling_profile_id),
        )

@dataclass(frozen=True, slots=True)
class PlantReportedContext:
    """Context relayed through a Speedway technician rather than directly ingested."""

    context_id: str
    service_case_id: str
    asset_id: str
    entered_at: datetime
    entered_by: str
    reported_source_class: PlantContextSourceClass
    reported_source: str
    original_wording_or_bounded_summary: str
    source_verification_state: PlantContextVerificationState
    reported_time_kind: ReportedTimeKind
    reported_clock_quality: str
    provenance: tuple[str, ...]
    reported_event_start: datetime | None = None
    reported_event_end: datetime | None = None
    source_record_reference: str | None = None
    plant_contact_role: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "context_id",
            "service_case_id",
            "asset_id",
            "entered_by",
            "reported_source",
            "original_wording_or_bounded_summary",
            "reported_clock_quality",
        ):
            object.__setattr__(self, name, _required_text(name, getattr(self, name)))
        if not isinstance(self.reported_source_class, PlantContextSourceClass):
            raise ServiceCaseError("reported_source_class must be a PlantContextSourceClass")
        if not isinstance(self.source_verification_state, PlantContextVerificationState):
            raise ServiceCaseError(
                "source_verification_state must be a PlantContextVerificationState"
            )
        if not isinstance(self.reported_time_kind, ReportedTimeKind):
            raise ServiceCaseError("reported_time_kind must be a ReportedTimeKind")
        _require_aware(self.entered_at, "entered_at")
        object.__setattr__(self, "provenance", _text_tuple("provenance", self.provenance))
        object.__setattr__(
            self,
            "source_record_reference",
            _optional_text("source_record_reference", self.source_record_reference),
        )
        object.__setattr__(
            self,
            "plant_contact_role",
            _optional_text("plant_contact_role", self.plant_contact_role),
        )
        if self.reported_event_start is not None:
            _require_aware(self.reported_event_start, "reported_event_start")
        if self.reported_event_end is not None:
            _require_aware(self.reported_event_end, "reported_event_end")
        self._validate_reported_time()

    def _validate_reported_time(self) -> None:
        start = self.reported_event_start
        end = self.reported_event_end
        if self.reported_time_kind in {ReportedTimeKind.EXACT, ReportedTimeKind.APPROXIMATE}:
            if start is None or end is not None:
                raise ServiceCaseError(
                    f"{self.reported_time_kind.value} reported time requires start only"
                )
        elif self.reported_time_kind is ReportedTimeKind.WINDOW:
            if start is None or end is None:
                raise ServiceCaseError("window reported time requires start and end")
            if end < start:
                raise ServiceCaseError("reported_event_end must not precede reported_event_start")
        elif start is not None or end is not None:
            raise ServiceCaseError("unknown reported time must not include event timestamps")

@dataclass(frozen=True, slots=True)
class ServiceCase:
    """Immutable current service-case state referencing retained evidence by identity."""

    service_case_id: str
    customer_id: str
    site_id: str
    asset_id: str
    opened_at: datetime
    opened_by: str
    service_call_received_at: datetime
    reported_symptom: str
    preincident_window_start: datetime
    preincident_window_end: datetime
    status: ServiceCaseStatus = ServiceCaseStatus.OPEN
    reported_incident_at: datetime | None = None
    service_call_reference: str | None = None
    current_configuration_version: str | None = None
    evidence_ids: tuple[str, ...] = ()
    plant_reported_context_ids: tuple[str, ...] = ()
    working_explanation_ids: tuple[str, ...] = ()
    missing_evidence_request_ids: tuple[str, ...] = ()
    first_detected_departure: FirstDetectedDeparture | None = None

    def __post_init__(self) -> None:
        for name in (
            "service_case_id",
            "customer_id",
            "site_id",
            "asset_id",
            "opened_by",
            "reported_symptom",
        ):
            object.__setattr__(self, name, _required_text(name, getattr(self, name)))
        if not isinstance(self.status, ServiceCaseStatus):
            raise ServiceCaseError("status must be a ServiceCaseStatus")
        for name in (
            "opened_at",
            "service_call_received_at",
            "preincident_window_start",
            "preincident_window_end",
        ):
            _require_aware(getattr(self, name), name)
        if self.opened_at < self.service_call_received_at:
            raise ServiceCaseError("opened_at must not precede service_call_received_at")
        if self.preincident_window_end < self.preincident_window_start:
            raise ServiceCaseError(
                "preincident_window_end must not precede preincident_window_start"
            )
        if self.preincident_window_end > self.service_call_received_at:
            raise ServiceCaseError(
                "preincident_window_end must not follow service_call_received_at"
            )
        if self.reported_incident_at is not None:
            _require_aware(self.reported_incident_at, "reported_incident_at")
            if self.reported_incident_at > self.service_call_received_at:
                raise ServiceCaseError(
                    "reported_incident_at must not follow service_call_received_at"
                )
            if self.preincident_window_end > self.reported_incident_at:
                raise ServiceCaseError(
                    "preincident_window_end must not follow reported_incident_at"
                )
        object.__setattr__(
            self,
            "service_call_reference",
            _optional_text("service_call_reference", self.service_call_reference),
        )
        object.__setattr__(
            self,
            "current_configuration_version",
            _optional_text(
                "current_configuration_version",
                self.current_configuration_version,
            ),
        )
        for name in (
            "evidence_ids",
            "plant_reported_context_ids",
            "working_explanation_ids",
            "missing_evidence_request_ids",
        ):
            object.__setattr__(
                self,
                name,
                _text_tuple(name, getattr(self, name), allow_empty=True),
            )
        departure = self.first_detected_departure
        if departure is not None:
            if departure.asset_id != self.asset_id:
                raise ServiceCaseError(
                    "first_detected_departure asset_id must match service case asset_id"
                )
            if not (
                self.preincident_window_start
                <= departure.observed_at
                <= self.preincident_window_end
            ):
                raise ServiceCaseError(
                    "first_detected_departure must fall inside the preincident evidence window"
                )



def validate_plant_reported_context_binding(
    service_case: ServiceCase,
    context: PlantReportedContext,
) -> None:
    """Verify one reported-context record is identity-bound to the service case."""

    if context.service_case_id != service_case.service_case_id:
        raise ServiceCaseError(
            "plant-reported context service_case_id must match service case"
        )
    if context.asset_id != service_case.asset_id:
        raise ServiceCaseError("plant-reported context asset_id must match service case")
    if context.context_id not in service_case.plant_reported_context_ids:
        raise ServiceCaseError(
            "plant-reported context must be referenced by the service case"
        )


def first_detected_departure_to_dict(value: FirstDetectedDeparture) -> dict[str, Any]:
    return {
        "departure_id": value.departure_id,
        "asset_id": value.asset_id,
        "relationship_id": value.relationship_id,
        "observed_at": value.observed_at.isoformat(),
        "expected_reference_id": value.expected_reference_id,
        "configuration_version": value.configuration_version,
        "clock_quality": value.clock_quality,
        "reason_code": value.reason_code,
        "evidence_ids": list(value.evidence_ids),
        "source_ids": list(value.source_ids),
        "calibration_id": value.calibration_id,
        "sampling_profile_id": value.sampling_profile_id,
        "root_cause_established": False,
        "incident_start_established": False,
        "causation_established": False,
    }

def plant_reported_context_to_dict(value: PlantReportedContext) -> dict[str, Any]:
    return {
        "schema_version": "linealert.plant-reported-context.v1",
        "context_id": value.context_id,
        "service_case_id": value.service_case_id,
        "asset_id": value.asset_id,
        "entered_at": value.entered_at.isoformat(),
        "entered_by": value.entered_by,
        "reported_source_class": value.reported_source_class.value,
        "reported_source": value.reported_source,
        "original_wording_or_bounded_summary": value.original_wording_or_bounded_summary,
        "source_verification_state": value.source_verification_state.value,
        "reported_time_kind": value.reported_time_kind.value,
        "reported_clock_quality": value.reported_clock_quality,
        "reported_event_start": (
            value.reported_event_start.isoformat()
            if value.reported_event_start is not None
            else None
        ),
        "reported_event_end": (
            value.reported_event_end.isoformat()
            if value.reported_event_end is not None
            else None
        ),
        "source_record_reference": value.source_record_reference,
        "plant_contact_role": value.plant_contact_role,
        "provenance": list(value.provenance),
        "direct_system_observation": False,
        "verified_source_record": False,
        "causal_claim_established": False,
        "claim_boundaries": list(PLANT_CONTEXT_CLAIM_BOUNDARIES),
    }


def service_case_to_dict(value: ServiceCase) -> dict[str, Any]:
    return {
        "schema_version": "linealert.service-case.v1",
        "service_case_id": value.service_case_id,
        "customer_id": value.customer_id,
        "site_id": value.site_id,
        "asset_id": value.asset_id,
        "opened_at": value.opened_at.isoformat(),
        "opened_by": value.opened_by,
        "service_call_received_at": value.service_call_received_at.isoformat(),
        "reported_symptom": value.reported_symptom,
        "reported_incident_at": (
            value.reported_incident_at.isoformat()
            if value.reported_incident_at is not None
            else None
        ),
        "service_call_reference": value.service_call_reference,
        "preincident_window_start": value.preincident_window_start.isoformat(),
        "preincident_window_end": value.preincident_window_end.isoformat(),
        "current_configuration_version": value.current_configuration_version,
        "status": value.status.value,
        "evidence_ids": list(value.evidence_ids),
        "plant_reported_context_ids": list(value.plant_reported_context_ids),
        "working_explanation_ids": list(value.working_explanation_ids),
        "missing_evidence_request_ids": list(value.missing_evidence_request_ids),
        "first_detected_departure": (
            first_detected_departure_to_dict(value.first_detected_departure)
            if value.first_detected_departure is not None
            else None
        ),
        "authorized_action": False,
        "claim_boundaries": list(SERVICE_CASE_CLAIM_BOUNDARIES),
    }


def _require_schema(payload: Mapping[str, Any], expected: str) -> None:
    actual = payload.get("schema_version")
    if actual != expected:
        raise ServiceCaseError(
            f"schema_version must be {expected}; received {actual!r}"
        )


def first_detected_departure_from_dict(
    payload: Mapping[str, Any],
) -> FirstDetectedDeparture:
    evidence_ids = payload.get("evidence_ids", ())
    source_ids = payload.get("source_ids", ())
    if not isinstance(evidence_ids, Sequence) or isinstance(evidence_ids, (str, bytes)):
        raise ServiceCaseError("evidence_ids must be an array")
    if not isinstance(source_ids, Sequence) or isinstance(source_ids, (str, bytes)):
        raise ServiceCaseError("source_ids must be an array")
    return FirstDetectedDeparture(
        departure_id=payload.get("departure_id", ""),
        asset_id=payload.get("asset_id", ""),
        relationship_id=payload.get("relationship_id", ""),
        observed_at=_parse_datetime("observed_at", payload.get("observed_at")),
        expected_reference_id=payload.get("expected_reference_id", ""),
        configuration_version=payload.get("configuration_version", ""),
        clock_quality=payload.get("clock_quality", ""),
        reason_code=payload.get("reason_code", ""),
        evidence_ids=tuple(evidence_ids),
        source_ids=tuple(source_ids),
        calibration_id=payload.get("calibration_id"),
        sampling_profile_id=payload.get("sampling_profile_id"),
    )


def plant_reported_context_from_dict(
    payload: Mapping[str, Any],
) -> PlantReportedContext:
    _require_schema(payload, "linealert.plant-reported-context.v1")
    provenance = payload.get("provenance", ())
    if not isinstance(provenance, Sequence) or isinstance(provenance, (str, bytes)):
        raise ServiceCaseError("provenance must be an array")
    return PlantReportedContext(
        context_id=payload.get("context_id", ""),
        service_case_id=payload.get("service_case_id", ""),
        asset_id=payload.get("asset_id", ""),
        entered_at=_parse_datetime("entered_at", payload.get("entered_at")),
        entered_by=payload.get("entered_by", ""),
        reported_source_class=_enum_value(
            PlantContextSourceClass,
            "reported_source_class",
            payload.get("reported_source_class"),
        ),
        reported_source=payload.get("reported_source", ""),
        original_wording_or_bounded_summary=payload.get(
            "original_wording_or_bounded_summary",
            "",
        ),
        source_verification_state=_enum_value(
            PlantContextVerificationState,
            "source_verification_state",
            payload.get("source_verification_state"),
        ),
        reported_time_kind=_enum_value(
            ReportedTimeKind,
            "reported_time_kind",
            payload.get("reported_time_kind"),
        ),
        reported_clock_quality=payload.get("reported_clock_quality", ""),
        provenance=tuple(provenance),
        reported_event_start=_optional_datetime(
            "reported_event_start",
            payload.get("reported_event_start"),
        ),
        reported_event_end=_optional_datetime(
            "reported_event_end",
            payload.get("reported_event_end"),
        ),
        source_record_reference=payload.get("source_record_reference"),
        plant_contact_role=payload.get("plant_contact_role"),
    )


def service_case_from_dict(payload: Mapping[str, Any]) -> ServiceCase:
    _require_schema(payload, "linealert.service-case.v1")
    tuple_fields: dict[str, tuple[str, ...]] = {}
    for name in (
        "evidence_ids",
        "plant_reported_context_ids",
        "working_explanation_ids",
        "missing_evidence_request_ids",
    ):
        raw = payload.get(name, ())
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise ServiceCaseError(f"{name} must be an array")
        tuple_fields[name] = tuple(raw)

    departure_raw = payload.get("first_detected_departure")
    if departure_raw is not None and not isinstance(departure_raw, Mapping):
        raise ServiceCaseError("first_detected_departure must be an object or null")
    return ServiceCase(
        service_case_id=payload.get("service_case_id", ""),
        customer_id=payload.get("customer_id", ""),
        site_id=payload.get("site_id", ""),
        asset_id=payload.get("asset_id", ""),
        opened_at=_parse_datetime("opened_at", payload.get("opened_at")),
        opened_by=payload.get("opened_by", ""),
        service_call_received_at=_parse_datetime(
            "service_call_received_at",
            payload.get("service_call_received_at"),
        ),
        reported_symptom=payload.get("reported_symptom", ""),
        preincident_window_start=_parse_datetime(
            "preincident_window_start",
            payload.get("preincident_window_start"),
        ),
        preincident_window_end=_parse_datetime(
            "preincident_window_end",
            payload.get("preincident_window_end"),
        ),
        status=_enum_value(ServiceCaseStatus, "status", payload.get("status", "open")),
        reported_incident_at=_optional_datetime(
            "reported_incident_at",
            payload.get("reported_incident_at"),
        ),
        service_call_reference=payload.get("service_call_reference"),
        current_configuration_version=payload.get("current_configuration_version"),
        first_detected_departure=(
            first_detected_departure_from_dict(departure_raw)
            if departure_raw is not None
            else None
        ),
        **tuple_fields,
    )
