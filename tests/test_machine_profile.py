from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from linealert_core import MachineProfileError, TimingStatus
from linealert_core.replay import (
    ReplayInputError,
    build_core_from_config,
    load_events,
    replay_events,
    summary_to_dict,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / "examples" / "labeler_demo_config.json"
EVENTS_PATH = REPOSITORY_ROOT / "examples" / "labeler_demo_events.jsonl"


def test_full_labeler_profile_replays_one_localized_deviation() -> None:
    core = build_core_from_config(CONFIG_PATH)
    events = load_events(EVENTS_PATH)
    summary = replay_events(core, events)
    report = summary_to_dict(summary)

    assert core.machine_profile is not None
    assert core.machine_profile.profile_id == "generic-pressure-sensitive-labeler-demo-v1"
    assert core.machine_profile.asset_id == "LABELER-DEMO-01"
    assert len(core.machine_profile.components) == 12
    assert len(core.machine_profile.component_dependencies) == 11
    assert len(core.topology.edges) == 9

    assert summary.total_events == 10
    assert summary.duplicate_events == 0
    assert summary.timing_finding_count == 9
    assert summary.recommendation_count == 1

    late_findings = [
        finding
        for result in summary.results
        for finding in result.timing_findings
        if finding.status is TimingStatus.LATE
    ]
    assert len(late_findings) == 1
    assert late_findings[0].rule_id == "label-presentation-delay"
    assert late_findings[0].delay_seconds == pytest.approx(0.55)

    recommendation = summary.results[5].recommendations[0]
    assert recommendation.topology.upstream == "LabelFeedCommand"
    assert recommendation.topology.downstream == "LabelAtPeelPoint"
    assert "cause remains unresolved" in recommendation.interpretation

    assert report["machine_profile"]["profile_id"] == (
        "generic-pressure-sensitive-labeler-demo-v1"
    )
    assert len(report["process_topology"]["dependencies"]) == 9


def test_profile_rejects_undeclared_component() -> None:
    core = build_core_from_config(CONFIG_PATH)
    event = replace(load_events(EVENTS_PATH)[0], component_id="unknown-component")

    with pytest.raises(MachineProfileError, match="undeclared component"):
        core.ingest(event)


def test_profile_rejects_event_bound_to_wrong_component() -> None:
    core = build_core_from_config(CONFIG_PATH)
    event = replace(load_events(EVENTS_PATH)[0], component_id="spacing-conveyor")

    with pytest.raises(MachineProfileError, match="not bound to component"):
        core.ingest(event)


def test_profile_rejects_unapproved_operating_mode() -> None:
    core = build_core_from_config(CONFIG_PATH)
    event = replace(
        load_events(EVENTS_PATH)[0],
        attributes={"operating_mode": "unapproved-bottle"},
    )

    with pytest.raises(MachineProfileError, match="not approved"):
        core.ingest(event)


def test_config_rejects_topology_event_missing_from_profile(tmp_path: Path) -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["topology"]["dependencies"].append(
        {"from": "UnknownEvent", "to": "ProductReleased"}
    )
    config_path = tmp_path / "invalid-profile.json"
    config_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ReplayInputError, match="not declared by machine profile"):
        build_core_from_config(config_path)
