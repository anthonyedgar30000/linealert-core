from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from linealert_core.baseline import (
    BaselineApplicability,
    BaselineComparisonPolicy,
    BaselineError,
    BaselineEvidence,
    BaselineInvalidation,
    BaselineModel,
    BaselineObservation,
    BaselineRecord,
    BaselineRegistry,
    BaselineResolutionStatus,
    DriftStatus,
    EnvelopeStatus,
)


def applicability(**overrides: str) -> BaselineApplicability:
    values = {
        "asset_id": "LABELER-DEMO-01",
        "component_id": "label-feed-servo",
        "observation_key": "lag:LabelFeedCommand->LabelAtPeelPoint",
        "operating_mode": "500ml-round-bottle",
        "configuration_version": "plc-program-4.2.1",
        "firmware_version": "servo-fw-3.7",
        "calibration_id": "label-sensor-cal-2026-07-10",
        "sampling_profile_id": "event-timing-v1",
    }
    values.update(overrides)
    return BaselineApplicability(
        **values,
        context_tags={"label_stock": "supplier-a-roll-42"},
    )


def evidence() -> BaselineEvidence:
    return BaselineEvidence(
        source_id="commissioning-historian-export",
        source_reference="FAT-2026-LABELER-01 rows 120-239",
        captured_start=datetime(2026, 7, 10, 14, 0, tzinfo=UTC),
        captured_end=datetime(2026, 7, 10, 15, 0, tzinfo=UTC),
        clock_quality="ntp-synchronized-verified",
        engineering_unit="s",
        sample_count=120,
        test_conditions="500 ml bottles at approved commissioning speed and load",
        approved_by="controls-engineer@example.test",
        approved_at=datetime(2026, 7, 10, 16, 0, tzinfo=UTC),
        approval_reference="commissioning-review-CR-1042",
    )


def record(
    baseline_id: str = "label-presentation-v1",
    *,
    replaces: str | None = None,
    mean: float = 0.20,
) -> BaselineRecord:
    return BaselineRecord(
        baseline_id=baseline_id,
        version=baseline_id.rsplit("-", 1)[-1],
        applicability=applicability(),
        model=BaselineModel(
            mean=mean,
            stddev=0.01,
            approved_min=0.05,
            approved_max=0.35,
        ),
        evidence=evidence(),
        replaces_baseline_id=replaces,
    )


def observation(value: float, **context_overrides: str) -> BaselineObservation:
    return BaselineObservation(
        applicability=applicability(**context_overrides),
        value=value,
        unit="s",
        timestamp=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        source_id="plc-labeler-demo",
        quality="good",
    )


def test_exact_context_resolves_and_calculates_drift_inside_envelope() -> None:
    registry = BaselineRegistry((record(),))

    evaluation = registry.evaluate(
        observation(0.25),
        BaselineComparisonPolicy(
            sigma_threshold=3.0,
            minimum_absolute_drift=0.02,
        ),
    )

    assert evaluation.resolution.status is BaselineResolutionStatus.RESOLVED
    assert evaluation.assessment is not None
    assert evaluation.assessment.residual == pytest.approx(0.05)
    assert evaluation.assessment.drift_threshold == pytest.approx(0.03)
    assert evaluation.assessment.envelope_status is EnvelopeStatus.WITHIN
    assert evaluation.assessment.drift_status is DriftStatus.DRIFTED_WITHIN_ENVELOPE
    assert "does not establish a fault" in evaluation.assessment.retained_uncertainty


def test_outside_envelope_remains_distinct_from_baseline_drift() -> None:
    evaluation = BaselineRegistry((record(),)).evaluate(observation(0.40))

    assert evaluation.assessment is not None
    assert evaluation.assessment.envelope_status is EnvelopeStatus.ABOVE
    assert (
        evaluation.assessment.drift_status
        is DriftStatus.OUTSIDE_APPROVED_ENVELOPE
    )


def test_context_mismatch_returns_explicit_rejection_without_comparison() -> None:
    evaluation = BaselineRegistry((record(),)).evaluate(
        observation(0.22, firmware_version="servo-fw-3.8")
    )

    assert evaluation.resolution.status is BaselineResolutionStatus.NOT_FOUND
    assert evaluation.assessment is None
    assert evaluation.resolution.rejections[0].baseline_id == "label-presentation-v1"
    assert "firmware_version mismatch" in evaluation.resolution.rejections[0].reasons[0]


def test_multiple_exact_matches_are_ambiguous_not_silently_ranked() -> None:
    registry = BaselineRegistry(
        (
            record("label-presentation-v1"),
            record("label-presentation-independent-copy"),
        )
    )

    resolution = registry.resolve(applicability())

    assert resolution.status is BaselineResolutionStatus.AMBIGUOUS
    assert resolution.baseline is None
    assert resolution.candidate_ids == (
        "label-presentation-independent-copy",
        "label-presentation-v1",
    )


def test_append_only_replacement_preserves_history_and_selects_successor() -> None:
    first = record("label-presentation-v1")
    successor = record(
        "label-presentation-v2",
        replaces="label-presentation-v1",
        mean=0.21,
    )
    registry = BaselineRegistry((first, successor))

    assert registry.records == (first, successor)
    assert registry.effective_records == (successor,)
    assert registry.resolve(applicability()).baseline is successor


def test_invalidation_removes_baseline_without_erasing_record() -> None:
    baseline = record()
    invalidation = BaselineInvalidation(
        baseline_id=baseline.baseline_id,
        reason="Sensor was found out of calibration after commissioning review.",
        invalidated_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        invalidated_by="instrumentation-tech@example.test",
        evidence_reference="calibration-ticket-CAL-882",
    )
    registry = BaselineRegistry((baseline,), (invalidation,))

    assert registry.records == (baseline,)
    assert registry.effective_records == ()
    assert registry.resolve(applicability()).status is BaselineResolutionStatus.NOT_FOUND


def test_suspect_quality_and_unit_mismatch_are_not_compared() -> None:
    registry = BaselineRegistry((record(),))
    suspect = replace(observation(0.22), quality="suspect")
    wrong_unit = replace(observation(0.22), unit="ms")

    with pytest.raises(BaselineError, match="not comparable"):
        registry.evaluate(suspect)
    with pytest.raises(BaselineError, match="does not match baseline unit"):
        registry.evaluate(wrong_unit)


def test_replacement_cannot_change_scope_or_branch_history() -> None:
    first = record("label-presentation-v1")
    changed_scope = replace(
        record("label-presentation-v2", replaces=first.baseline_id),
        applicability=applicability(operating_mode="1l-square-bottle"),
    )
    parallel = record("label-presentation-v3", replaces=first.baseline_id)

    with pytest.raises(BaselineError, match="preserve exact applicability"):
        BaselineRegistry((first, changed_scope))
    with pytest.raises(BaselineError, match="multiple replacements"):
        BaselineRegistry((first, record("v2", replaces=first.baseline_id), parallel))


def test_timestamps_must_be_aware() -> None:
    with pytest.raises(BaselineError, match="timezone-aware"):
        replace(
            evidence(),
            captured_start=datetime(2026, 7, 10, 14, 0),
            captured_end=datetime(2026, 7, 10, 15, 0) + timedelta(0),
        )


def test_json_registry_loading_and_machine_readable_evaluation(tmp_path) -> None:
    import json

    from linealert_core.baseline_io import (
        baseline_evaluation_to_dict,
        load_baseline_registry,
    )

    registry_path = tmp_path / "baselines.json"
    registry_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "baseline_id": "label-presentation-v1",
                        "version": "1.0.0",
                        "replaces_baseline_id": None,
                        "applicability": {
                            "asset_id": "LABELER-DEMO-01",
                            "component_id": "label-feed-servo",
                            "observation_key": (
                                "lag:LabelFeedCommand->LabelAtPeelPoint"
                            ),
                            "operating_mode": "500ml-round-bottle",
                            "configuration_version": "plc-program-4.2.1",
                            "firmware_version": "servo-fw-3.7",
                            "calibration_id": "label-sensor-cal-2026-07-10",
                            "sampling_profile_id": "event-timing-v1",
                            "context_tags": {
                                "label_stock": "supplier-a-roll-42"
                            },
                        },
                        "model": {
                            "mean": 0.2,
                            "stddev": 0.01,
                            "approved_min": 0.05,
                            "approved_max": 0.35,
                        },
                        "evidence": {
                            "source_id": "commissioning-historian-export",
                            "source_reference": "FAT rows 120-239",
                            "captured_start": "2026-07-10T14:00:00Z",
                            "captured_end": "2026-07-10T15:00:00Z",
                            "clock_quality": "ntp-synchronized-verified",
                            "engineering_unit": "s",
                            "sample_count": 120,
                            "test_conditions": "approved speed and load",
                            "approved_by": "controls-engineer@example.test",
                            "approved_at": "2026-07-10T16:00:00Z",
                            "approval_reference": "commissioning-review-CR-1042",
                        },
                    }
                ],
                "invalidations": [],
            }
        ),
        encoding="utf-8",
    )

    registry = load_baseline_registry(registry_path)
    report = baseline_evaluation_to_dict(registry.evaluate(observation(0.25)))

    assert report["resolution"]["status"] == "resolved"
    assert report["assessment"]["drift_status"] == "drifted_within_envelope"
    assert report["assessment"]["envelope_status"] == "within"
