"""JSON policy loading and reporting for timing signal analysis."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .signal_processing import (
    SignalAnalysisError,
    SignalAnalysisPolicy,
    TimingSeriesAssessment,
)


def load_signal_policy(path: str | Path) -> SignalAnalysisPolicy:
    """Load one explicit timing signal-analysis policy from JSON."""

    policy_path = Path(path)
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SignalAnalysisError(
            f"{policy_path}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise SignalAnalysisError(f"{policy_path}: policy must be an object")

    return SignalAnalysisPolicy(
        policy_id=_required_text(raw, "policy_id", policy_path),
        version=_required_text(raw, "version", policy_path),
        minimum_points=_required_int(raw, "minimum_points", policy_path),
        baseline_points=_required_int(raw, "baseline_points", policy_path),
        recent_points=_required_int(raw, "recent_points", policy_path),
        sustained_outside_points=_required_int(
            raw,
            "sustained_outside_points",
            policy_path,
        ),
        recurring_excursion_count=_required_int(
            raw,
            "recurring_excursion_count",
            policy_path,
        ),
        variability_ratio=_required_float(raw, "variability_ratio", policy_path),
        variability_min_envelope_fraction=_required_float(
            raw,
            "variability_min_envelope_fraction",
            policy_path,
        ),
        drift_min_envelope_fraction=_required_float(
            raw,
            "drift_min_envelope_fraction",
            policy_path,
        ),
        drift_min_directional_fraction=_required_float(
            raw,
            "drift_min_directional_fraction",
            policy_path,
        ),
        change_point_min_segment_points=_required_int(
            raw,
            "change_point_min_segment_points",
            policy_path,
        ),
        change_point_min_mean_shift_fraction=_required_float(
            raw,
            "change_point_min_mean_shift_fraction",
            policy_path,
        ),
    )


def signal_assessments_to_dict(
    assessments: tuple[TimingSeriesAssessment, ...],
) -> list[dict[str, Any]]:
    """Return JSON-compatible timing-series assessments."""

    return [
        {
            "policy": {
                "policy_id": assessment.policy_id,
                "version": assessment.policy_version,
            },
            "relationship": {
                "rule_id": assessment.rule_id,
                "asset_id": assessment.asset_id,
                "observation_key": assessment.observation_key,
                "from": assessment.topology_from,
                "to": assessment.topology_to,
                "approved_min_seconds": assessment.approved_min_seconds,
                "approved_max_seconds": assessment.approved_max_seconds,
            },
            "window": {
                "sample_count": assessment.sample_count,
                "first_timestamp": assessment.first_timestamp.isoformat(),
                "last_timestamp": assessment.last_timestamp.isoformat(),
            },
            "baseline": {
                "source": assessment.baseline_source,
                "count": assessment.baseline_count,
                "start": assessment.baseline_start.isoformat(),
                "end": assessment.baseline_end.isoformat(),
                "mean_seconds": assessment.baseline_mean_seconds,
                "stddev_seconds": assessment.baseline_stddev_seconds,
            },
            "recent": {
                "count": assessment.recent_count,
                "start": assessment.recent_start.isoformat(),
                "end": assessment.recent_end.isoformat(),
                "mean_seconds": assessment.recent_mean_seconds,
                "stddev_seconds": assessment.recent_stddev_seconds,
            },
            "excursions": {
                "total": assessment.outside_count,
                "recent": assessment.recent_outside_count,
            },
            "trend": {
                "slope_seconds_per_sample": assessment.slope_seconds_per_sample,
                "directional_fraction": assessment.directional_fraction,
            },
            "patterns": [pattern.value for pattern in assessment.patterns],
            "candidate_change": {
                "timestamp": (
                    assessment.candidate_change_timestamp.isoformat()
                    if assessment.candidate_change_timestamp is not None
                    else None
                ),
                "mean_shift_seconds": assessment.candidate_mean_shift_seconds,
                "operator_reported_start": (
                    assessment.operator_reported_start.isoformat()
                    if assessment.operator_reported_start is not None
                    else None
                ),
                "offset_from_report_seconds": (
                    assessment.candidate_offset_from_report_seconds
                ),
                "timeline_relation": assessment.timeline_relation,
            },
            "observations": list(assessment.observations),
            "retained_uncertainty": assessment.retained_uncertainty,
        }
        for assessment in assessments
    ]


def _required_text(
    raw: Mapping[str, object],
    field: str,
    path: Path,
) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SignalAnalysisError(
            f"{path}: {field} must be a non-empty string"
        )
    return value.strip()


def _required_int(
    raw: Mapping[str, object],
    field: str,
    path: Path,
) -> int:
    value = raw.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SignalAnalysisError(f"{path}: {field} must be an integer")
    return value


def _required_float(
    raw: Mapping[str, object],
    field: str,
    path: Path,
) -> float:
    value = raw.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SignalAnalysisError(f"{path}: {field} must be numeric")
    return float(value)
