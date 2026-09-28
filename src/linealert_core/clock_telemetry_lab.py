"""Read-only lab fixture adapter for event-bound clock offset evidence.

No device clock is queried or corrected. These samples are synthetic and their
reference topology is a declared test binding, not verified plant authority.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .clock_evidence import ClockObservation, ClockTelemetryProvenance
from .events import MachineEvent
from .streaming import StreamEnvelope


class ClockTelemetryLabError(ValueError):
    """Malformed lab fixture or conflicting source declaration."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClockTelemetryLabError(f"{name} must be non-empty")
    return value


def _time(value: Any, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ClockTelemetryLabError(f"{name} must be timezone-aware")
    return value


def _number(value: Any, name: str, *, maximum: float | None = None) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        or (maximum is not None and value > maximum)
    ):
        raise ClockTelemetryLabError(f"{name} must be finite and within declared bounds")
    return float(value)


def _path(value: Any, reference_id: str, clock_id: str) -> tuple[str, ...]:
    if (
        not isinstance(value, tuple)
        or len(value) < 2
        or any(not isinstance(node, str) or not node.strip() for node in value)
        or len(value) != len(set(value))
        or value[0] != reference_id
        or value[-1] != clock_id
    ):
        raise ClockTelemetryLabError(
            "reference_path must be an exact acyclic reference-to-clock path"
        )
    return value


@dataclass(frozen=True, slots=True)
class ClockSourceBinding:
    binding_id: str
    source_id: str
    clock_id: str
    reference_clock_id: str
    reference_path: tuple[str, ...]
    firmware_version: str
    configuration_version: str
    calibration_id: str
    sampling_profile_id: str
    max_sample_age_seconds: float

    def __post_init__(self) -> None:
        for name in (
            "binding_id",
            "source_id",
            "clock_id",
            "reference_clock_id",
            "firmware_version",
            "configuration_version",
            "calibration_id",
            "sampling_profile_id",
        ):
            _text(getattr(self, name), name)
        _path(self.reference_path, self.reference_clock_id, self.clock_id)
        _number(self.max_sample_age_seconds, "max_sample_age_seconds", maximum=86400)


@dataclass(frozen=True, slots=True)
class ClockTelemetrySample:
    sample_id: str
    binding_id: str
    source_id: str
    clock_id: str
    reference_clock_id: str
    reference_path: tuple[str, ...]
    firmware_version: str
    configuration_version: str
    calibration_id: str
    sampling_profile_id: str
    synchronization_method: str
    synchronization_state: str
    measurement_method: str
    sampled_at_reference: datetime
    valid_until_reference: datetime
    offset_ms: float
    uncertainty_ms: float
    maximum_drift_ppm: float
    source_classification: str = "synthetic_lab_telemetry"

    def __post_init__(self) -> None:
        for name in (
            "sample_id",
            "binding_id",
            "source_id",
            "clock_id",
            "reference_clock_id",
            "firmware_version",
            "configuration_version",
            "calibration_id",
            "sampling_profile_id",
            "synchronization_method",
            "measurement_method",
        ):
            _text(getattr(self, name), name)
        _path(self.reference_path, self.reference_clock_id, self.clock_id)
        if self.source_classification != "synthetic_lab_telemetry":
            raise ClockTelemetryLabError("lab adapter accepts synthetic_lab_telemetry only")
        if self.synchronization_state not in {"LOCKED", "DEGRADED", "UNLOCKED", "UNKNOWN"}:
            raise ClockTelemetryLabError("unsupported synchronization_state")
        _time(self.sampled_at_reference, "sampled_at_reference")
        _time(self.valid_until_reference, "valid_until_reference")
        if self.valid_until_reference <= self.sampled_at_reference:
            raise ClockTelemetryLabError("sample validity interval must be positive")
        if (
            isinstance(self.offset_ms, bool)
            or not isinstance(self.offset_ms, (int, float))
            or not math.isfinite(self.offset_ms)
        ):
            raise ClockTelemetryLabError("offset_ms must be finite")
        _number(self.uncertainty_ms, "uncertainty_ms")
        _number(self.maximum_drift_ppm, "maximum_drift_ppm", maximum=999999)


@dataclass(frozen=True, slots=True)
class ClockStepBoundary:
    """Supplied lab notice that this source clock stepped within a reference-time bracket."""

    boundary_id: str
    binding_id: str
    source_id: str
    clock_id: str
    reference_clock_id: str
    reference_path: tuple[str, ...]
    earliest_reference: datetime
    latest_reference: datetime
    observation_method: str
    source_classification: str = "synthetic_lab_telemetry"

    def __post_init__(self) -> None:
        for name in (
            "boundary_id",
            "binding_id",
            "source_id",
            "clock_id",
            "reference_clock_id",
            "observation_method",
        ):
            _text(getattr(self, name), name)
        _path(self.reference_path, self.reference_clock_id, self.clock_id)
        if self.source_classification != "synthetic_lab_telemetry":
            raise ClockTelemetryLabError("step boundary must be synthetic_lab_telemetry")
        _time(self.earliest_reference, "earliest_reference")
        _time(self.latest_reference, "latest_reference")
        if self.latest_reference < self.earliest_reference:
            raise ClockTelemetryLabError("step boundary reference bracket is reversed")


@dataclass(frozen=True, slots=True)
class ClockProjectionRefusal:
    event_id: str
    source_id: str
    reason_code: str
    sample_ids: tuple[str, ...]
    retained_uncertainty: str
    step_boundary_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClockProjection:
    observation: ClockObservation | None
    refusal: ClockProjectionRefusal | None


class ClockTelemetryLabAdapter:
    """Project only one unambiguous, current lab sample for an exact source."""

    def __init__(
        self,
        bindings: tuple[ClockSourceBinding, ...],
        samples: tuple[ClockTelemetrySample, ...],
        step_boundaries: tuple[ClockStepBoundary, ...] = (),
    ) -> None:
        if not bindings or len({b.source_id for b in bindings}) != len(bindings):
            raise ClockTelemetryLabError("one exact binding per source is required")
        if len({s.sample_id for s in samples}) != len(samples):
            raise ClockTelemetryLabError("sample IDs must be unique")
        if len({b.boundary_id for b in step_boundaries}) != len(step_boundaries):
            raise ClockTelemetryLabError("step boundary IDs must be unique")
        self._bindings = {b.source_id: b for b in bindings}
        if any(b.source_id not in self._bindings for b in step_boundaries):
            raise ClockTelemetryLabError("step boundary needs an exact source binding")
        self._samples = tuple(sorted(samples, key=lambda s: s.sample_id))
        self._step_boundaries = tuple(sorted(step_boundaries, key=lambda b: b.boundary_id))

    @staticmethod
    def _refuse(
        event: MachineEvent,
        code: str,
        samples: tuple[ClockTelemetrySample, ...],
        detail: str,
        boundaries: tuple[ClockStepBoundary, ...] = (),
    ) -> ClockProjection:
        return ClockProjection(
            None,
            ClockProjectionRefusal(
                event_id=event.event_id,
                source_id=event.source_id,
                reason_code=code,
                sample_ids=tuple(s.sample_id for s in samples),
                retained_uncertainty=detail,
                step_boundary_ids=tuple(b.boundary_id for b in boundaries),
            ),
        )

    def project(self, event: MachineEvent) -> ClockProjection:
        binding = self._bindings.get(event.source_id)
        if binding is None:
            return self._refuse(event, "CLOCK.BINDING_MISSING", (), "No lab source clock binding.")
        samples = tuple(s for s in self._samples if s.source_id == event.source_id)
        boundaries = tuple(b for b in self._step_boundaries if b.source_id == event.source_id)
        if any(
            b.binding_id != binding.binding_id
            or b.clock_id != binding.clock_id
            or b.reference_clock_id != binding.reference_clock_id
            or b.reference_path != binding.reference_path
            for b in boundaries
        ):
            return self._refuse(
                event,
                "CLOCK.STEP_BINDING_CONFLICT",
                samples,
                "Step boundary conflicts with the exact source clock or reference path.",
                boundaries,
            )
        if not samples:
            return self._refuse(event, "CLOCK.SAMPLE_MISSING", (), "No source offset sample.")
        identity = (
            "binding_id",
            "clock_id",
            "reference_clock_id",
            "reference_path",
            "firmware_version",
            "configuration_version",
            "calibration_id",
            "sampling_profile_id",
        )
        if any(
            any(getattr(s, name) != getattr(binding, name) for name in identity) for s in samples
        ):
            return self._refuse(
                event,
                "CLOCK.BINDING_CONFLICT",
                samples,
                "Sample clock, reference path, firmware, configuration, calibration or "
                "sampling identity conflicts with the exact lab binding.",
            )

        eligible: list[tuple[ClockTelemetrySample, datetime, float, float, float]] = []
        blocked: list[tuple[ClockTelemetrySample, tuple[ClockStepBoundary, ...]]] = []
        for sample in samples:
            try:
                candidate = event.timestamp - timedelta(milliseconds=sample.offset_ms)
                age = (candidate - sample.sampled_at_reference).total_seconds()
                if age < 0 or age > binding.max_sample_age_seconds:
                    continue
                # ppm × seconds / 1000 gives milliseconds. Solve the small
                # circular age/uncertainty term conservatively.
                rate_ms_per_second = sample.maximum_drift_ppm / 1000
                uncertainty = (sample.uncertainty_ms + rate_ms_per_second * age) / (
                    1 - sample.maximum_drift_ppm / 1_000_000
                )
                if (
                    candidate - timedelta(milliseconds=uncertainty) < sample.sampled_at_reference
                    or candidate + timedelta(milliseconds=uncertainty)
                    >= sample.valid_until_reference
                ):
                    continue
            except OverflowError:
                continue
            lower = candidate - timedelta(milliseconds=uncertainty)
            upper = candidate + timedelta(milliseconds=uncertainty)
            crossed = tuple(
                b
                for b in boundaries
                if upper >= b.earliest_reference
                and (
                    lower <= b.latest_reference
                    or sample.sampled_at_reference <= b.latest_reference
                )
            )
            if crossed:
                blocked.append((sample, crossed))
                continue
            eligible.append(
                (sample, candidate, age, uncertainty, uncertainty - sample.uncertainty_ms)
            )
        if not eligible:
            if blocked:
                return self._refuse(
                    event,
                    "CLOCK.STEP_WINDOW_UNQUALIFIED",
                    tuple(sample for sample, _ in blocked),
                    "The event interval touches a step bracket or its sample predates that step.",
                    tuple({b.boundary_id: b for _, bs in blocked for b in bs}.values()),
                )
            return self._refuse(
                event,
                "CLOCK.SAMPLE_OUTSIDE_VALIDITY",
                samples,
                "No sample bounds the event within its age and validity window.",
            )
        if len(eligible) != 1:
            return self._refuse(
                event,
                "CLOCK.SAMPLE_AMBIGUOUS",
                tuple(item[0] for item in eligible),
                "Multiple source samples qualify; no latest-wins selection is permitted.",
            )
        sample, candidate, age, uncertainty, drift_allowance = eligible[0]
        lower = candidate - timedelta(milliseconds=uncertainty)
        if sample.synchronization_state != "LOCKED":
            return self._refuse(
                event,
                "CLOCK.SYNC_UNQUALIFIED",
                (sample,),
                "A declared source sample is not in the locked synchronization state.",
            )
        preceding_steps = tuple(b for b in boundaries if b.latest_reference < lower)
        last_step = (
            max(preceding_steps, key=lambda b: (b.latest_reference, b.boundary_id))
            if preceding_steps
            else None
        )
        provenance = ClockTelemetryProvenance(
            sample_id=sample.sample_id,
            binding_id=binding.binding_id,
            sampled_at_reference=sample.sampled_at_reference,
            valid_until_reference=sample.valid_until_reference,
            synchronization_method=sample.synchronization_method,
            sample_measurement_method=sample.measurement_method,
            reference_path=sample.reference_path,
            firmware_version=sample.firmware_version,
            configuration_version=sample.configuration_version,
            calibration_id=sample.calibration_id,
            sampling_profile_id=sample.sampling_profile_id,
            source_classification=sample.source_classification,
            sample_uncertainty_ms=sample.uncertainty_ms,
            max_sample_age_seconds=binding.max_sample_age_seconds,
            maximum_drift_ppm=sample.maximum_drift_ppm,
            drift_allowance_ms=drift_allowance,
            age_seconds=age,
            last_step_boundary_id=last_step.boundary_id if last_step else None,
            last_step_earliest_reference=last_step.earliest_reference if last_step else None,
            last_step_latest_reference=last_step.latest_reference if last_step else None,
            last_step_observation_method=last_step.observation_method if last_step else None,
        )
        return ClockProjection(
            ClockObservation(
                event_id=event.event_id,
                source_id=event.source_id,
                clock_id=sample.clock_id,
                reference_clock_id=sample.reference_clock_id,
                source_timestamp=event.timestamp,
                observed_at_reference=candidate,
                offset_ms=sample.offset_ms,
                uncertainty_ms=uncertainty,
                measurement_method="synthetic_lab_telemetry_projection",
                evidence_id=f"{sample.sample_id}:{event.event_id}",
                telemetry_provenance=provenance,
            ),
            None,
        )

    def annotate(self, envelope: StreamEnvelope) -> tuple[StreamEnvelope, ClockProjection]:
        """Attach qualified evidence without modifying the event or transport claim."""

        if envelope.clock_observation is not None:
            raise ClockTelemetryLabError("existing clock observation cannot be overwritten")
        result = self.project(envelope.event)
        if result.observation is None:
            return envelope, result
        return replace(envelope, clock_observation=result.observation), result


def load_clock_telemetry_lab(path: str | Path) -> ClockTelemetryLabAdapter:
    """Read one size-bounded, exact local JSON fixture; never fetch a remote source."""

    source = Path(path)
    if source.stat().st_size > 1_000_000:
        raise ClockTelemetryLabError("lab fixture exceeds one MiB")
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != "linealert.clock-telemetry-lab.v1":
        raise ClockTelemetryLabError("unsupported lab clock fixture schema")
    if raw.get("classification") != "synthetic_lab_only":
        raise ClockTelemetryLabError("lab fixture must declare synthetic_lab_only")
    bindings_raw, samples_raw = raw.get("bindings"), raw.get("samples")
    boundaries_raw = raw.get("step_boundaries", [])
    if not all(isinstance(value, list) for value in (bindings_raw, samples_raw, boundaries_raw)):
        raise ClockTelemetryLabError("bindings, samples and step_boundaries must be arrays")
    try:
        bindings = tuple(
            ClockSourceBinding(**{**item, "reference_path": tuple(item["reference_path"])})
            for item in bindings_raw
        )
        samples = tuple(
            ClockTelemetrySample(
                **{
                    **item,
                    "reference_path": tuple(item["reference_path"]),
                    "sampled_at_reference": datetime.fromisoformat(item["sampled_at_reference"]),
                    "valid_until_reference": datetime.fromisoformat(item["valid_until_reference"]),
                }
            )
            for item in samples_raw
        )
        boundaries = tuple(
            ClockStepBoundary(
                **{
                    **item,
                    "reference_path": tuple(item["reference_path"]),
                    "earliest_reference": datetime.fromisoformat(item["earliest_reference"]),
                    "latest_reference": datetime.fromisoformat(item["latest_reference"]),
                }
            )
            for item in boundaries_raw
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ClockTelemetryLabError("invalid lab clock fixture record") from exc
    return ClockTelemetryLabAdapter(bindings, samples, boundaries)
