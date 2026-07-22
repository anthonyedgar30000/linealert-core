"""JSON loading and reporting for governed commissioned baselines."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .baseline import (
    BaselineApplicability,
    BaselineError,
    BaselineEvaluation,
    BaselineEvidence,
    BaselineInvalidation,
    BaselineModel,
    BaselineRecord,
    BaselineRegistry,
)


def load_baseline_registry(path: str | Path) -> BaselineRegistry:
    """Load immutable baseline records and append-only invalidations from JSON."""

    registry_path = Path(path)
    raw = _read_json_object(registry_path)
    records_raw = raw.get("records")
    if not isinstance(records_raw, list) or not records_raw:
        raise BaselineError(f"{registry_path}: records must be a non-empty list")
    invalidations_raw = raw.get("invalidations", [])
    if not isinstance(invalidations_raw, list):
        raise BaselineError(f"{registry_path}: invalidations must be a list")

    records = tuple(
        _parse_record(item, registry_path, index)
        for index, item in enumerate(records_raw, start=1)
    )
    invalidations = tuple(
        _parse_invalidation(item, registry_path, index)
        for index, item in enumerate(invalidations_raw, start=1)
    )
    return BaselineRegistry(records=records, invalidations=invalidations)


def baseline_evaluation_to_dict(evaluation: BaselineEvaluation) -> dict[str, Any]:
    """Return a JSON-compatible resolution and optional drift assessment."""

    resolution = evaluation.resolution
    assessment = evaluation.assessment
    return {
        "resolution": {
            "status": resolution.status.value,
            "baseline_id": (
                resolution.baseline.baseline_id
                if resolution.baseline is not None
                else None
            ),
            "candidate_ids": list(resolution.candidate_ids),
            "rejections": [
                {
                    "baseline_id": rejection.baseline_id,
                    "reasons": list(rejection.reasons),
                }
                for rejection in resolution.rejections
            ],
        },
        "assessment": (
            {
                "baseline_id": assessment.baseline_id,
                "baseline_version": assessment.baseline_version,
                "baseline_source": {
                    "source_id": assessment.baseline_source_id,
                    "source_reference": assessment.baseline_source_reference,
                    "approval_reference": assessment.baseline_approval_reference,
                },
                "applicability": {
                    "asset_id": assessment.applicability.asset_id,
                    "component_id": assessment.applicability.component_id,
                    "observation_key": assessment.applicability.observation_key,
                    "operating_mode": assessment.applicability.operating_mode,
                    "configuration_version": (
                        assessment.applicability.configuration_version
                    ),
                    "firmware_version": assessment.applicability.firmware_version,
                    "calibration_id": assessment.applicability.calibration_id,
                    "sampling_profile_id": (
                        assessment.applicability.sampling_profile_id
                    ),
                    "context_tags": dict(assessment.applicability.context_tags),
                },
                "observation": {
                    "source_id": assessment.observation_source_id,
                    "timestamp": assessment.observation_timestamp.isoformat(),
                    "quality": assessment.observation_quality,
                    "engineering_unit": assessment.engineering_unit,
                    "value": assessment.observed_value,
                },
                "observed_value": assessment.observed_value,
                "baseline_mean": assessment.baseline_mean,
                "residual": assessment.residual,
                "absolute_drift": assessment.absolute_drift,
                "normalized_sigma": assessment.normalized_sigma,
                "drift_threshold": assessment.drift_threshold,
                "envelope_status": assessment.envelope_status.value,
                "drift_status": assessment.drift_status.value,
                "retained_uncertainty": assessment.retained_uncertainty,
            }
            if assessment is not None
            else None
        ),
    }


def _parse_record(raw: object, path: Path, index: int) -> BaselineRecord:
    location = f"{path}: record {index}"
    item = _require_mapping(raw, location)
    applicability = _require_mapping(item.get("applicability"), f"{location}.applicability")
    model = _require_mapping(item.get("model"), f"{location}.model")
    evidence = _require_mapping(item.get("evidence"), f"{location}.evidence")
    tags = applicability.get("context_tags", {})
    if not isinstance(tags, Mapping) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in tags.items()
    ):
        raise BaselineError(f"{location}.applicability.context_tags must be an object")

    replaces = item.get("replaces_baseline_id")
    if replaces is not None and not isinstance(replaces, str):
        raise BaselineError(f"{location}.replaces_baseline_id must be a string or null")

    return BaselineRecord(
        baseline_id=_required_text(item, "baseline_id", location),
        version=_required_text(item, "version", location),
        replaces_baseline_id=replaces,
        applicability=BaselineApplicability(
            asset_id=_required_text(applicability, "asset_id", location),
            component_id=_required_text(applicability, "component_id", location),
            observation_key=_required_text(applicability, "observation_key", location),
            operating_mode=_required_text(applicability, "operating_mode", location),
            configuration_version=_required_text(
                applicability,
                "configuration_version",
                location,
            ),
            firmware_version=_required_text(applicability, "firmware_version", location),
            calibration_id=_required_text(applicability, "calibration_id", location),
            sampling_profile_id=_required_text(
                applicability,
                "sampling_profile_id",
                location,
            ),
            context_tags=dict(tags),
        ),
        model=BaselineModel(
            mean=_required_number(model, "mean", location),
            stddev=_required_number(model, "stddev", location),
            approved_min=_required_number(model, "approved_min", location),
            approved_max=_required_number(model, "approved_max", location),
        ),
        evidence=BaselineEvidence(
            source_id=_required_text(evidence, "source_id", location),
            source_reference=_required_text(evidence, "source_reference", location),
            captured_start=_required_datetime(evidence, "captured_start", location),
            captured_end=_required_datetime(evidence, "captured_end", location),
            clock_quality=_required_text(evidence, "clock_quality", location),
            engineering_unit=_required_text(evidence, "engineering_unit", location),
            sample_count=_required_int(evidence, "sample_count", location),
            test_conditions=_required_text(evidence, "test_conditions", location),
            approved_by=_required_text(evidence, "approved_by", location),
            approved_at=_required_datetime(evidence, "approved_at", location),
            approval_reference=_required_text(
                evidence,
                "approval_reference",
                location,
            ),
        ),
    )


def _parse_invalidation(raw: object, path: Path, index: int) -> BaselineInvalidation:
    location = f"{path}: invalidation {index}"
    item = _require_mapping(raw, location)
    return BaselineInvalidation(
        baseline_id=_required_text(item, "baseline_id", location),
        reason=_required_text(item, "reason", location),
        invalidated_at=_required_datetime(item, "invalidated_at", location),
        invalidated_by=_required_text(item, "invalidated_by", location),
        evidence_reference=_required_text(item, "evidence_reference", location),
    )


def _read_json_object(path: Path) -> Mapping[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BaselineError(
            f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise BaselineError(f"{path}: baseline registry must be an object")
    return raw


def _require_mapping(raw: object, location: str) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise BaselineError(f"{location} must be an object")
    return raw


def _required_text(raw: Mapping[str, object], field: str, location: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise BaselineError(f"{location}: {field} must be a non-empty string")
    return value.strip()


def _required_number(raw: Mapping[str, object], field: str, location: str) -> float:
    value = raw.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise BaselineError(f"{location}: {field} must be numeric")
    return float(value)


def _required_int(raw: Mapping[str, object], field: str, location: str) -> int:
    value = raw.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BaselineError(f"{location}: {field} must be an integer")
    return value


def _required_datetime(
    raw: Mapping[str, object],
    field: str,
    location: str,
) -> datetime:
    text = _required_text(raw, field, location)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BaselineError(f"{location}: {field} must be ISO 8601") from exc
