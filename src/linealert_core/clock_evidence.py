"""Event-bound clock evidence and conservative cross-clock timing assessment.

Offset is signed: source clock time minus reference clock time. Neither source
timestamps nor machine events are rewritten by this module.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any


class ClockEvidenceError(ValueError):
    """Malformed or mismatched clock evidence."""


class IntervalDisposition(StrEnum):
    EARLY = "early"
    WITHIN = "within"
    LATE = "late"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class ClockTelemetryProvenance:
    """Exact lab sample and binding retained with an event projection."""

    sample_id: str
    binding_id: str
    sampled_at_reference: datetime
    valid_until_reference: datetime
    synchronization_method: str
    sample_measurement_method: str
    reference_path: tuple[str, ...]
    firmware_version: str
    configuration_version: str
    calibration_id: str
    sampling_profile_id: str
    source_classification: str
    sample_uncertainty_ms: float
    max_sample_age_seconds: float
    maximum_drift_ppm: float
    drift_allowance_ms: float
    age_seconds: float
    last_step_boundary_id: str | None = None
    last_step_earliest_reference: datetime | None = None
    last_step_latest_reference: datetime | None = None
    last_step_observation_method: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "sample_id",
            "binding_id",
            "synchronization_method",
            "sample_measurement_method",
            "firmware_version",
            "configuration_version",
            "calibration_id",
            "sampling_profile_id",
            "source_classification",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ClockEvidenceError(f"{name} must be non-empty")
        if (
            not isinstance(self.reference_path, tuple)
            or len(self.reference_path) < 2
            or any(not isinstance(node, str) or not node.strip() for node in self.reference_path)
        ):
            raise ClockEvidenceError("reference_path must contain exact reference and clock nodes")
        for name in ("sampled_at_reference", "valid_until_reference"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ClockEvidenceError(f"{name} must be timezone-aware")
        if self.sampled_at_reference >= self.valid_until_reference:
            raise ClockEvidenceError("telemetry validity interval must be positive")
        for name in (
            "sample_uncertainty_ms",
            "max_sample_age_seconds",
            "maximum_drift_ppm",
            "drift_allowance_ms",
            "age_seconds",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ClockEvidenceError(f"{name} must be finite and non-negative")
        if self.maximum_drift_ppm >= 1_000_000:
            raise ClockEvidenceError("maximum_drift_ppm must be below one million")
        step_fields = (
            self.last_step_boundary_id,
            self.last_step_earliest_reference,
            self.last_step_latest_reference,
            self.last_step_observation_method,
        )
        if any(field is None for field in step_fields) and not all(
            field is None for field in step_fields
        ):
            raise ClockEvidenceError("step boundary provenance must be complete")
        if self.last_step_boundary_id is not None:
            if (
                not isinstance(self.last_step_boundary_id, str)
                or not self.last_step_boundary_id.strip()
                or not isinstance(self.last_step_observation_method, str)
                or not self.last_step_observation_method.strip()
            ):
                raise ClockEvidenceError("step boundary identity and method must be non-empty")
            boundary_start = self.last_step_earliest_reference
            boundary_end = self.last_step_latest_reference
            if (
                not isinstance(boundary_start, datetime)
                or boundary_start.tzinfo is None
                or boundary_start.utcoffset() is None
                or not isinstance(boundary_end, datetime)
                or boundary_end.tzinfo is None
                or boundary_end.utcoffset() is None
                or boundary_start > boundary_end
                or self.sampled_at_reference <= boundary_end
            ):
                raise ClockEvidenceError("sample must follow the retained step boundary")


@dataclass(frozen=True, slots=True)
class ClockObservation:
    """One externally supplied offset bound for one exact source event.

    The uncertainty must include the complete measurement path. A mere NTP/PTP
    configuration flag, source/server arrival difference, or ingestion delay is
    insufficient to construct this record.
    """

    event_id: str
    source_id: str
    clock_id: str
    reference_clock_id: str
    source_timestamp: datetime
    observed_at_reference: datetime
    offset_ms: float
    uncertainty_ms: float
    measurement_method: str
    evidence_id: str
    telemetry_provenance: ClockTelemetryProvenance | None = None

    def __post_init__(self) -> None:
        for name in (
            "event_id",
            "source_id",
            "clock_id",
            "reference_clock_id",
            "measurement_method",
            "evidence_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ClockEvidenceError(f"{name} must be non-empty")
        for name in ("source_timestamp", "observed_at_reference"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ClockEvidenceError(f"{name} must be timezone-aware")
        for name in ("offset_ms", "uncertainty_ms"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ClockEvidenceError(f"{name} must be finite")
        if self.uncertainty_ms < 0:
            raise ClockEvidenceError("uncertainty_ms must be non-negative")
        implied_offset_ms = (
            self.source_timestamp - self.observed_at_reference
        ).total_seconds() * 1000
        if abs(implied_offset_ms - self.offset_ms) > self.uncertainty_ms + 1e-6:
            raise ClockEvidenceError(
                "event reference time is inconsistent with the declared offset bound"
            )
        provenance = self.telemetry_provenance
        if provenance is not None:
            if not isinstance(provenance, ClockTelemetryProvenance) or (
                provenance.reference_path[0] != self.reference_clock_id
                or provenance.reference_path[-1] != self.clock_id
            ):
                raise ClockEvidenceError("telemetry provenance does not match clock path")
            lower = self.observed_at_reference - timedelta(milliseconds=self.uncertainty_ms)
            upper = self.observed_at_reference + timedelta(milliseconds=self.uncertainty_ms)
            if lower < provenance.sampled_at_reference or upper >= provenance.valid_until_reference:
                raise ClockEvidenceError("event reference interval exceeds telemetry validity")
            age = (self.observed_at_reference - provenance.sampled_at_reference).total_seconds()
            expanded = (
                provenance.sample_uncertainty_ms + provenance.maximum_drift_ppm / 1000 * age
            ) / (1 - provenance.maximum_drift_ppm / 1_000_000)
            if (
                age < 0
                or age > provenance.max_sample_age_seconds
                or not math.isclose(age, provenance.age_seconds, abs_tol=1e-6)
                or not math.isclose(
                    self.uncertainty_ms,
                    provenance.sample_uncertainty_ms + provenance.drift_allowance_ms,
                    abs_tol=1e-6,
                )
                or not math.isclose(self.uncertainty_ms, expanded, abs_tol=1e-6)
            ):
                raise ClockEvidenceError("telemetry age or uncertainty derivation mismatch")


@dataclass(frozen=True, slots=True)
class ClockIntervalAssessment:
    """A bounded estimated interval, conditional on the supplied clock evidence."""

    reference_clock_id: str
    raw_delay_ms: float
    estimated_delay_ms: float
    lower_delay_ms: float
    upper_delay_ms: float
    combined_uncertainty_ms: float
    disposition: IntervalDisposition
    start_evidence_id: str
    end_evidence_id: str
    start_observation: ClockObservation
    end_observation: ClockObservation


def _observation_to_dict(value: ClockObservation) -> dict[str, Any]:
    payload = {
        "event_id": value.event_id,
        "source_id": value.source_id,
        "clock_id": value.clock_id,
        "reference_clock_id": value.reference_clock_id,
        "source_timestamp": value.source_timestamp.isoformat(),
        "observed_at_reference": value.observed_at_reference.isoformat(),
        "offset_ms": value.offset_ms,
        "uncertainty_ms": value.uncertainty_ms,
        "measurement_method": value.measurement_method,
        "evidence_id": value.evidence_id,
    }
    if value.telemetry_provenance is not None:
        p = value.telemetry_provenance
        payload["telemetry_provenance"] = {
            "sample_id": p.sample_id,
            "binding_id": p.binding_id,
            "sampled_at_reference": p.sampled_at_reference.isoformat(),
            "valid_until_reference": p.valid_until_reference.isoformat(),
            "synchronization_method": p.synchronization_method,
            "sample_measurement_method": p.sample_measurement_method,
            "reference_path": list(p.reference_path),
            "firmware_version": p.firmware_version,
            "configuration_version": p.configuration_version,
            "calibration_id": p.calibration_id,
            "sampling_profile_id": p.sampling_profile_id,
            "source_classification": p.source_classification,
            "sample_uncertainty_ms": p.sample_uncertainty_ms,
            "max_sample_age_seconds": p.max_sample_age_seconds,
            "maximum_drift_ppm": p.maximum_drift_ppm,
            "drift_allowance_ms": p.drift_allowance_ms,
            "age_seconds": p.age_seconds,
        }
        if p.last_step_boundary_id is not None:
            assert p.last_step_earliest_reference is not None
            assert p.last_step_latest_reference is not None
            payload["telemetry_provenance"]["last_step_boundary_id"] = p.last_step_boundary_id
            payload["telemetry_provenance"]["last_step_earliest_reference"] = (
                p.last_step_earliest_reference.isoformat()
            )
            payload["telemetry_provenance"]["last_step_latest_reference"] = (
                p.last_step_latest_reference.isoformat()
            )
            payload["telemetry_provenance"]["last_step_observation_method"] = (
                p.last_step_observation_method
            )
    return payload


def _provenance_from_dict(raw: Mapping[str, Any]) -> ClockTelemetryProvenance:
    try:
        path = raw["reference_path"]
        if not isinstance(path, list):
            raise ClockEvidenceError("reference_path must be a list")
        return ClockTelemetryProvenance(
            sample_id=raw["sample_id"],
            binding_id=raw["binding_id"],
            sampled_at_reference=datetime.fromisoformat(raw["sampled_at_reference"]),
            valid_until_reference=datetime.fromisoformat(raw["valid_until_reference"]),
            synchronization_method=raw["synchronization_method"],
            sample_measurement_method=raw["sample_measurement_method"],
            reference_path=tuple(path),
            firmware_version=raw["firmware_version"],
            configuration_version=raw["configuration_version"],
            calibration_id=raw["calibration_id"],
            sampling_profile_id=raw["sampling_profile_id"],
            source_classification=raw["source_classification"],
            sample_uncertainty_ms=raw["sample_uncertainty_ms"],
            max_sample_age_seconds=raw["max_sample_age_seconds"],
            maximum_drift_ppm=raw["maximum_drift_ppm"],
            drift_allowance_ms=raw["drift_allowance_ms"],
            age_seconds=raw["age_seconds"],
            last_step_boundary_id=raw.get("last_step_boundary_id"),
            last_step_earliest_reference=(
                datetime.fromisoformat(raw["last_step_earliest_reference"])
                if raw.get("last_step_earliest_reference") is not None
                else None
            ),
            last_step_latest_reference=(
                datetime.fromisoformat(raw["last_step_latest_reference"])
                if raw.get("last_step_latest_reference") is not None
                else None
            ),
            last_step_observation_method=raw.get("last_step_observation_method"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ClockEvidenceError("invalid retained clock telemetry provenance") from exc


def _observation_from_dict(raw: Mapping[str, Any]) -> ClockObservation:
    try:
        provenance = raw.get("telemetry_provenance")
        if provenance is not None and not isinstance(provenance, Mapping):
            raise ClockEvidenceError("telemetry_provenance must be an object")
        return ClockObservation(
            event_id=raw["event_id"],
            source_id=raw["source_id"],
            clock_id=raw["clock_id"],
            reference_clock_id=raw["reference_clock_id"],
            source_timestamp=datetime.fromisoformat(raw["source_timestamp"]),
            observed_at_reference=datetime.fromisoformat(raw["observed_at_reference"]),
            offset_ms=raw["offset_ms"],
            uncertainty_ms=raw["uncertainty_ms"],
            measurement_method=raw["measurement_method"],
            evidence_id=raw["evidence_id"],
            telemetry_provenance=(
                _provenance_from_dict(provenance) if provenance is not None else None
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ClockEvidenceError("invalid retained clock observation") from exc


def interval_assessment_to_dict(value: ClockIntervalAssessment) -> dict[str, Any]:
    """Preserve every bound and provenance identifier in a JSON payload."""

    return {
        "reference_clock_id": value.reference_clock_id,
        "raw_delay_ms": value.raw_delay_ms,
        "estimated_delay_ms": value.estimated_delay_ms,
        "lower_delay_ms": value.lower_delay_ms,
        "upper_delay_ms": value.upper_delay_ms,
        "combined_uncertainty_ms": value.combined_uncertainty_ms,
        "disposition": value.disposition.value,
        "start_evidence_id": value.start_evidence_id,
        "end_evidence_id": value.end_evidence_id,
        "start_observation": _observation_to_dict(value.start_observation),
        "end_observation": _observation_to_dict(value.end_observation),
    }


def interval_assessment_from_dict(raw: Mapping[str, Any]) -> ClockIntervalAssessment:
    """Rebuild a retained bound, rejecting malformed or inconsistent values."""

    try:
        value = ClockIntervalAssessment(
            reference_clock_id=raw["reference_clock_id"],
            raw_delay_ms=raw["raw_delay_ms"],
            estimated_delay_ms=raw["estimated_delay_ms"],
            lower_delay_ms=raw["lower_delay_ms"],
            upper_delay_ms=raw["upper_delay_ms"],
            combined_uncertainty_ms=raw["combined_uncertainty_ms"],
            disposition=IntervalDisposition(raw["disposition"]),
            start_evidence_id=raw["start_evidence_id"],
            end_evidence_id=raw["end_evidence_id"],
            start_observation=_observation_from_dict(raw["start_observation"]),
            end_observation=_observation_from_dict(raw["end_observation"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ClockEvidenceError("invalid retained clock interval assessment") from exc
    for name in ("reference_clock_id", "start_evidence_id", "end_evidence_id"):
        if not isinstance(getattr(value, name), str) or not getattr(value, name).strip():
            raise ClockEvidenceError(f"invalid retained {name}")
    numbers = (
        value.raw_delay_ms,
        value.estimated_delay_ms,
        value.lower_delay_ms,
        value.upper_delay_ms,
        value.combined_uncertainty_ms,
    )
    if any(
        isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n)
        for n in numbers
    ):
        raise ClockEvidenceError("retained clock interval must contain finite numbers")
    if value.combined_uncertainty_ms < 0 or value.lower_delay_ms > value.upper_delay_ms:
        raise ClockEvidenceError("invalid retained clock interval bounds")
    if (
        value.start_observation.evidence_id != value.start_evidence_id
        or value.end_observation.evidence_id != value.end_evidence_id
        or value.start_observation.reference_clock_id != value.reference_clock_id
        or value.end_observation.reference_clock_id != value.reference_clock_id
    ):
        raise ClockEvidenceError("retained clock observation identity mismatch")
    if (
        not math.isclose(
            value.estimated_delay_ms,
            value.raw_delay_ms
            + value.start_observation.offset_ms
            - value.end_observation.offset_ms,
            abs_tol=1e-6,
        )
        or not math.isclose(
            value.combined_uncertainty_ms,
            value.start_observation.uncertainty_ms + value.end_observation.uncertainty_ms,
            abs_tol=1e-6,
        )
        or not math.isclose(
            value.lower_delay_ms,
            value.estimated_delay_ms - value.combined_uncertainty_ms,
            abs_tol=1e-6,
        )
        or not math.isclose(
            value.upper_delay_ms,
            value.estimated_delay_ms + value.combined_uncertainty_ms,
            abs_tol=1e-6,
        )
    ):
        raise ClockEvidenceError("retained clock interval arithmetic mismatch")
    return value


def assess_cross_clock_interval(
    *,
    start: ClockObservation,
    end: ClockObservation,
    raw_delay_ms: float,
    min_delay_ms: float,
    max_delay_ms: float,
    max_combined_uncertainty_ms: float,
) -> ClockIntervalAssessment:
    """Bound an event pair using exact per-event offsets on one reference clock.

    Interval classifications are supported only if the entire bound lies on
    one side of both rule limits. This does not verify either clock observation.
    """

    values = (raw_delay_ms, min_delay_ms, max_delay_ms, max_combined_uncertainty_ms)
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values
    ):
        raise ClockEvidenceError("interval inputs must be finite numbers")
    if min_delay_ms < 0 or max_delay_ms < min_delay_ms or max_combined_uncertainty_ms < 0:
        raise ClockEvidenceError("invalid interval limits or uncertainty requirement")
    if start.reference_clock_id != end.reference_clock_id:
        raise ClockEvidenceError("clock observations do not share an exact reference clock")
    if start.event_id == end.event_id or start.evidence_id == end.evidence_id:
        raise ClockEvidenceError("event and clock evidence identities must be distinct")

    bound = start.uncertainty_ms + end.uncertainty_ms
    estimate = raw_delay_ms + start.offset_ms - end.offset_ms
    low, high = estimate - bound, estimate + bound
    if bound > max_combined_uncertainty_ms:
        disposition = IntervalDisposition.INDETERMINATE
    elif high < min_delay_ms:
        disposition = IntervalDisposition.EARLY
    elif low > max_delay_ms:
        disposition = IntervalDisposition.LATE
    elif low >= min_delay_ms and high <= max_delay_ms:
        disposition = IntervalDisposition.WITHIN
    else:
        disposition = IntervalDisposition.INDETERMINATE
    return ClockIntervalAssessment(
        reference_clock_id=start.reference_clock_id,
        raw_delay_ms=raw_delay_ms,
        estimated_delay_ms=estimate,
        lower_delay_ms=low,
        upper_delay_ms=high,
        combined_uncertainty_ms=bound,
        disposition=disposition,
        start_evidence_id=start.evidence_id,
        end_evidence_id=end.evidence_id,
        start_observation=start,
        end_observation=end,
    )


@dataclass(frozen=True, slots=True)
class ClockTrendAssessment:
    """An observed offset trend; it does not identify a faulty time source."""

    clock_id: str
    reference_clock_id: str
    disposition: str
    rate_ppm: float | None
    evidence_ids: tuple[str, ...]


def assess_clock_drift(
    observations: tuple[ClockObservation, ...],
    *,
    minimum_rate_ppm: float,
    minimum_step_ms: float = 50.0,
) -> ClockTrendAssessment:
    """Flag a resolved sustained slope or isolated step across a bounded series.

    An unresolved series stays indeterminate; a jump is not called drift. More
    samples or independent reference telemetry are needed to locate a cause.
    """

    if len(observations) < 3:
        raise ClockEvidenceError("drift assessment requires at least three observations")
    if not math.isfinite(minimum_rate_ppm) or minimum_rate_ppm <= 0:
        raise ClockEvidenceError("minimum_rate_ppm must be positive and finite")
    if not math.isfinite(minimum_step_ms) or minimum_step_ms <= 0:
        raise ClockEvidenceError("minimum_step_ms must be positive and finite")
    first = observations[0]
    if any(
        (o.clock_id, o.source_id, o.reference_clock_id)
        != (first.clock_id, first.source_id, first.reference_clock_id)
        for o in observations
    ):
        raise ClockEvidenceError("drift series must use one clock, source, and reference")
    if len({o.evidence_id for o in observations}) != len(observations):
        raise ClockEvidenceError("drift series has duplicate evidence identities")
    intervals = [
        (b.observed_at_reference - a.observed_at_reference).total_seconds()
        for a, b in zip(observations, observations[1:], strict=False)
    ]
    if any(dt <= 0 for dt in intervals):
        raise ClockEvidenceError("drift observations must be in increasing reference time")
    deltas = [
        b.offset_ms - a.offset_ms for a, b in zip(observations, observations[1:], strict=False)
    ]
    resolved = all(
        abs(delta) > a.uncertainty_ms + b.uncertainty_ms
        for delta, a, b in zip(deltas, observations, observations[1:], strict=False)
    )
    same_direction = all(delta > 0 for delta in deltas) or all(delta < 0 for delta in deltas)
    rates = [delta * 1000.0 / dt for delta, dt in zip(deltas, intervals, strict=True)]
    consistent = max(rates) - min(rates) <= max(minimum_rate_ppm, abs(sum(rates) / len(rates)))
    rate = (observations[-1].offset_ms - first.offset_ms) * 1000.0 / sum(intervals)
    step_indices = [
        i
        for i, delta in enumerate(deltas)
        if abs(delta) >= minimum_step_ms
        and abs(delta) > observations[i].uncertainty_ms + observations[i + 1].uncertainty_ms
    ]
    isolated_step = (
        len(observations) >= 4
        and len(step_indices) == 1
        and 0 < step_indices[0] < len(deltas) - 1
        and all(
            abs(delta) <= minimum_step_ms / 4
            for i, delta in enumerate(deltas)
            if i != step_indices[0]
        )
    )
    if isolated_step:
        disposition = "STEP_CANDIDATE"
        rate = None
    elif resolved and same_direction and consistent and abs(rate) >= minimum_rate_ppm:
        disposition = "DRIFT_CANDIDATE"
    else:
        disposition = "INDETERMINATE"
    return ClockTrendAssessment(
        clock_id=first.clock_id,
        reference_clock_id=first.reference_clock_id,
        disposition=disposition,
        rate_ppm=rate,
        evidence_ids=tuple(o.evidence_id for o in observations),
    )
