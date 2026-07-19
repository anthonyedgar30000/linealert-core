from __future__ import annotations

import json
from pathlib import Path

import pytest

from linealert_core import CheckDisposition, DiagnosticProjectionError
from linealert_core.diagnostic_cli import main
from linealert_core.diagnostic_io import (
    collect_timing_findings,
    load_diagnostic_engine,
    load_operator_report,
    projection_to_dict,
)
from linealert_core.replay import build_core_from_config, load_events, replay_events

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / "examples" / "labeler_demo_config.json"
EVENTS_PATH = REPOSITORY_ROOT / "examples" / "labeler_demo_events.jsonl"
GUIDE_PATH = REPOSITORY_ROOT / "examples" / "labeler_diagnostic_guide.json"
REPORT_PATH = REPOSITORY_ROOT / "examples" / "labeler_operator_report.json"


def build_projection():
    core = build_core_from_config(CONFIG_PATH)
    summary = replay_events(core, load_events(EVENTS_PATH))
    engine = load_diagnostic_engine(
        GUIDE_PATH,
        machine_profile=core.machine_profile,
        topology=core.topology,
    )
    operator_report = load_operator_report(REPORT_PATH)
    projection = engine.project(
        operator_report=operator_report,
        timing_findings=collect_timing_findings(summary.results),
    )
    return projection


def test_projection_combines_operator_timeline_guide_and_machine_evidence() -> None:
    projection = build_projection()
    report = projection_to_dict(projection)

    assert projection.operator_report.reported_start is not None
    assert projection.operator_report.reported_start.isoformat() == (
        "2026-07-19T13:40:00+00:00"
    )
    assert projection.first_observed_deviation is not None
    assert projection.first_observed_deviation.rule_id == (
        "label-presentation-delay"
    )
    assert projection.first_observed_deviation.topology_from == (
        "LabelFeedCommand"
    )
    assert projection.first_observed_deviation.topology_to == (
        "LabelAtPeelPoint"
    )

    assert len(projection.abnormal_relationships) == 1
    assert len(projection.healthy_relationships) == 8
    assert projection.investigation_region is not None
    assert projection.investigation_region.upstream == "LabelFeedCommand"
    assert projection.investigation_region.downstream == "LabelAtPeelPoint"

    assert projection.check_assessments[0].check_id == (
        "inspect-label-presentation"
    )
    assert (
        projection.check_assessments[0].disposition
        is CheckDisposition.EVIDENCE_ALIGNED
    )
    assert projection.check_assessments[1].check_id == "verify-web-path"
    assert (
        projection.check_assessments[2].disposition
        is CheckDisposition.DEPRIORITIZED_BY_HEALTHY_EVIDENCE
    )
    assert "does not establish a root cause" in (
        projection.retained_uncertainty
    )
    assert "infer when degradation began" in projection.retained_uncertainty

    assert report["operator_report"]["recent_changes"][0].startswith(
        "A new label roll"
    )
    assert report["first_observed_deviation"]["delay_seconds"] == (
        pytest.approx(0.55)
    )
    assert report["ranked_checks"][0]["disposition"] == "evidence_aligned"


def test_projection_does_not_turn_one_cycle_into_a_degradation_timeline() -> None:
    projection = build_projection()
    rendered = json.dumps(projection_to_dict(projection))

    assert "became late" not in rendered
    assert "degradation began at" not in rendered
    assert "infer when degradation began" in rendered


def test_guide_only_check_remains_visible_without_invented_evidence() -> None:
    core = build_core_from_config(CONFIG_PATH)
    summary = replay_events(core, load_events(EVENTS_PATH))
    engine = load_diagnostic_engine(
        GUIDE_PATH,
        machine_profile=core.machine_profile,
        topology=core.topology,
    )
    operator_report = load_operator_report(REPORT_PATH)
    stretch_report = type(operator_report)(
        symptom_id="label-stretch-lines",
        reported_start=operator_report.reported_start,
        description="Operator reports intermittent stretch lines.",
        operating_mode=operator_report.operating_mode,
    )

    projection = engine.project(
        operator_report=stretch_report,
        timing_findings=collect_timing_findings(summary.results),
    )

    speed_check = next(
        assessment
        for assessment in projection.check_assessments
        if assessment.check_id == "check-speed-interaction"
    )
    assert speed_check.disposition is CheckDisposition.GUIDE_ONLY
    assert "does not directly assess" in speed_check.evidence[0]


def test_diagnostic_guide_rejects_unknown_machine_reference(
    tmp_path: Path,
) -> None:
    raw = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    raw["symptoms"][0]["checks"][0]["component_ids"].append(
        "unknown-component"
    )
    guide_path = tmp_path / "invalid-guide.json"
    guide_path.write_text(json.dumps(raw), encoding="utf-8")

    core = build_core_from_config(CONFIG_PATH)
    with pytest.raises(DiagnosticProjectionError, match="unknown component"):
        load_diagnostic_engine(
            guide_path,
            machine_profile=core.machine_profile,
            topology=core.topology,
        )


def test_unknown_symptom_is_rejected() -> None:
    core = build_core_from_config(CONFIG_PATH)
    summary = replay_events(core, load_events(EVENTS_PATH))
    engine = load_diagnostic_engine(
        GUIDE_PATH,
        machine_profile=core.machine_profile,
        topology=core.topology,
    )
    operator_report = load_operator_report(REPORT_PATH)
    unknown_report = type(operator_report)(
        symptom_id="unknown-symptom",
        reported_start=operator_report.reported_start,
        description="Unknown issue.",
        operating_mode=operator_report.operating_mode,
    )

    with pytest.raises(DiagnosticProjectionError, match="not declared"):
        engine.project(
            operator_report=unknown_report,
            timing_findings=collect_timing_findings(summary.results),
        )


def test_diagnostic_cli_writes_combined_report(tmp_path: Path) -> None:
    output_path = tmp_path / "diagnostic-report.json"

    exit_code = main(
        [
            "--config",
            str(CONFIG_PATH),
            "--input",
            str(EVENTS_PATH),
            "--guide",
            str(GUIDE_PATH),
            "--operator-report",
            str(REPORT_PATH),
            "--output",
            str(output_path),
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["summary"]["timing_findings"] == 9
    assert report["diagnostic_projection"]["symptom"]["symptom_id"] == (
        "label-alignment-off"
    )
    assert report["diagnostic_projection"]["first_observed_deviation"][
        "status"
    ] == "late"
