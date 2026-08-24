from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from linealert_core import (
    DependencyEdge,
    DeterministicStreamSimulator,
    LineAlertCore,
    LiveConditionConsumer,
    MachineEvent,
    StreamEnvelope,
    TemporalRule,
    TimingConditionBinding,
    TopologyGraph,
    build_core_from_config,
    condition_signal_projection_to_dict,
    live_condition_summary_to_dict,
    load_condition_signal_bindings,
    load_events,
    project_replay_condition_signals,
    replay_events,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_labeler_live_stream_emits_exact_measured_relationship() -> None:
    events = load_events(PROJECT_ROOT / "examples" / "labeler_demo_events.jsonl")
    bindings = load_condition_signal_bindings(
        PROJECT_ROOT / "examples" / "condition_signal_bindings.json"
    )
    consumer = LiveConditionConsumer(
        build_core_from_config(PROJECT_ROOT / "examples" / "labeler_demo_config.json"),
        bindings,
    )

    emitted = []
    for envelope in DeterministicStreamSimulator(
        events=events,
        session_id="labeler-live-session-1",
        ingestion_delay_seconds=0.05,
        clock_quality="synchronized",
        transport_attributes={"source": "bounded-lab-simulator"},
    ):
        result = consumer.consume(envelope)
        emitted.extend(result.measurements)

    assert len(emitted) == 1
    measurement = emitted[0]
    observation = measurement.observation
    assert observation.signal_name == "label_presentation_delay_ms"
    assert observation.value == 550.0
    assert observation.min_value == 50.0
    assert observation.max_value == 350.0
    assert observation.temporal_rule_status == "late"
    assert observation.start_event_id == "labeler-cycle-1001-05"
    assert observation.end_event_id == "labeler-cycle-1001-06"
    assert observation.start_source_id == "plc-labeler-demo"
    assert observation.end_source_id == "plc-labeler-demo"
    assert measurement.clock_evidence.basis == "same_source_relative_interval"
    assert measurement.clock_evidence.start_clock_quality == "synchronized"
    assert measurement.clock_evidence.end_clock_quality == "synchronized"

    summary = consumer.summary()
    assert summary.measurement_count == 1
    assert summary.refusal_count == 0
    assert summary.stream_summary.accepted_events == len(events)

    report = live_condition_summary_to_dict(summary)
    assert report["condition_signals"]["count"] == 1
    assert report["condition_signals"]["observations"][0]["clock_evidence"]["basis"] == (
        "same_source_relative_interval"
    )
    json.dumps(report, sort_keys=True)


def test_live_projection_matches_replay_measurement_before_clock_annotation() -> None:
    config = PROJECT_ROOT / "examples" / "labeler_demo_config.json"
    events = load_events(PROJECT_ROOT / "examples" / "labeler_demo_events.jsonl")
    bindings = load_condition_signal_bindings(
        PROJECT_ROOT / "examples" / "condition_signal_bindings.json"
    )
    replay_projection = condition_signal_projection_to_dict(
        project_replay_condition_signals(
            replay_events(build_core_from_config(config), events),
            bindings,
        )
    )

    consumer = LiveConditionConsumer(build_core_from_config(config), bindings)
    consumer.consume_all(
        DeterministicStreamSimulator(
            events=events,
            session_id="labeler-live-session-2",
            ingestion_delay_seconds=0.05,
            clock_quality="synchronized",
        )
    )
    live_projection = live_condition_summary_to_dict(consumer.summary())["condition_signals"]
    for observation in live_projection["observations"]:
        observation.pop("clock_evidence")

    assert live_projection == replay_projection


def _cross_source_core() -> LineAlertCore:
    return LineAlertCore(
        rules=[
            TemporalRule(
                rule_id="cross-source-delay",
                start_event="StartObserved",
                end_event="EndObserved",
                min_delay_seconds=0.1,
                max_delay_seconds=1.0,
                topology_from="StartObserved",
                topology_to="EndObserved",
            )
        ],
        topology=TopologyGraph([DependencyEdge("StartObserved", "EndObserved")]),
    )


def _event(
    event_id: str,
    event_type: str,
    source_id: str,
    milliseconds: int,
) -> MachineEvent:
    return MachineEvent(
        event_id=event_id,
        source_id=source_id,
        asset_id="LAB-01",
        component_id="station",
        event_type=event_type,
        timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
        + timedelta(milliseconds=milliseconds),
        correlation_id="cycle-1",
    )


def _envelope(
    event: MachineEvent,
    *,
    clock_quality: str,
) -> StreamEnvelope:
    return StreamEnvelope(
        session_id=f"session-{event.source_id}",
        sequence_number=0,
        received_at=event.timestamp + timedelta(milliseconds=10),
        event=event,
        clock_quality=clock_quality,
    )


def test_cross_source_unsynchronized_interval_is_retained_but_not_promoted() -> None:
    binding = TimingConditionBinding(
        signal_name="cross_source_delay_ms",
        rule_id="cross-source-delay",
        semantic="measured_cross_source_delay",
        scope="live_measurement_candidate",
        unit="ms",
    )
    consumer = LiveConditionConsumer(_cross_source_core(), (binding,))
    start = _event("start-1", "StartObserved", "source-a", 0)
    end = _event("end-1", "EndObserved", "source-b", 500)

    consumer.consume(_envelope(start, clock_quality="unsynchronized"))
    result = consumer.consume(_envelope(end, clock_quality="unknown"))

    assert result.measurements == ()
    assert len(result.refusals) == 1
    refusal = result.refusals[0]
    assert refusal.reason_code == "EVIDENCE.RELATIONSHIP_CROSS_SOURCE_CLOCK_UNQUALIFIED"
    assert refusal.start_clock_quality == "unsynchronized"
    assert refusal.end_clock_quality == "unknown"
    assert consumer.summary().stream_summary.timing_finding_count == 1
    assert consumer.summary().measurement_count == 0


def test_cross_source_synchronized_interval_can_be_projected() -> None:
    binding = TimingConditionBinding(
        signal_name="cross_source_delay_ms",
        rule_id="cross-source-delay",
        semantic="measured_cross_source_delay",
        scope="live_measurement_candidate",
        unit="ms",
    )
    consumer = LiveConditionConsumer(_cross_source_core(), (binding,))
    start = _event("start-2", "StartObserved", "source-a", 0)
    end = _event("end-2", "EndObserved", "source-b", 500)

    consumer.consume(_envelope(start, clock_quality="synchronized"))
    result = consumer.consume(_envelope(end, clock_quality="synchronized"))

    assert len(result.measurements) == 1
    assert result.refusals == ()
    measurement = result.measurements[0]
    assert measurement.observation.value == 500.0
    assert measurement.clock_evidence.basis == "synchronized_cross_source_interval"
