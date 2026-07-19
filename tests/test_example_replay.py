from __future__ import annotations

from pathlib import Path

from linealert_core import TimingStatus
from linealert_core.replay import (
    build_core_from_config,
    load_events,
    replay_events,
    summary_to_dict,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_shipped_example_runs_end_to_end() -> None:
    config_path = REPOSITORY_ROOT / "examples" / "replay_config.json"
    events_path = REPOSITORY_ROOT / "examples" / "events.jsonl"

    core = build_core_from_config(config_path)
    events = load_events(events_path)
    summary = replay_events(core, events)
    report = summary_to_dict(summary)

    assert summary.total_events == 2
    assert summary.duplicate_events == 0
    assert summary.timing_finding_count == 1
    assert summary.recommendation_count == 1

    finding = summary.results[-1].timing_findings[0]
    recommendation = summary.results[-1].recommendations[0]

    assert finding.rule_id == "transfer-delay"
    assert finding.delay_seconds == 5.0
    assert finding.status is TimingStatus.LATE
    assert recommendation.topology.upstream == "ActuatorCommand"
    assert recommendation.topology.downstream == "ProductTransfer"
    assert "physical or logical cause remains unresolved" in recommendation.interpretation
    assert "does not prove a root cause" in recommendation.retained_uncertainty

    assert report["summary"] == {
        "total_events": 2,
        "duplicate_events": 0,
        "timing_findings": 1,
        "recommendations": 1,
    }
