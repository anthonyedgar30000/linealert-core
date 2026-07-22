from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from linealert_core import (
    BaselineApplicability,
    BaselineComparisonPolicy,
    BaselineEvidence,
    BaselineModel,
    BaselineRecord,
    BaselineRegistry,
    DependencyEdge,
    DriftStatus,
    EnvelopeStatus,
    EventQuality,
    LineAlertCore,
    MachineEvent,
    TemporalRule,
    TimingBaselineContext,
    TimingBaselineDisposition,
    TimingStatus,
    TopologyGraph,
    assess_replay_timing_baselines,
    load_timing_baseline_contexts,
    replay_events,
    timing_baseline_assessment_to_dict,
)
from linealert_core.baseline import BaselineError
from linealert_core.cli import main


def replay_summary(delay_seconds: float):
    topology = TopologyGraph(
        [DependencyEdge(upstream="LabelFeedCommand", downstream="LabelAtPeelPoint")]
    )
    core = LineAlertCore(
        rules=[
            TemporalRule(
                rule_id="label-presentation-delay",
                start_event="LabelFeedCommand",
                end_event="LabelAtPeelPoint",
                min_delay_seconds=2.0,
                max_delay_seconds=4.0,
                topology_from="LabelFeedCommand",
                topology_to="LabelAtPeelPoint",
            )
        ],
        topology=topology,
    )
    start = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    events = (
        MachineEvent(
            event_id="start-1",
            source_id="plc-labeler-demo",
            asset_id="LABELER-DEMO-01",
            component_id="label-feed-servo",
            event_type="LabelFeedCommand",
            timestamp=start,
            correlation_id="cycle-1",
            quality=EventQuality.GOOD,
        ),
        MachineEvent(
            event_id="end-1",
            source_id="plc-labeler-demo",
            asset_id="LABELER-DEMO-01",
            component_id="label-feed-servo",
            event_type="LabelAtPeelPoint",
            timestamp=start + timedelta(seconds=delay_seconds),
            correlation_id="cycle-1",
            quality=EventQuality.GOOD,
        ),
    )
    return replay_events(core, events)


def baseline_registry(*, approved_max: float = 4.0) -> BaselineRegistry:
    applicability = BaselineApplicability(
        asset_id="LABELER-DEMO-01",
        component_id="label-feed-servo",
        observation_key="lag:LabelFeedCommand->LabelAtPeelPoint",
        operating_mode="500ml-round-bottle",
        configuration_version="plc-program-4.2.1",
        firmware_version="servo-fw-3.7",
        calibration_id="label-sensor-cal-2026-07-10",
        sampling_profile_id="event-timing-v1",
        context_tags={"label_stock": "supplier-a-roll-42"},
    )
    return BaselineRegistry(
        (
            BaselineRecord(
                baseline_id="label-presentation-v1",
                version="1.0.0",
                applicability=applicability,
                model=BaselineModel(
                    mean=3.0,
                    stddev=0.1,
                    approved_min=2.0,
                    approved_max=approved_max,
                ),
                evidence=BaselineEvidence(
                    source_id="commissioning-historian-export",
                    source_reference="FAT rows 120-239",
                    captured_start=datetime(2026, 7, 10, 14, 0, tzinfo=UTC),
                    captured_end=datetime(2026, 7, 10, 15, 0, tzinfo=UTC),
                    clock_quality="ntp-synchronized-verified",
                    engineering_unit="s",
                    sample_count=120,
                    test_conditions="approved commissioning speed and nominal load",
                    approved_by="controls-engineer@example.test",
                    approved_at=datetime(2026, 7, 10, 16, 0, tzinfo=UTC),
                    approval_reference="commissioning-review-CR-1042",
                ),
            ),
        )
    )


def context(**overrides: str) -> TimingBaselineContext:
    values = {
        "rule_id": "label-presentation-delay",
        "component_id": "label-feed-servo",
        "operating_mode": "500ml-round-bottle",
        "configuration_version": "plc-program-4.2.1",
        "firmware_version": "servo-fw-3.7",
        "calibration_id": "label-sensor-cal-2026-07-10",
        "sampling_profile_id": "event-timing-v1",
        "observation_source_id": "replay-derived-timing",
        "observation_quality": "good",
    }
    values.update(overrides)
    return TimingBaselineContext(
        **values,
        context_tags={"label_stock": "supplier-a-roll-42"},
    )


def test_replay_timing_finding_resolves_baseline_and_calculates_drift() -> None:
    assessment = assess_replay_timing_baselines(
        replay_summary(3.5),
        baseline_registry(),
        (context(),),
        BaselineComparisonPolicy(
            sigma_threshold=3.0,
            minimum_absolute_drift=0.2,
        ),
    )

    result = assessment.results[0]
    assert result.temporal_rule_status is TimingStatus.WITHIN
    assert result.disposition is TimingBaselineDisposition.EVALUATED
    assert result.evaluation is not None
    assert result.evaluation.assessment is not None
    assert result.evaluation.assessment.drift_status is DriftStatus.DRIFTED_WITHIN_ENVELOPE
    assert result.evaluation.assessment.envelope_status is EnvelopeStatus.WITHIN
    assert assessment.drifted_count == 1


def test_temporal_rule_and_baseline_envelope_remain_separate() -> None:
    assessment = assess_replay_timing_baselines(
        replay_summary(3.5),
        baseline_registry(approved_max=3.2),
        (context(),),
    )

    result = assessment.results[0]
    assert result.temporal_rule_status is TimingStatus.WITHIN
    assert result.evaluation is not None
    assert result.evaluation.assessment is not None
    assert result.evaluation.assessment.envelope_status is EnvelopeStatus.ABOVE
    assert (
        result.evaluation.assessment.drift_status
        is DriftStatus.OUTSIDE_APPROVED_ENVELOPE
    )
    assert "separate bounded comparisons" in result.retained_uncertainty


def test_missing_context_and_mismatched_context_remain_explicit() -> None:
    missing = assess_replay_timing_baselines(
        replay_summary(3.1),
        baseline_registry(),
        (),
    )
    mismatch = assess_replay_timing_baselines(
        replay_summary(3.1),
        baseline_registry(),
        (context(firmware_version="servo-fw-3.8"),),
    )

    assert (
        missing.results[0].disposition
        is TimingBaselineDisposition.CONTEXT_NOT_CONFIGURED
    )
    assert missing.results[0].evaluation is None
    assert mismatch.results[0].evaluation is not None
    assert mismatch.results[0].evaluation.assessment is None
    assert mismatch.not_found_count == 1


def test_non_comparable_timing_quality_is_rejected_without_diagnosis() -> None:
    assessment = assess_replay_timing_baselines(
        replay_summary(3.1),
        baseline_registry(),
        (context(observation_quality="suspect"),),
    )

    result = assessment.results[0]
    assert result.disposition is TimingBaselineDisposition.COMPARISON_REJECTED
    assert result.evaluation is None
    assert result.rejection_reason is not None
    assert "not comparable" in result.rejection_reason
    assert assessment.rejected_count == 1


def test_context_loader_rejects_duplicate_rule_ids(tmp_path: Path) -> None:
    path = tmp_path / "contexts.json"
    payload = {
        "contexts": [
            {
                "rule_id": "label-presentation-delay",
                "component_id": "label-feed-servo",
                "operating_mode": "500ml-round-bottle",
                "configuration_version": "plc-program-4.2.1",
                "firmware_version": "servo-fw-3.7",
                "calibration_id": "label-sensor-cal-2026-07-10",
                "sampling_profile_id": "event-timing-v1",
                "observation_source_id": "replay-derived-timing",
                "context_tags": {"label_stock": "supplier-a-roll-42"},
            }
        ]
        * 2
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BaselineError, match="must be unique"):
        load_timing_baseline_contexts(path)


def test_cli_emits_machine_readable_timing_baseline_assessment(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    events_path = tmp_path / "events.jsonl"
    registry_path = tmp_path / "baselines.json"
    contexts_path = tmp_path / "contexts.json"
    output_path = tmp_path / "report.json"

    config_path.write_text(
        json.dumps(
            {
                "topology": {
                    "dependencies": [
                        {
                            "from": "LabelFeedCommand",
                            "to": "LabelAtPeelPoint",
                        }
                    ]
                },
                "temporal_rules": [
                    {
                        "rule_id": "label-presentation-delay",
                        "start_event": "LabelFeedCommand",
                        "end_event": "LabelAtPeelPoint",
                        "min_delay_seconds": 2.0,
                        "max_delay_seconds": 4.0,
                        "topology_from": "LabelFeedCommand",
                        "topology_to": "LabelAtPeelPoint",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    events_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_id": "start-1",
                        "source_id": "plc-labeler-demo",
                        "asset_id": "LABELER-DEMO-01",
                        "component_id": "label-feed-servo",
                        "event_type": "LabelFeedCommand",
                        "timestamp": "2026-07-22T12:00:00Z",
                        "correlation_id": "cycle-1",
                    }
                ),
                json.dumps(
                    {
                        "event_id": "end-1",
                        "source_id": "plc-labeler-demo",
                        "asset_id": "LABELER-DEMO-01",
                        "component_id": "label-feed-servo",
                        "event_type": "LabelAtPeelPoint",
                        "timestamp": "2026-07-22T12:00:03.5Z",
                        "correlation_id": "cycle-1",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
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
                            "mean": 3.0,
                            "stddev": 0.1,
                            "approved_min": 2.0,
                            "approved_max": 4.0,
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
    contexts_path.write_text(
        json.dumps(
            {
                "contexts": [
                    {
                        "rule_id": "label-presentation-delay",
                        "component_id": "label-feed-servo",
                        "operating_mode": "500ml-round-bottle",
                        "configuration_version": "plc-program-4.2.1",
                        "firmware_version": "servo-fw-3.7",
                        "calibration_id": "label-sensor-cal-2026-07-10",
                        "sampling_profile_id": "event-timing-v1",
                        "observation_source_id": "replay-derived-timing",
                        "context_tags": {
                            "label_stock": "supplier-a-roll-42"
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--input",
            str(events_path),
            "--baseline-registry",
            str(registry_path),
            "--timing-baseline-contexts",
            str(contexts_path),
            "--baseline-minimum-absolute-drift",
            "0.2",
            "--output",
            str(output_path),
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    baseline_report = report["timing_baseline_assessment"]
    assert exit_code == 0
    assert baseline_report["summary"]["baseline_resolved"] == 1
    assert baseline_report["summary"]["drifted_within_envelope"] == 1
    assert baseline_report["results"][0]["temporal_rule_status"] == "within"
    assert (
        baseline_report["results"][0]["baseline_evaluation"]["assessment"][
            "drift_status"
        ]
        == "drifted_within_envelope"
    )


def test_machine_readable_report_preserves_resolution_rejections() -> None:
    assessment = assess_replay_timing_baselines(
        replay_summary(3.1),
        baseline_registry(),
        (context(firmware_version="servo-fw-3.8"),),
    )

    report = timing_baseline_assessment_to_dict(assessment)

    assert report["summary"]["baseline_not_found"] == 1
    reasons = report["results"][0]["baseline_evaluation"]["resolution"][
        "rejections"
    ][0]["reasons"]
    assert any("firmware_version mismatch" in reason for reason in reasons)
