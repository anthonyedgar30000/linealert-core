"""Connect replayed timing findings to governed baseline assessment."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .baseline import (
    BaselineApplicability,
    BaselineComparisonPolicy,
    BaselineError,
    BaselineEvaluation,
    BaselineObservation,
    BaselineRegistry,
    BaselineResolutionStatus,
    DriftStatus,
)
from .baseline_io import baseline_evaluation_to_dict
from .replay import ReplaySummary
from .timing import TimingFinding, TimingStatus


class TimingBaselineDisposition(StrEnum):
    """Outcome of attempting a baseline assessment for one timing finding."""

    EVALUATED = "evaluated"
    CONTEXT_NOT_CONFIGURED = "context_not_configured"
    COMPARISON_REJECTED = "comparison_rejected"


@dataclass(frozen=True, slots=True)
class TimingBaselineContext:
    """Explicit operating context used to make one timing rule comparable."""

    rule_id: str
    component_id: str
    operating_mode: str
    configuration_version: str
    firmware_version: str
    calibration_id: str
    sampling_profile_id: str
    observation_source_id: str
    observation_quality: str = "good"
    context_tags: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "rule_id",
            "component_id",
            "operating_mode",
            "configuration_version",
            "firmware_version",
            "calibration_id",
            "sampling_profile_id",
            "observation_source_id",
            "observation_quality",
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
class TimingBaselineResult:
    """One timing finding plus its bounded baseline-resolution outcome."""

    rule_id: str
    asset_id: str
    correlation_id: str
    observation_key: str
    start_timestamp: datetime
    end_timestamp: datetime
    delay_seconds: float
    temporal_rule_status: TimingStatus
    disposition: TimingBaselineDisposition
    evaluation: BaselineEvaluation | None
    rejection_reason: str | None
    retained_uncertainty: str


@dataclass(frozen=True, slots=True)
class ReplayBaselineAssessment:
    """All deterministic baseline outcomes for timing findings in one replay."""

    results: tuple[TimingBaselineResult, ...]

    @property
    def total_findings(self) -> int:
        return len(self.results)

    @property
    def evaluated_count(self) -> int:
        return sum(
            result.disposition is TimingBaselineDisposition.EVALUATED
            for result in self.results
        )

    @property
    def missing_context_count(self) -> int:
        return sum(
            result.disposition is TimingBaselineDisposition.CONTEXT_NOT_CONFIGURED
            for result in self.results
        )

    @property
    def rejected_count(self) -> int:
        return sum(
            result.disposition is TimingBaselineDisposition.COMPARISON_REJECTED
            for result in self.results
        )

    @property
    def resolved_count(self) -> int:
        return sum(
            result.evaluation is not None
            and result.evaluation.resolution.status is BaselineResolutionStatus.RESOLVED
            for result in self.results
        )

    @property
    def not_found_count(self) -> int:
        return sum(
            result.evaluation is not None
            and result.evaluation.resolution.status is BaselineResolutionStatus.NOT_FOUND
            for result in self.results
        )

    @property
    def ambiguous_count(self) -> int:
        return sum(
            result.evaluation is not None
            and result.evaluation.resolution.status is BaselineResolutionStatus.AMBIGUOUS
            for result in self.results
        )

    @property
    def drifted_count(self) -> int:
        return sum(
            result.evaluation is not None
            and result.evaluation.assessment is not None
            and result.evaluation.assessment.drift_status
            is DriftStatus.DRIFTED_WITHIN_ENVELOPE
            for result in self.results
        )

    @property
    def envelope_excursion_count(self) -> int:
        return sum(
            result.evaluation is not None
            and result.evaluation.assessment is not None
            and result.evaluation.assessment.drift_status
            is DriftStatus.OUTSIDE_APPROVED_ENVELOPE
            for result in self.results
        )


def assess_replay_timing_baselines(
    summary: ReplaySummary,
    registry: BaselineRegistry,
    contexts: tuple[TimingBaselineContext, ...],
    policy: BaselineComparisonPolicy | None = None,
) -> ReplayBaselineAssessment:
    """Resolve and compare each timing finding without turning drift into diagnosis."""

    context_by_rule = _index_contexts(contexts)
    selected_policy = policy or BaselineComparisonPolicy()
    results: list[TimingBaselineResult] = []

    for pipeline_result in summary.results:
        for finding in pipeline_result.timing_findings:
            context = context_by_rule.get(finding.rule_id)
            if context is None:
                results.append(
                    _result(
                        finding=finding,
                        disposition=TimingBaselineDisposition.CONTEXT_NOT_CONFIGURED,
                        evaluation=None,
                        rejection_reason=(
                            f"no timing baseline context is configured for rule "
                            f"{finding.rule_id!r}"
                        ),
                    )
                )
                continue

            applicability = BaselineApplicability(
                asset_id=finding.asset_id,
                component_id=context.component_id,
                observation_key=finding.observation_key,
                operating_mode=context.operating_mode,
                configuration_version=context.configuration_version,
                firmware_version=context.firmware_version,
                calibration_id=context.calibration_id,
                sampling_profile_id=context.sampling_profile_id,
                context_tags=context.context_tags,
            )
            observation = BaselineObservation(
                applicability=applicability,
                value=finding.delay_seconds,
                unit="s",
                timestamp=finding.end_timestamp,
                source_id=context.observation_source_id,
                quality=context.observation_quality,
            )
            try:
                evaluation = registry.evaluate(observation, selected_policy)
            except BaselineError as exc:
                results.append(
                    _result(
                        finding=finding,
                        disposition=TimingBaselineDisposition.COMPARISON_REJECTED,
                        evaluation=None,
                        rejection_reason=str(exc),
                    )
                )
                continue

            results.append(
                _result(
                    finding=finding,
                    disposition=TimingBaselineDisposition.EVALUATED,
                    evaluation=evaluation,
                    rejection_reason=None,
                )
            )

    return ReplayBaselineAssessment(results=tuple(results))


def load_timing_baseline_contexts(
    path: str | Path,
) -> tuple[TimingBaselineContext, ...]:
    """Load explicit timing-to-baseline applicability context from JSON."""

    source_path = Path(path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BaselineError(
            f"{source_path}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise BaselineError(f"{source_path}: context configuration must be an object")

    contexts_raw = raw.get("contexts")
    if not isinstance(contexts_raw, list) or not contexts_raw:
        raise BaselineError(f"{source_path}: contexts must be a non-empty list")

    contexts = tuple(
        _parse_context(item, source_path, index)
        for index, item in enumerate(contexts_raw, start=1)
    )
    _index_contexts(contexts)
    return contexts


def timing_baseline_assessment_to_dict(
    assessment: ReplayBaselineAssessment,
) -> dict[str, Any]:
    """Return a JSON-compatible replay baseline evidence section."""

    return {
        "summary": {
            "total_findings": assessment.total_findings,
            "evaluated": assessment.evaluated_count,
            "context_not_configured": assessment.missing_context_count,
            "comparison_rejected": assessment.rejected_count,
            "baseline_resolved": assessment.resolved_count,
            "baseline_not_found": assessment.not_found_count,
            "baseline_ambiguous": assessment.ambiguous_count,
            "drifted_within_envelope": assessment.drifted_count,
            "outside_approved_envelope": assessment.envelope_excursion_count,
        },
        "results": [
            {
                "rule_id": result.rule_id,
                "asset_id": result.asset_id,
                "correlation_id": result.correlation_id,
                "observation_key": result.observation_key,
                "start_timestamp": result.start_timestamp.isoformat(),
                "end_timestamp": result.end_timestamp.isoformat(),
                "delay_seconds": result.delay_seconds,
                "temporal_rule_status": result.temporal_rule_status.value,
                "disposition": result.disposition.value,
                "rejection_reason": result.rejection_reason,
                "baseline_evaluation": (
                    baseline_evaluation_to_dict(result.evaluation)
                    if result.evaluation is not None
                    else None
                ),
                "retained_uncertainty": result.retained_uncertainty,
            }
            for result in assessment.results
        ],
    }


def _result(
    *,
    finding: TimingFinding,
    disposition: TimingBaselineDisposition,
    evaluation: BaselineEvaluation | None,
    rejection_reason: str | None,
) -> TimingBaselineResult:
    return TimingBaselineResult(
        rule_id=finding.rule_id,
        asset_id=finding.asset_id,
        correlation_id=finding.correlation_id,
        observation_key=finding.observation_key,
        start_timestamp=finding.start_timestamp,
        end_timestamp=finding.end_timestamp,
        delay_seconds=finding.delay_seconds,
        temporal_rule_status=finding.status,
        disposition=disposition,
        evaluation=evaluation,
        rejection_reason=rejection_reason,
        retained_uncertainty=(
            "The temporal-rule status and commissioned-baseline assessment are "
            "separate bounded comparisons. Neither establishes a fault, physical "
            "root cause, safe production change, or authorization."
        ),
    )


def _index_contexts(
    contexts: tuple[TimingBaselineContext, ...],
) -> dict[str, TimingBaselineContext]:
    counts = Counter(context.rule_id for context in contexts)
    duplicates = sorted(rule_id for rule_id, count in counts.items() if count > 1)
    if duplicates:
        raise BaselineError(
            "timing baseline context rule IDs must be unique: "
            + ", ".join(duplicates)
        )
    return {context.rule_id: context for context in contexts}


def _parse_context(
    raw: object,
    path: Path,
    index: int,
) -> TimingBaselineContext:
    location = f"{path}: context {index}"
    if not isinstance(raw, Mapping):
        raise BaselineError(f"{location} must be an object")
    tags = raw.get("context_tags", {})
    if not isinstance(tags, Mapping) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in tags.items()
    ):
        raise BaselineError(f"{location}.context_tags must be an object")

    return TimingBaselineContext(
        rule_id=_required_text(raw, "rule_id", location),
        component_id=_required_text(raw, "component_id", location),
        operating_mode=_required_text(raw, "operating_mode", location),
        configuration_version=_required_text(
            raw,
            "configuration_version",
            location,
        ),
        firmware_version=_required_text(raw, "firmware_version", location),
        calibration_id=_required_text(raw, "calibration_id", location),
        sampling_profile_id=_required_text(
            raw,
            "sampling_profile_id",
            location,
        ),
        observation_source_id=_required_text(
            raw,
            "observation_source_id",
            location,
        ),
        observation_quality=_optional_text(raw, "observation_quality") or "good",
        context_tags=dict(tags),
    )


def _required_text(raw: Mapping[str, object], field_name: str, location: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise BaselineError(
            f"{location}: {field_name} must be a non-empty string"
        )
    return value.strip()


def _optional_text(raw: Mapping[str, object], field_name: str) -> str | None:
    value = raw.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise BaselineError(f"{field_name} must be a string when supplied")
    return value.strip() or None
