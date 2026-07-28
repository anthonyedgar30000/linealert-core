from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from linealert_core import (
    DependencyEdge,
    DeterministicStreamSimulator,
    EventIdentityCollision,
    LineAlertCore,
    MachineEvent,
    StreamConsumer,
    StreamDisposition,
    StreamEnvelope,
    StreamInputError,
    TemporalRule,
    TimingStatus,
    TopologyGraph,
    consume_stream,
    stream_summary_to_dict,
)
from linealert_core.replay import build_core_from_config, load_events, replay_events

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_core() -> LineAlertCore:
    return LineAlertCore(
        rules=[
            TemporalRule(
                rule_id="transfer-delay",
                start_event="ActuatorCommand",
                end_event="ProductTransfer",
                min_delay_seconds=2.0,
                max_delay_seconds=4.0,
                topology_from="ActuatorCommand",
                topology_to="ProductTransfer",
            )
        ],
        topology=TopologyGraph(
            [DependencyEdge("ActuatorCommand", "ProductTransfer")]
        ),
    )


def machine_event(
    event_id: str,
    event_type: str,
    seconds: int,
    *,
    correlation_id: str = "cycle-1",
) -> MachineEvent:
    return MachineEvent(
        event_id=event_id,
        source_id="plc-lab-1",
        asset_id="LABELER-LAB-01",
        component_id="labeler",
        event_type=event_type,
        timestamp=datetime(2026, 7, 28, 12, 0, seconds, tzinfo=UTC),
        correlation_id=correlation_id,
    )


def envelope(
    event: MachineEvent,
    sequence_number: int,
    *,
    session_id: str = "session-a",
    clock_quality: str = "synchronized",
    transport_attributes: dict[str, object] | None = None,
) -> StreamEnvelope:
    return StreamEnvelope(
        session_id=session_id,
        sequence_number=sequence_number,
        received_at=event.timestamp + timedelta(milliseconds=50),
        event=event,
        clock_quality=clock_quality,
        transport_attributes=transport_attributes or {"adapter": "deterministic-test"},
    )


def test_labeler_stream_matches_ordered_replay_results() -> None:
    config_path = PROJECT_ROOT / "examples" / "labeler_demo_config.json"
    events_path = PROJECT_ROOT / "examples" / "labeler_demo_events.jsonl"
    events = load_events(events_path)

    replay = replay_events(build_core_from_config(config_path), events)
    stream = consume_stream(
        build_core_from_config(config_path),
        DeterministicStreamSimulator(
            events=events,
            session_id="labeler-lab-session-1",
            ingestion_delay_seconds=0.05,
            clock_quality="synchronized",
            transport_attributes={"source": "bounded-lab-simulator"},
        ),
    )

    assert stream.transport_integrity_complete is True
    assert stream.accepted_events == len(events)
    assert stream.rejected_events == 0
    assert stream.event_fingerprints == tuple(event.fingerprint for event in events)
    assert stream.pipeline_results == replay.results
    assert stream.timing_finding_count == replay.timing_finding_count == 9
    assert stream.recommendation_count == replay.recommendation_count == 1

    late_findings = tuple(
        finding
        for result in stream.pipeline_results
        for finding in result.timing_findings
        if finding.status is TimingStatus.LATE
    )
    assert len(late_findings) == 1
    assert late_findings[0].topology_from == "LabelFeedCommand"
    assert late_findings[0].topology_to == "LabelAtPeelPoint"


def test_sequence_gap_is_retained_and_not_admitted_to_core() -> None:
    start = machine_event("e-1", "ActuatorCommand", 0)
    end = machine_event("e-2", "ProductTransfer", 5)
    consumer = StreamConsumer(make_core())

    accepted_start = consumer.consume(envelope(start, 0))
    rejected_gap = consumer.consume(envelope(end, 2))

    assert accepted_start.receipt.disposition is StreamDisposition.ACCEPTED
    assert rejected_gap.receipt.disposition is StreamDisposition.REJECTED_SEQUENCE_GAP
    assert rejected_gap.receipt.expected_sequence_number == 1
    assert rejected_gap.pipeline_result is None
    assert consumer.summary().timing_finding_count == 0

    accepted_resend = consumer.consume(envelope(end, 1))
    assert accepted_resend.receipt.disposition is StreamDisposition.ACCEPTED
    assert accepted_resend.pipeline_result is not None
    assert accepted_resend.pipeline_result.timing_findings[0].status is TimingStatus.LATE


def test_out_of_order_transport_frame_is_not_silently_reordered() -> None:
    start = machine_event("e-1", "ActuatorCommand", 0)
    consumer = StreamConsumer(make_core())

    consumer.consume(envelope(start, 0))
    result = consumer.consume(envelope(start, 0))

    assert result.receipt.disposition is StreamDisposition.REJECTED_OUT_OF_ORDER
    assert result.pipeline_result is None
    assert consumer.summary().duplicate_events == 0


def test_exact_event_duplicate_with_next_transport_sequence_remains_idempotent() -> None:
    start = machine_event("e-1", "ActuatorCommand", 0)
    consumer = StreamConsumer(make_core())

    consumer.consume(envelope(start, 0))
    duplicate = consumer.consume(envelope(start, 1))

    assert duplicate.receipt.disposition is StreamDisposition.ACCEPTED
    assert duplicate.pipeline_result is not None
    assert duplicate.pipeline_result.receipt.duplicate is True
    assert consumer.summary().duplicate_events == 1


def test_source_restart_requires_zero_and_old_session_cannot_reappear() -> None:
    first = machine_event("e-1", "ActuatorCommand", 0, correlation_id="cycle-1")
    second = machine_event("e-2", "ActuatorCommand", 1, correlation_id="cycle-2")
    consumer = StreamConsumer(make_core())

    consumer.consume(envelope(first, 0, session_id="session-a"))
    bad_restart = consumer.consume(envelope(second, 1, session_id="session-b"))
    good_restart = consumer.consume(envelope(second, 0, session_id="session-b"))
    reused_old = consumer.consume(envelope(second, 1, session_id="session-a"))

    assert bad_restart.receipt.disposition is StreamDisposition.REJECTED_SESSION_START
    assert good_restart.receipt.disposition is StreamDisposition.ACCEPTED
    assert good_restart.receipt.session_transition is True
    assert reused_old.receipt.disposition is StreamDisposition.REJECTED_SESSION_REUSE


def test_core_ingest_failure_does_not_commit_new_transport_session() -> None:
    first = machine_event("e-1", "ActuatorCommand", 0)
    colliding = machine_event("e-1", "ProductTransfer", 1)
    recovery = machine_event("e-2", "ActuatorCommand", 2, correlation_id="cycle-2")
    consumer = StreamConsumer(make_core())

    consumer.consume(envelope(first, 0, session_id="session-a"))

    with pytest.raises(EventIdentityCollision):
        consumer.consume(envelope(colliding, 0, session_id="session-b"))

    assert len(consumer.summary().results) == 1

    recovered = consumer.consume(envelope(recovery, 0, session_id="session-b"))
    assert recovered.receipt.disposition is StreamDisposition.ACCEPTED
    assert recovered.receipt.session_transition is True
    assert recovered.receipt.expected_sequence_number == 0


def test_stream_envelope_rejects_naive_receive_timestamp() -> None:
    event = machine_event("e-1", "ActuatorCommand", 0)

    with pytest.raises(StreamInputError, match="timezone-aware"):
        StreamEnvelope(
            session_id="session-a",
            sequence_number=0,
            received_at=datetime(2026, 7, 28, 12, 0),
            event=event,
        )


def test_stream_envelope_enforces_governed_clock_quality() -> None:
    event = machine_event("e-1", "ActuatorCommand", 0)

    normalized = envelope(event, 0, clock_quality=" SYNCHRONIZED ")
    assert normalized.clock_quality == "synchronized"

    with pytest.raises(StreamInputError, match="clock_quality must be one of"):
        envelope(event, 0, clock_quality="gps_locked")


def test_transport_attributes_are_deeply_frozen_and_json_compatible() -> None:
    event = machine_event("e-1", "ActuatorCommand", 0)
    supplied = {
        "adapter": "lab",
        "route": {"hops": ["collector-a", "collector-b"]},
        "retry": 0,
    }
    transport = envelope(event, 0, transport_attributes=supplied)
    supplied["route"]["hops"].append("mutated-after-envelope")

    assert transport.transport_attributes["route"]["hops"] == (
        "collector-a",
        "collector-b",
    )

    summary = consume_stream(make_core(), (transport,))
    report = stream_summary_to_dict(summary)
    attributes = report["envelopes"][0]["transport"]["transport_attributes"]

    assert attributes == {
        "adapter": "lab",
        "retry": 0,
        "route": {"hops": ["collector-a", "collector-b"]},
    }
    json.dumps(report, sort_keys=True)


@pytest.mark.parametrize(
    "attributes",
    [
        {"unsupported": {"set-value"}},
        {"non_finite": float("nan")},
        {1: "non-string-key"},
    ],
)
def test_transport_attributes_reject_non_evidence_values(
    attributes: dict[object, object],
) -> None:
    event = machine_event("e-1", "ActuatorCommand", 0)

    with pytest.raises(StreamInputError):
        envelope(event, 0, transport_attributes=attributes)


def test_stream_report_preserves_transport_and_source_timestamps() -> None:
    event = machine_event("e-1", "ActuatorCommand", 0)
    summary = consume_stream(
        make_core(),
        DeterministicStreamSimulator(
            events=(event,),
            session_id="session-a",
            clock_quality="synchronized",
            transport_attributes={"adapter": "lab"},
        ),
    )

    report = stream_summary_to_dict(summary)
    transport = report["envelopes"][0]["transport"]

    assert report["summary"]["transport_integrity_complete"] is True
    assert transport["source_timestamp"] == event.timestamp.isoformat()
    assert transport["received_at"] != transport["source_timestamp"]
    assert transport["clock_quality"] == "synchronized"
    assert transport["transport_attributes"] == {"adapter": "lab"}
