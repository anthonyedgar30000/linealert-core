from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from linealert_core import (
    SignalAnalysisError,
    SignalAnalysisPolicy,
    SignalPattern,
    TimingFinding,
    TimingSignalAnalyzer,
    TimingStatus,
)
from linealert_core.diagnostic_cli import main
from linealert_core.diagnostic_io import (
    collect_timing_findings,
    load_diagnostic_engine,
    load_operator_report,
)
from linealert_core.replay import build_core_from_config, load_events, replay_events
from linealert_core.signal_io import load_signal_policy

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / "examples" / "labeler_demo_config.json"
HISTORY_PATH = REPOSITORY_ROOT / "examples" / "labeler_timing_history.jsonl"
GUIDE_PATH = REPOSITORY_ROOT / "examples" / "labeler_diagnostic_guide.json"
REPORT_PATH = REPOSITORY_ROOT / "examples" / "labeler_operator_report.json"
POLICY_PATH = REPOSITORY_ROOT / "examples" / "labeler_signal_policy.json"


def test_historical_labeler_series_detects_degradation_patterns() -> None:
    core = build_core_from_config(CONFIG_PATH)
    summary = replay_events(core, load_events(HISTORY_PATH))
    operator_report = load_operator_report(REPORT_PATH)
    policy = load_signal_policy(POLICY_PATH)

    assessments = TimingSignalAnalyzer(policy).analyze(
        collect_timing_findings(summary.results),
        operator_reported_start=operator_report.reported_start,
    )

    assert len(assessments) == 1
    assessment = assessments[0]
    assert assessment.sample_count == 18
    assert assessment.baseline_source == "healthy_before_operator_report"
    assert assessment.baseline_count == 6
    assert assessment.outside_count == 5
    assert assessment.recent_outside_count == 5
    assert SignalPattern.RECURRING_EXCURSIONS in assessment.patterns
    assert SignalPattern.RISING_VARIABILITY in assessment.patterns
    assert SignalPattern.GRADUAL_DRIFT in assessment.patterns
    assert SignalPattern.SUSTAINED_SHIFT in assessment.patterns
    assert assessment.candidate_change_timestamp is not None
    assert assessment.candidate_change_timestamp.isoformat() == (
        "2026-07-19T13:34:00+00:00"
    )
    assert assessment.timeline_relation == "candidate_before_operator_report"
    assert assessment.candidate_offset_from_report_seconds == pytest.approx(-360.0)
    assert "not the proven start of degradation" in assessment.retained_uncertainty


def test_signal_patterns_improve_diagnostic_projection_ranking() -> None:
    core = build_core_from_config(CONFIG_PATH)
    summary = replay_events(core, load_events(HISTORY_PATH))
    timing_findings = collect_timing_findings(summary.results)
    operator_report = load_operator_report(REPORT_PATH)
    signal_assessments = TimingSignalAnalyzer(
        load_signal_policy(POLICY_PATH)
    ).analyze(
        timing_findings,
        operator_reported_start=operator_report.reported_start,
    )
    engine = load_diagnostic_engine(
        GUIDE_PATH,
        machine_profile=core.machine_profile,
        topology=core.topology,
    )

    projection = engine.project(
        operator_report=operator_report,
        timing_findings=timing_findings,
        signal_assessments=signal_assessments,
    )

    assert projection.primary_signal_assessment is not None
    assert projection.primary_signal_assessment.rule_id == (
        "label-presentation-delay"
    )
    assert projection.investigation_region is not None
    assert projection.investigation_region.upstream == "LabelFeedCommand"
    assert projection.investigation_region.downstream == "LabelAtPeelPoint"
    assert projection.check_assessments[0].check_id == (
        "inspect-label-presentation"
    )
    assert "gradual_drift" in projection.check_assessments[0].evidence[0]
    assert "candidate statistical change point" in projection.retained_uncertainty


def test_isolated_excursion_remains_distinct_from_sustained_shift() -> None:
    start = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    values = (
        0.20,
        0.21,
        0.19,
        0.20,
        0.22,
        0.20,
        0.40,
        0.21,
        0.20,
        0.19,
        0.21,
        0.20,
    )
    findings = tuple(
        _finding(start + timedelta(minutes=index), value, index)
        for index, value in enumerate(values)
    )

    assessment = TimingSignalAnalyzer(_policy()).analyze(findings)[0]

    assert assessment.patterns == (SignalPattern.ISOLATED_EXCURSION,)
    assert assessment.candidate_change_timestamp is None


def test_small_series_is_marked_insufficient() -> None:
    start = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    findings = tuple(
        _finding(start + timedelta(minutes=index), 0.20, index)
        for index in range(5)
    )

    assessment = TimingSignalAnalyzer(_policy()).analyze(findings)[0]

    assert assessment.patterns == (SignalPattern.INSUFFICIENT_DATA,)
    assert not assessment.has_actionable_pattern


def test_policy_rejects_hidden_or_incoherent_thresholds() -> None:
    with pytest.raises(SignalAnalysisError, match="variability_ratio"):
        SignalAnalysisPolicy(
            policy_id="invalid",
            version="1",
            minimum_points=12,
            baseline_points=6,
            recent_points=5,
            sustained_outside_points=3,
            recurring_excursion_count=2,
            variability_ratio=1.0,
            variability_min_envelope_fraction=0.05,
            drift_min_envelope_fraction=0.25,
            drift_min_directional_fraction=0.65,
            change_point_min_segment_points=4,
            change_point_min_mean_shift_fraction=0.20,
        )


def test_diagnostic_cli_emits_historical_signal_analysis(tmp_path: Path) -> None:
    output_path = tmp_path / "historical-diagnostic-report.json"

    exit_code = main(
        [
            "--config",
            str(CONFIG_PATH),
            "--input",
            str(HISTORY_PATH),
            "--guide",
            str(GUIDE_PATH),
            "--operator-report",
            str(REPORT_PATH),
            "--signal-policy",
            str(POLICY_PATH),
            "--output",
            str(output_path),
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    signal = report["timing_signal_analysis"][0]
    assert exit_code == 0
    assert report["summary"]["total_events"] == 36
    assert report["summary"]["timing_findings"] == 18
    assert signal["relationship"]["rule_id"] == "label-presentation-delay"
    assert signal["patterns"] == [
        "recurring_excursions",
        "rising_variability",
        "gradual_drift",
        "sustained_shift",
    ]
    assert signal["candidate_change"]["timeline_relation"] == (
        "candidate_before_operator_report"
    )
    assert report["diagnostic_projection"]["primary_signal_relationship"][
        "from"
    ] == "LabelFeedCommand"


def _policy() -> SignalAnalysisPolicy:
    return SignalAnalysisPolicy(
        policy_id="test-policy",
        version="1",
        minimum_points=12,
        baseline_points=6,
        recent_points=5,
        sustained_outside_points=3,
        recurring_excursion_count=2,
        variability_ratio=2.0,
        variability_min_envelope_fraction=0.05,
        drift_min_envelope_fraction=0.25,
        drift_min_directional_fraction=0.65,
        change_point_min_segment_points=4,
        change_point_min_mean_shift_fraction=0.20,
    )


def _finding(timestamp: datetime, delay: float, index: int) -> TimingFinding:
    status = TimingStatus.LATE if delay > 0.35 else TimingStatus.WITHIN
    return TimingFinding(
        rule_id="label-presentation-delay",
        asset_id="LABELER-DEMO-01",
        correlation_id=f"cycle-{index}",
        start_timestamp=timestamp,
        end_timestamp=timestamp + timedelta(seconds=delay),
        delay_seconds=delay,
        min_delay_seconds=0.05,
        max_delay_seconds=0.35,
        status=status,
        topology_from="LabelFeedCommand",
        topology_to="LabelAtPeelPoint",
    )
