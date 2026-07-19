from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from linealert_core import EventQuality, TimingStatus
from linealert_core.cli import main
from linealert_core.replay import (
    ReplayInputError,
    build_core_from_config,
    load_events,
    replay_events,
    summary_to_dict,
)


def write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "topology": {
                    "dependencies": [
                        {"from": "ActuatorCommand", "to": "ProductTransfer"}
                    ]
                },
                "temporal_rules": [
                    {
                        "rule_id": "transfer-delay",
                        "start_event": "ActuatorCommand",
                        "end_event": "ProductTransfer",
                        "min_delay_seconds": 2.0,
                        "max_delay_seconds": 4.0,
                        "topology_from": "ActuatorCommand",
                        "topology_to": "ProductTransfer",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def event_payload(
    event_id: str,
    event_type: str,
    timestamp: str,
    *,
    correlation_id: str = "cycle-1",
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "source_id": "plc-1",
        "asset_id": "LABELER-04",
        "component_id": "labeler",
        "event_type": event_type,
        "timestamp": timestamp,
        "correlation_id": correlation_id,
    }


def test_jsonl_replay_emits_late_finding_and_recommendation(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    events_path = tmp_path / "events.jsonl"
    write_config(config_path)
    events_path.write_text(
        "\n".join(
            json.dumps(payload)
            for payload in (
                event_payload("e-1", "ActuatorCommand", "2026-07-19T12:00:00Z"),
                event_payload("e-2", "ProductTransfer", "2026-07-19T12:00:05Z"),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    summary = replay_events(build_core_from_config(config_path), load_events(events_path))

    assert summary.total_events == 2
    assert summary.timing_finding_count == 1
    assert summary.recommendation_count == 1
    assert summary.results[-1].timing_findings[0].status is TimingStatus.LATE
    assert "does not prove a root cause" in (
        summary.results[-1].recommendations[0].retained_uncertainty
    )


def test_csv_loader_preserves_measurement_quality_and_attributes(tmp_path: Path) -> None:
    events_path = tmp_path / "events.csv"
    with events_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=[
                "event_id",
                "source_id",
                "asset_id",
                "component_id",
                "event_type",
                "timestamp",
                "correlation_id",
                "value",
                "unit",
                "quality",
                "attributes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                **event_payload("e-1", "ServoCurrent", "2026-07-19T12:00:00+00:00"),
                "value": "3.8",
                "unit": "A",
                "quality": "suspect",
                "attributes": json.dumps({"recipe": "500ml"}),
            }
        )

    event = load_events(events_path)[0]

    assert event.value == 3.8
    assert event.unit == "A"
    assert event.quality is EventQuality.SUSPECT
    assert event.attributes["recipe"] == "500ml"


def test_loader_rejects_naive_timestamp(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        json.dumps(event_payload("e-1", "ActuatorCommand", "2026-07-19T12:00:00")),
        encoding="utf-8",
    )

    with pytest.raises(ReplayInputError, match="timezone-aware"):
        load_events(events_path)


def test_replay_counts_exact_duplicate_events(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    events_path = tmp_path / "events.jsonl"
    write_config(config_path)
    payload = event_payload("e-1", "ActuatorCommand", "2026-07-19T12:00:00Z")
    events_path.write_text(
        json.dumps(payload) + "\n" + json.dumps(payload) + "\n",
        encoding="utf-8",
    )

    summary = replay_events(build_core_from_config(config_path), load_events(events_path))

    assert summary.total_events == 2
    assert summary.duplicate_events == 1
    assert summary_to_dict(summary)["events"][1]["receipt"]["duplicate"] is True


def test_cli_writes_machine_readable_report(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    events_path = tmp_path / "events.jsonl"
    output_path = tmp_path / "report.json"
    write_config(config_path)
    events_path.write_text(
        json.dumps(event_payload("e-1", "ActuatorCommand", "2026-07-19T12:00:00Z"))
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--input",
            str(events_path),
            "--output",
            str(output_path),
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["summary"]["total_events"] == 1
    assert report["events"][0]["receipt"]["delivered_to"] == ["timing-monitor"]
