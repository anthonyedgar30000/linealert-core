"""Deterministic time-series analysis for repeated timing relationships."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from statistics import fmean, pstdev

from .timing import TimingFinding, TimingStatus


class SignalAnalysisError(ValueError):
    """Raised when signal-analysis inputs or policies are invalid."""


class SignalPattern(StrEnum):
    """Bounded patterns observable in one timing relationship history."""

    INSUFFICIENT_DATA = "insufficient_data"
    STABLE = "stable"
    ISOLATED_EXCURSION = "isolated_excursion"
    RECURRING_EXCURSIONS = "recurring_excursions"
    RISING_VARIABILITY = "rising_variability"
    GRADUAL_DRIFT = "gradual_drift"
    SUSTAINED_SHIFT = "sustained_shift"


@dataclass(frozen=True, slots=True)
class SignalAnalysisPolicy:
    """Explicit thresholds controlling deterministic timing-series analysis."""

    policy_id: str
    version: str
    minimum_points: int
    baseline_points: int
    recent_points: int
    sustained_outside_points: int
    recurring_excursion_count: int
    variability_ratio: float
    variability_min_envelope_fraction: float
    drift_min_envelope_fraction: float
    drift_min_directional_fraction: float
    change_point_min_segment_points: int
    change_point_min_mean_shift_fraction: float

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or not self.version.strip():
            raise SignalAnalysisError("policy_id and version must not be empty")
        integer_fields = (
            "minimum_points",
            "baseline_points",
            "recent_points",
            "sustained_outside_points",
            "recurring_excursion_count",
            "change_point_min_segment_points",
        )
        for field_name in integer_fields:
            if getattr(self, field_name) < 1:
                raise SignalAnalysisError(f"{field_name} must be at least 1")
        if self.minimum_points < max(self.baseline_points, self.recent_points):
            raise SignalAnalysisError(
                "minimum_points must cover baseline_points and recent_points"
            )
        if self.variability_ratio <= 1.0:
            raise SignalAnalysisError("variability_ratio must be greater than 1")
        fraction_fields = (
            "variability_min_envelope_fraction",
            "drift_min_envelope_fraction",
            "drift_min_directional_fraction",
            "change_point_min_mean_shift_fraction",
        )
        for field_name in fraction_fields:
            value = getattr(self, field_name)
            if value <= 0.0 or value > 1.0:
                raise SignalAnalysisError(
                    f"{field_name} must be greater than 0 and at most 1"
                )


@dataclass(frozen=True, slots=True)
class TimingSeriesAssessment:
    """Deterministic characterization of one repeated timing relationship."""

    policy_id: str
    policy_version: str
    rule_id: str
    asset_id: str
    observation_key: str
    topology_from: str
    topology_to: str
    sample_count: int
    first_timestamp: datetime
    last_timestamp: datetime
    approved_min_seconds: float
    approved_max_seconds: float
    baseline_source: str
    baseline_count: int
    baseline_start: datetime
    baseline_end: datetime
    baseline_mean_seconds: float
    baseline_stddev_seconds: float
    recent_count: int
    recent_start: datetime
    recent_end: datetime
    recent_mean_seconds: float
    recent_stddev_seconds: float
    outside_count: int
    recent_outside_count: int
    slope_seconds_per_sample: float
    directional_fraction: float
    patterns: tuple[SignalPattern, ...]
    candidate_change_timestamp: datetime | None
    candidate_mean_shift_seconds: float | None
    operator_reported_start: datetime | None
    candidate_offset_from_report_seconds: float | None
    timeline_relation: str | None
    observations: tuple[str, ...]
    retained_uncertainty: str

    @property
    def has_actionable_pattern(self) -> bool:
        """Whether this history contains more than stable or insufficient data."""

        return any(
            pattern not in {SignalPattern.STABLE, SignalPattern.INSUFFICIENT_DATA}
            for pattern in self.patterns
        )


class TimingSignalAnalyzer:
    """Analyze repeated timing findings using explicit, reviewable thresholds."""

    def __init__(self, policy: SignalAnalysisPolicy) -> None:
        self.policy = policy

    def analyze(
        self,
        findings: tuple[TimingFinding, ...],
        *,
        operator_reported_start: datetime | None = None,
    ) -> tuple[TimingSeriesAssessment, ...]:
        """Group compatible findings and assess each ordered time series."""

        if operator_reported_start is not None and (
            operator_reported_start.tzinfo is None
            or operator_reported_start.utcoffset() is None
        ):
            raise SignalAnalysisError(
                "operator_reported_start must be timezone-aware"
            )

        grouped: dict[
            tuple[str, str, str, str, float, float],
            list[TimingFinding],
        ] = defaultdict(list)
        for finding in findings:
            key = (
                finding.asset_id,
                finding.rule_id,
                finding.topology_from,
                finding.topology_to,
                finding.min_delay_seconds,
                finding.max_delay_seconds,
            )
            grouped[key].append(finding)

        assessments = [
            self._assess_series(
                tuple(
                    sorted(
                        series,
                        key=lambda item: (
                            item.end_timestamp,
                            item.correlation_id,
                        ),
                    )
                ),
                operator_reported_start=operator_reported_start,
            )
            for series in grouped.values()
        ]
        return tuple(
            sorted(
                assessments,
                key=lambda item: (
                    item.asset_id,
                    item.topology_from,
                    item.topology_to,
                    item.rule_id,
                ),
            )
        )

    def _assess_series(
        self,
        series: tuple[TimingFinding, ...],
        *,
        operator_reported_start: datetime | None,
    ) -> TimingSeriesAssessment:
        first = series[0]
        baseline, baseline_source = self._select_baseline(
            series,
            operator_reported_start=operator_reported_start,
        )
        recent = series[-min(len(series), self.policy.recent_points) :]
        values = tuple(finding.delay_seconds for finding in series)
        baseline_values = tuple(finding.delay_seconds for finding in baseline)
        recent_values = tuple(finding.delay_seconds for finding in recent)

        baseline_mean = fmean(baseline_values)
        baseline_stddev = _stddev(baseline_values)
        recent_mean = fmean(recent_values)
        recent_stddev = _stddev(recent_values)
        outside_count = sum(
            finding.status is not TimingStatus.WITHIN for finding in series
        )
        recent_outside_count = sum(
            finding.status is not TimingStatus.WITHIN for finding in recent
        )
        slope = _linear_slope(values)
        directional_fraction = _directional_fraction(values, slope)
        scale = _analysis_scale(
            first.min_delay_seconds,
            first.max_delay_seconds,
            baseline_mean,
        )

        patterns = self._detect_patterns(
            series=series,
            baseline_stddev=baseline_stddev,
            recent_stddev=recent_stddev,
            outside_count=outside_count,
            recent=recent,
            slope=slope,
            directional_fraction=directional_fraction,
            scale=scale,
        )
        change_timestamp, mean_shift = self._candidate_change_point(
            series,
            scale=scale,
            patterns=patterns,
        )
        offset, relation = _timeline_alignment(
            change_timestamp,
            operator_reported_start,
        )
        observations = _build_observations(
            series=series,
            baseline_mean=baseline_mean,
            baseline_stddev=baseline_stddev,
            recent_mean=recent_mean,
            recent_stddev=recent_stddev,
            outside_count=outside_count,
            patterns=patterns,
            change_timestamp=change_timestamp,
            operator_reported_start=operator_reported_start,
            timeline_relation=relation,
        )

        return TimingSeriesAssessment(
            policy_id=self.policy.policy_id,
            policy_version=self.policy.version,
            rule_id=first.rule_id,
            asset_id=first.asset_id,
            observation_key=first.observation_key,
            topology_from=first.topology_from,
            topology_to=first.topology_to,
            sample_count=len(series),
            first_timestamp=series[0].start_timestamp,
            last_timestamp=series[-1].end_timestamp,
            approved_min_seconds=first.min_delay_seconds,
            approved_max_seconds=first.max_delay_seconds,
            baseline_source=baseline_source,
            baseline_count=len(baseline),
            baseline_start=baseline[0].start_timestamp,
            baseline_end=baseline[-1].end_timestamp,
            baseline_mean_seconds=baseline_mean,
            baseline_stddev_seconds=baseline_stddev,
            recent_count=len(recent),
            recent_start=recent[0].start_timestamp,
            recent_end=recent[-1].end_timestamp,
            recent_mean_seconds=recent_mean,
            recent_stddev_seconds=recent_stddev,
            outside_count=outside_count,
            recent_outside_count=recent_outside_count,
            slope_seconds_per_sample=slope,
            directional_fraction=directional_fraction,
            patterns=patterns,
            candidate_change_timestamp=change_timestamp,
            candidate_mean_shift_seconds=mean_shift,
            operator_reported_start=operator_reported_start,
            candidate_offset_from_report_seconds=offset,
            timeline_relation=relation,
            observations=observations,
            retained_uncertainty=(
                "Patterns describe the supplied timing history under this explicit "
                "policy. A candidate change point is a statistical boundary, not "
                "the proven start of degradation or a physical root cause."
            ),
        )

    def _select_baseline(
        self,
        series: tuple[TimingFinding, ...],
        *,
        operator_reported_start: datetime | None,
    ) -> tuple[tuple[TimingFinding, ...], str]:
        healthy = tuple(
            finding for finding in series if finding.status is TimingStatus.WITHIN
        )
        if operator_reported_start is not None:
            healthy_before_report = tuple(
                finding
                for finding in healthy
                if finding.end_timestamp < operator_reported_start
            )
            if len(healthy_before_report) >= self.policy.baseline_points:
                return (
                    healthy_before_report[-self.policy.baseline_points :],
                    "healthy_before_operator_report",
                )
        if len(healthy) >= self.policy.baseline_points:
            return (
                healthy[: self.policy.baseline_points],
                "earliest_healthy_observations",
            )
        count = min(len(series), self.policy.baseline_points)
        return (
            series[:count],
            "earliest_available_not_confirmed_healthy",
        )

    def _detect_patterns(
        self,
        *,
        series: tuple[TimingFinding, ...],
        baseline_stddev: float,
        recent_stddev: float,
        outside_count: int,
        recent: tuple[TimingFinding, ...],
        slope: float,
        directional_fraction: float,
        scale: float,
    ) -> tuple[SignalPattern, ...]:
        if len(series) < self.policy.minimum_points:
            return (SignalPattern.INSUFFICIENT_DATA,)

        detected: list[SignalPattern] = []
        if outside_count == 1:
            detected.append(SignalPattern.ISOLATED_EXCURSION)
        elif outside_count >= self.policy.recurring_excursion_count:
            detected.append(SignalPattern.RECURRING_EXCURSIONS)

        variability_increase = recent_stddev - baseline_stddev
        if (
            recent_stddev >= baseline_stddev * self.policy.variability_ratio
            and variability_increase
            >= scale * self.policy.variability_min_envelope_fraction
        ):
            detected.append(SignalPattern.RISING_VARIABILITY)

        modeled_change = abs(slope) * (len(series) - 1)
        if (
            modeled_change >= scale * self.policy.drift_min_envelope_fraction
            and directional_fraction >= self.policy.drift_min_directional_fraction
        ):
            detected.append(SignalPattern.GRADUAL_DRIFT)

        sustained_count = self.policy.sustained_outside_points
        if len(recent) >= sustained_count:
            tail = recent[-sustained_count:]
            tail_statuses = {finding.status for finding in tail}
            if len(tail_statuses) == 1 and TimingStatus.WITHIN not in tail_statuses:
                detected.append(SignalPattern.SUSTAINED_SHIFT)

        if not detected:
            detected.append(SignalPattern.STABLE)
        return tuple(detected)

    def _candidate_change_point(
        self,
        series: tuple[TimingFinding, ...],
        *,
        scale: float,
        patterns: tuple[SignalPattern, ...],
    ) -> tuple[datetime | None, float | None]:
        if not any(
            pattern
            in {
                SignalPattern.RISING_VARIABILITY,
                SignalPattern.GRADUAL_DRIFT,
                SignalPattern.SUSTAINED_SHIFT,
            }
            for pattern in patterns
        ):
            return None, None

        minimum = self.policy.change_point_min_segment_points
        if len(series) < minimum * 2:
            return None, None

        values = tuple(finding.delay_seconds for finding in series)
        required_shift = scale * self.policy.change_point_min_mean_shift_fraction
        candidates: list[tuple[float, int]] = []
        for split in range(minimum, len(series) - minimum + 1):
            before_mean = fmean(values[:split])
            after_mean = fmean(values[split:])
            shift = abs(after_mean - before_mean)
            if shift >= required_shift:
                candidates.append((shift, split))
        if not candidates:
            return None, None

        shift, split = max(candidates, key=lambda item: (item[0], -item[1]))
        return series[split].start_timestamp, shift


def _stddev(values: tuple[float, ...]) -> float:
    return pstdev(values) if len(values) > 1 else 0.0


def _analysis_scale(
    approved_min: float,
    approved_max: float,
    baseline_mean: float,
) -> float:
    envelope_span = approved_max - approved_min
    return max(envelope_span, abs(baseline_mean) * 0.1, 1e-9)


def _linear_slope(values: tuple[float, ...]) -> float:
    if len(values) < 2:
        return 0.0
    mean_x = (len(values) - 1) / 2.0
    mean_y = fmean(values)
    numerator = sum(
        (index - mean_x) * (value - mean_y)
        for index, value in enumerate(values)
    )
    denominator = sum((index - mean_x) ** 2 for index in range(len(values)))
    return numerator / denominator if denominator else 0.0


def _directional_fraction(values: tuple[float, ...], slope: float) -> float:
    if len(values) < 2 or slope == 0.0:
        return 0.0
    expected_positive = slope > 0.0
    deltas = tuple(
        values[index] - values[index - 1]
        for index in range(1, len(values))
    )
    directional = sum(
        (delta > 0.0) if expected_positive else (delta < 0.0)
        for delta in deltas
        if delta != 0.0
    )
    nonzero = sum(delta != 0.0 for delta in deltas)
    return directional / nonzero if nonzero else 0.0


def _timeline_alignment(
    candidate_change: datetime | None,
    operator_reported_start: datetime | None,
) -> tuple[float | None, str | None]:
    if candidate_change is None or operator_reported_start is None:
        return None, None
    offset = (candidate_change - operator_reported_start).total_seconds()
    if offset < 0:
        relation = "candidate_before_operator_report"
    elif offset > 0:
        relation = "candidate_after_operator_report"
    else:
        relation = "candidate_matches_operator_report"
    return offset, relation


def _build_observations(
    *,
    series: tuple[TimingFinding, ...],
    baseline_mean: float,
    baseline_stddev: float,
    recent_mean: float,
    recent_stddev: float,
    outside_count: int,
    patterns: tuple[SignalPattern, ...],
    change_timestamp: datetime | None,
    operator_reported_start: datetime | None,
    timeline_relation: str | None,
) -> tuple[str, ...]:
    messages = [
        (
            f"Analyzed {len(series)} observations from "
            f"{series[0].start_timestamp.isoformat()} through "
            f"{series[-1].end_timestamp.isoformat()}."
        ),
        (
            f"Baseline mean/stddev: {baseline_mean:.3f}s / "
            f"{baseline_stddev:.3f}s; recent mean/stddev: "
            f"{recent_mean:.3f}s / {recent_stddev:.3f}s."
        ),
        f"Observed {outside_count} timing-envelope excursions.",
        "Detected patterns: " + ", ".join(pattern.value for pattern in patterns) + ".",
    ]
    if change_timestamp is not None:
        messages.append(
            "Candidate statistical change boundary: "
            f"{change_timestamp.isoformat()}."
        )
    if operator_reported_start is not None and timeline_relation is not None:
        messages.append(
            "Operator-reported symptom start: "
            f"{operator_reported_start.isoformat()} ({timeline_relation})."
        )
    return tuple(messages)
