"""Governed commissioned-baseline resolution and deterministic drift assessment."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType


class BaselineError(ValueError):
    """Raised when baseline records or comparisons are invalid."""


class BaselineResolutionStatus(StrEnum):
    """Outcome of resolving one operating context against the registry."""

    RESOLVED = "resolved"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


class EnvelopeStatus(StrEnum):
    """Observed value relative to the approved operating envelope."""

    BELOW = "below"
    WITHIN = "within"
    ABOVE = "above"


class DriftStatus(StrEnum):
    """Observed value relative to baseline and approved envelope."""

    WITHIN_EXPECTED_BASELINE = "within_expected_baseline"
    DRIFTED_WITHIN_ENVELOPE = "drifted_within_envelope"
    OUTSIDE_APPROVED_ENVELOPE = "outside_approved_envelope"


@dataclass(frozen=True, slots=True)
class BaselineApplicability:
    """Exact operating context required for baseline applicability."""

    asset_id: str
    component_id: str
    observation_key: str
    operating_mode: str
    configuration_version: str
    firmware_version: str
    calibration_id: str
    sampling_profile_id: str
    context_tags: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "asset_id",
            "component_id",
            "observation_key",
            "operating_mode",
            "configuration_version",
            "firmware_version",
            "calibration_id",
            "sampling_profile_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise BaselineError(f"{field_name} must be a non-empty string")

        normalized: dict[str, str] = {}
        for key, value in self.context_tags.items():
            if not isinstance(key, str) or not key.strip():
                raise BaselineError("context tag keys must be non-empty strings")
            if not isinstance(value, str) or not value.strip():
                raise BaselineError("context tag values must be non-empty strings")
            normalized[key.strip()] = value.strip()
        object.__setattr__(
            self,
            "context_tags",
            MappingProxyType(dict(sorted(normalized.items()))),
        )


@dataclass(frozen=True, slots=True)
class BaselineEvidence:
    """Source, test, time, and approval evidence for one baseline record."""

    source_id: str
    source_reference: str
    captured_start: datetime
    captured_end: datetime
    clock_quality: str
    engineering_unit: str
    sample_count: int
    test_conditions: str
    approved_by: str
    approved_at: datetime
    approval_reference: str

    def __post_init__(self) -> None:
        for field_name in (
            "source_id",
            "source_reference",
            "clock_quality",
            "engineering_unit",
            "test_conditions",
            "approved_by",
            "approval_reference",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise BaselineError(f"{field_name} must be a non-empty string")
        _require_aware(self.captured_start, "captured_start")
        _require_aware(self.captured_end, "captured_end")
        _require_aware(self.approved_at, "approved_at")
        if self.captured_end < self.captured_start:
            raise BaselineError("captured_end must not precede captured_start")
        if self.sample_count < 1:
            raise BaselineError("sample_count must be at least 1")


@dataclass(frozen=True, slots=True)
class BaselineModel:
    """Expected baseline distribution and separate approved envelope."""

    mean: float
    stddev: float
    approved_min: float
    approved_max: float

    def __post_init__(self) -> None:
        for field_name in ("mean", "stddev", "approved_min", "approved_max"):
            if not math.isfinite(getattr(self, field_name)):
                raise BaselineError(f"{field_name} must be finite")
        if self.stddev < 0.0:
            raise BaselineError("stddev must be non-negative")
        if self.approved_max < self.approved_min:
            raise BaselineError("approved_max must be >= approved_min")
        if not self.approved_min <= self.mean <= self.approved_max:
            raise BaselineError("baseline mean must be inside the approved envelope")


@dataclass(frozen=True, slots=True)
class BaselineRecord:
    """Immutable baseline record; replacement points backward to preserved history."""

    baseline_id: str
    version: str
    applicability: BaselineApplicability
    model: BaselineModel
    evidence: BaselineEvidence
    replaces_baseline_id: str | None = None

    def __post_init__(self) -> None:
        if not self.baseline_id.strip() or not self.version.strip():
            raise BaselineError("baseline_id and version must be non-empty")
        if self.replaces_baseline_id is not None:
            if not self.replaces_baseline_id.strip():
                raise BaselineError("replaces_baseline_id must not be empty")
            if self.replaces_baseline_id == self.baseline_id:
                raise BaselineError("a baseline cannot replace itself")


@dataclass(frozen=True, slots=True)
class BaselineInvalidation:
    """Append-only evidence that prevents a baseline from being selected."""

    baseline_id: str
    reason: str
    invalidated_at: datetime
    invalidated_by: str
    evidence_reference: str

    def __post_init__(self) -> None:
        for field_name in (
            "baseline_id",
            "reason",
            "invalidated_by",
            "evidence_reference",
        ):
            value = getattr(self, field_name)
            if not value.strip():
                raise BaselineError(f"{field_name} must be non-empty")
        _require_aware(self.invalidated_at, "invalidated_at")


@dataclass(frozen=True, slots=True)
class BaselineRejection:
    """Why one effective baseline did not apply to the supplied context."""

    baseline_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BaselineResolution:
    """Deterministic baseline-resolution outcome without hidden fallback."""

    status: BaselineResolutionStatus
    baseline: BaselineRecord | None
    candidate_ids: tuple[str, ...]
    rejections: tuple[BaselineRejection, ...]


@dataclass(frozen=True, slots=True)
class BaselineObservation:
    """One current observation proposed for baseline comparison."""

    applicability: BaselineApplicability
    value: float
    unit: str
    timestamp: datetime
    source_id: str
    quality: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise BaselineError("observation value must be finite")
        for field_name in ("unit", "source_id", "quality"):
            value = getattr(self, field_name)
            if not value.strip():
                raise BaselineError(f"observation {field_name} must be non-empty")
        _require_aware(self.timestamp, "observation timestamp")


@dataclass(frozen=True, slots=True)
class BaselineComparisonPolicy:
    """Explicit deterministic thresholds for baseline drift classification."""

    sigma_threshold: float = 3.0
    minimum_absolute_drift: float = 0.0
    comparable_qualities: frozenset[str] = frozenset({"good"})

    def __post_init__(self) -> None:
        if not math.isfinite(self.sigma_threshold) or self.sigma_threshold <= 0.0:
            raise BaselineError("sigma_threshold must be finite and greater than 0")
        if (
            not math.isfinite(self.minimum_absolute_drift)
            or self.minimum_absolute_drift < 0.0
        ):
            raise BaselineError(
                "minimum_absolute_drift must be finite and non-negative"
            )
        normalized = frozenset(value.strip() for value in self.comparable_qualities)
        if not normalized or any(not value for value in normalized):
            raise BaselineError("comparable_qualities must contain non-empty values")
        object.__setattr__(self, "comparable_qualities", normalized)


@dataclass(frozen=True, slots=True)
class DriftAssessment:
    """Bounded baseline and envelope comparison for one observation."""

    baseline_id: str
    baseline_version: str
    baseline_source_id: str
    baseline_source_reference: str
    baseline_approval_reference: str
    applicability: BaselineApplicability
    observation_source_id: str
    observation_timestamp: datetime
    observation_quality: str
    engineering_unit: str
    observed_value: float
    baseline_mean: float
    residual: float
    absolute_drift: float
    normalized_sigma: float | None
    drift_threshold: float
    envelope_status: EnvelopeStatus
    drift_status: DriftStatus
    retained_uncertainty: str


@dataclass(frozen=True, slots=True)
class BaselineEvaluation:
    """Resolution plus an optional drift assessment when exactly one baseline applies."""

    resolution: BaselineResolution
    assessment: DriftAssessment | None


class BaselineRegistry:
    """Resolve effective immutable baselines and compare current observations."""

    def __init__(
        self,
        records: tuple[BaselineRecord, ...],
        invalidations: tuple[BaselineInvalidation, ...] = (),
    ) -> None:
        if not records:
            raise BaselineError("baseline registry requires at least one record")
        self.records = records
        self.invalidations = invalidations
        self._records_by_id = self._validate_and_index()
        self._replacement_by_id = {
            record.replaces_baseline_id: record.baseline_id
            for record in self.records
            if record.replaces_baseline_id is not None
        }
        self._invalidation_by_id = {
            invalidation.baseline_id: invalidation
            for invalidation in self.invalidations
        }
        self._effective_records = self._resolve_effective_records()

    @property
    def effective_records(self) -> tuple[BaselineRecord, ...]:
        """Return selectable records after append-only replacement and invalidation."""

        return self._effective_records

    def resolve(self, applicability: BaselineApplicability) -> BaselineResolution:
        """Require exact applicability and never silently choose among matches."""

        relevant = tuple(
            record
            for record in self.records
            if record.applicability.asset_id == applicability.asset_id
            and record.applicability.observation_key == applicability.observation_key
        )
        matches: list[BaselineRecord] = []
        rejections: list[BaselineRejection] = []
        for record in relevant:
            reasons = list(
                _applicability_mismatches(record.applicability, applicability)
            )
            replacement = self._replacement_by_id.get(record.baseline_id)
            if replacement is not None:
                reasons.append(f"replaced by baseline {replacement!r}")
            invalidation = self._invalidation_by_id.get(record.baseline_id)
            if invalidation is not None:
                reasons.append(
                    f"invalidated: {invalidation.reason} "
                    f"(evidence {invalidation.evidence_reference!r})"
                )
            if reasons:
                rejections.append(
                    BaselineRejection(
                        baseline_id=record.baseline_id,
                        reasons=tuple(reasons),
                    )
                )
            else:
                matches.append(record)

        ordered_matches = tuple(sorted(matches, key=lambda item: item.baseline_id))
        ordered_rejections = tuple(
            sorted(rejections, key=lambda item: item.baseline_id)
        )
        if len(ordered_matches) == 1:
            return BaselineResolution(
                status=BaselineResolutionStatus.RESOLVED,
                baseline=ordered_matches[0],
                candidate_ids=(ordered_matches[0].baseline_id,),
                rejections=ordered_rejections,
            )
        if not ordered_matches:
            return BaselineResolution(
                status=BaselineResolutionStatus.NOT_FOUND,
                baseline=None,
                candidate_ids=(),
                rejections=ordered_rejections,
            )
        return BaselineResolution(
            status=BaselineResolutionStatus.AMBIGUOUS,
            baseline=None,
            candidate_ids=tuple(record.baseline_id for record in ordered_matches),
            rejections=ordered_rejections,
        )

    def evaluate(
        self,
        observation: BaselineObservation,
        policy: BaselineComparisonPolicy | None = None,
    ) -> BaselineEvaluation:
        """Resolve the baseline first, then calculate drift only when comparable."""

        resolution = self.resolve(observation.applicability)
        if resolution.status is not BaselineResolutionStatus.RESOLVED:
            return BaselineEvaluation(resolution=resolution, assessment=None)
        assert resolution.baseline is not None
        assessment = compare_to_baseline(
            resolution.baseline,
            observation,
            policy or BaselineComparisonPolicy(),
        )
        return BaselineEvaluation(resolution=resolution, assessment=assessment)

    def _validate_and_index(self) -> dict[str, BaselineRecord]:
        ids = [record.baseline_id for record in self.records]
        duplicates = sorted(
            baseline_id
            for baseline_id, count in Counter(ids).items()
            if count > 1
        )
        if duplicates:
            raise BaselineError(
                "duplicate baseline IDs: " + ", ".join(duplicates)
            )
        records_by_id = {record.baseline_id: record for record in self.records}

        replaced_counts = Counter(
            record.replaces_baseline_id
            for record in self.records
            if record.replaces_baseline_id is not None
        )
        branching = sorted(
            baseline_id
            for baseline_id, count in replaced_counts.items()
            if count > 1
        )
        if branching:
            raise BaselineError(
                "a baseline cannot have multiple replacements: " + ", ".join(branching)
            )

        for record in self.records:
            replaced_id = record.replaces_baseline_id
            if replaced_id is None:
                continue
            replaced = records_by_id.get(replaced_id)
            if replaced is None:
                raise BaselineError(
                    f"baseline {record.baseline_id!r} replaces unknown baseline "
                    f"{replaced_id!r}"
                )
            if record.applicability != replaced.applicability:
                raise BaselineError(
                    "replacement baselines must preserve exact applicability scope"
                )
            if record.evidence.engineering_unit != replaced.evidence.engineering_unit:
                raise BaselineError(
                    "replacement baselines must preserve the engineering unit"
                )

        invalidation_ids = [item.baseline_id for item in self.invalidations]
        duplicate_invalidations = sorted(
            baseline_id
            for baseline_id, count in Counter(invalidation_ids).items()
            if count > 1
        )
        if duplicate_invalidations:
            raise BaselineError(
                "duplicate baseline invalidations: "
                + ", ".join(duplicate_invalidations)
            )
        for invalidation in self.invalidations:
            if invalidation.baseline_id not in records_by_id:
                raise BaselineError(
                    f"invalidation references unknown baseline "
                    f"{invalidation.baseline_id!r}"
                )
        _validate_no_replacement_cycles(self.records)
        return records_by_id

    def _resolve_effective_records(self) -> tuple[BaselineRecord, ...]:
        replaced = set(self._replacement_by_id)
        invalidated = set(self._invalidation_by_id)
        return tuple(
            sorted(
                (
                    record
                    for record in self.records
                    if record.baseline_id not in replaced
                    and record.baseline_id not in invalidated
                ),
                key=lambda item: item.baseline_id,
            )
        )


def compare_to_baseline(
    baseline: BaselineRecord,
    observation: BaselineObservation,
    policy: BaselineComparisonPolicy,
) -> DriftAssessment:
    """Compare one observation without converting drift into diagnosis."""

    if observation.applicability != baseline.applicability:
        raise BaselineError("observation applicability does not match the baseline")
    if observation.unit != baseline.evidence.engineering_unit:
        raise BaselineError(
            f"observation unit {observation.unit!r} does not match baseline unit "
            f"{baseline.evidence.engineering_unit!r}"
        )
    if observation.quality not in policy.comparable_qualities:
        allowed = ", ".join(sorted(policy.comparable_qualities))
        raise BaselineError(
            f"observation quality {observation.quality!r} is not comparable; "
            f"expected one of: {allowed}"
        )

    model = baseline.model
    residual = observation.value - model.mean
    absolute_drift = abs(residual)
    sigma_drift = policy.sigma_threshold * model.stddev
    drift_threshold = max(policy.minimum_absolute_drift, sigma_drift)
    normalized_sigma = residual / model.stddev if model.stddev > 0.0 else None

    if observation.value < model.approved_min:
        envelope_status = EnvelopeStatus.BELOW
    elif observation.value > model.approved_max:
        envelope_status = EnvelopeStatus.ABOVE
    else:
        envelope_status = EnvelopeStatus.WITHIN

    if envelope_status is not EnvelopeStatus.WITHIN:
        drift_status = DriftStatus.OUTSIDE_APPROVED_ENVELOPE
    elif absolute_drift >= drift_threshold and absolute_drift > 0.0:
        drift_status = DriftStatus.DRIFTED_WITHIN_ENVELOPE
    else:
        drift_status = DriftStatus.WITHIN_EXPECTED_BASELINE

    return DriftAssessment(
        baseline_id=baseline.baseline_id,
        baseline_version=baseline.version,
        baseline_source_id=baseline.evidence.source_id,
        baseline_source_reference=baseline.evidence.source_reference,
        baseline_approval_reference=baseline.evidence.approval_reference,
        applicability=baseline.applicability,
        observation_source_id=observation.source_id,
        observation_timestamp=observation.timestamp,
        observation_quality=observation.quality,
        engineering_unit=observation.unit,
        observed_value=observation.value,
        baseline_mean=model.mean,
        residual=residual,
        absolute_drift=absolute_drift,
        normalized_sigma=normalized_sigma,
        drift_threshold=drift_threshold,
        envelope_status=envelope_status,
        drift_status=drift_status,
        retained_uncertainty=(
            "This assessment reports deterministic difference from an applicable "
            "commissioned baseline and approved envelope. It does not establish a "
            "fault, physical root cause, safe production change, or authorization."
        ),
    )


def _applicability_mismatches(
    expected: BaselineApplicability,
    observed: BaselineApplicability,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "component_id",
        "operating_mode",
        "configuration_version",
        "firmware_version",
        "calibration_id",
        "sampling_profile_id",
    ):
        expected_value = getattr(expected, field_name)
        observed_value = getattr(observed, field_name)
        if expected_value != observed_value:
            reasons.append(
                f"{field_name} mismatch: baseline={expected_value!r}, "
                f"observed={observed_value!r}"
            )
    if dict(expected.context_tags) != dict(observed.context_tags):
        reasons.append(
            "context_tags mismatch: "
            f"baseline={dict(expected.context_tags)!r}, "
            f"observed={dict(observed.context_tags)!r}"
        )
    return tuple(reasons)


def _validate_no_replacement_cycles(records: tuple[BaselineRecord, ...]) -> None:
    predecessor = {
        record.baseline_id: record.replaces_baseline_id for record in records
    }
    for baseline_id in predecessor:
        seen: set[str] = set()
        current: str | None = baseline_id
        while current is not None:
            if current in seen:
                raise BaselineError("baseline replacement lineage must be acyclic")
            seen.add(current)
            current = predecessor.get(current)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BaselineError(f"{field_name} must be timezone-aware")
