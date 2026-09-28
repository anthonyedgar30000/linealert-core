from __future__ import annotations

import copy
import json
import threading
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from linealert_core.clock_evidence import (
    ClockEvidenceError,
    ClockObservation,
    IntervalDisposition,
    assess_clock_drift,
    assess_cross_clock_interval,
)
from linealert_core.condition_projection import (
    ConditionProjectionError,
    TimingConditionBinding,
    project_replay_condition_signals,
)
from linealert_core.events import MachineEvent
from linealert_core.historian import TimescaleHistorian
from linealert_core.historian_service import measurement_from_payload
from linealert_core.live_condition import LiveConditionConsumer, live_condition_summary_to_dict
from linealert_core.pipeline import LineAlertCore
from linealert_core.replay import ReplaySummary
from linealert_core.streaming import StreamEnvelope, StreamInputError
from linealert_core.timing import TemporalRule
from linealert_core.topology import DependencyEdge, TopologyGraph

BASE = datetime(2026, 9, 28, 19, tzinfo=UTC)


def observation(
    event: MachineEvent,
    *,
    offset_ms: float,
    uncertainty_ms: float,
    reference: str = "reference-1",
) -> ClockObservation:
    return ClockObservation(
        event_id=event.event_id,
        source_id=event.source_id,
        clock_id=f"clock-{event.source_id}",
        reference_clock_id=reference,
        source_timestamp=event.timestamp,
        observed_at_reference=event.timestamp - timedelta(milliseconds=offset_ms),
        offset_ms=offset_ms,
        uncertainty_ms=uncertainty_ms,
        measurement_method="bounded_lab_reference_comparison",
        evidence_id=f"clock-sample-{event.event_id}",
    )


def event(event_id: str, source_id: str, event_type: str, ms: int) -> MachineEvent:
    return MachineEvent(
        event_id=event_id,
        source_id=source_id,
        asset_id="LAB-01",
        component_id="test-station",
        event_type=event_type,
        timestamp=BASE + timedelta(milliseconds=ms),
        correlation_id="cycle-1",
    )


def consumer() -> LiveConditionConsumer:
    core = LineAlertCore(
        rules=[
            TemporalRule(
                rule_id="delay",
                start_event="Start",
                end_event="End",
                min_delay_seconds=0.1,
                max_delay_seconds=0.6,
                topology_from="Start",
                topology_to="End",
            )
        ],
        topology=TopologyGraph([DependencyEdge("Start", "End")]),
    )
    return LiveConditionConsumer(
        core,
        (
            TimingConditionBinding(
                signal_name="delay_ms",
                rule_id="delay",
                semantic="test_delay",
                scope="lab",
                max_combined_uncertainty_ms=20,
            ),
        ),
    )


def envelope(e: MachineEvent, clock: ClockObservation | None) -> StreamEnvelope:
    return StreamEnvelope(
        session_id=f"session-{e.source_id}",
        sequence_number=0,
        received_at=e.timestamp + timedelta(milliseconds=30),
        event=e,
        clock_quality="synchronized",
        clock_observation=clock,
    )


def test_cross_clock_interval_uses_signed_offsets_and_conservative_sum() -> None:
    start = event("start", "plc", "Start", 0)
    end = event("end", "scada", "End", 135)
    assessment = assess_cross_clock_interval(
        start=observation(start, offset_ms=10, uncertainty_ms=12),
        end=observation(end, offset_ms=-5, uncertainty_ms=18),
        raw_delay_ms=135,
        min_delay_ms=100,
        max_delay_ms=600,
        max_combined_uncertainty_ms=40,
    )
    assert assessment.estimated_delay_ms == 150
    assert (assessment.lower_delay_ms, assessment.upper_delay_ms) == (120, 180)
    assert assessment.disposition is IntervalDisposition.WITHIN


def test_cross_source_admission_requires_numeric_evidence_under_declared_limit() -> None:
    start = event("start", "plc", "Start", 0)
    end = event("end", "scada", "End", 300)
    c = consumer()
    c.consume(envelope(start, observation(start, offset_ms=2, uncertainty_ms=4)))
    result = c.consume(envelope(end, observation(end, offset_ms=-3, uncertainty_ms=5)))
    assert len(result.measurements) == 1
    assessment = result.measurements[0].clock_evidence.interval_assessment
    assert assessment is not None and assessment.disposition is IntervalDisposition.WITHIN
    report = live_condition_summary_to_dict(c.summary())
    retained = report["condition_signals"]["observations"][0]["clock_evidence"]
    assert retained["interval_assessment"]["combined_uncertainty_ms"] == 9
    assert retained["interval_assessment"]["start_evidence_id"] == "clock-sample-start"
    rebuilt = measurement_from_payload(report["condition_signals"]["observations"][0])
    assert rebuilt.clock_evidence.interval_assessment == assessment
    historian = object.__new__(TimescaleHistorian)
    historian._lock = threading.RLock()
    historian._connection = MagicMock()
    historian.record_condition_measurement(
        rebuilt, episode_id="lab-episode", source_mode="synthetic"
    )
    cursor = historian._connection.cursor.return_value.__enter__.return_value
    retained_json = json.loads(cursor.execute.call_args.args[1][-1])
    assert retained_json["interval_assessment"]["start_observation"]["clock_id"] == "clock-plc"
    assert retained_json["interval_assessment"]["end_observation"]["offset_ms"] == -3
    tampered = copy.deepcopy(report["condition_signals"]["observations"][0])
    tampered["clock_evidence"]["interval_assessment"]["lower_delay_ms"] = -100
    with pytest.raises(ValueError, match="invalid condition clock"):
        measurement_from_payload(tampered)


@pytest.mark.parametrize(
    "offset,uncertainty,reason",
    [
        (0, 0, "EVIDENCE.RELATIONSHIP_CLOCK_OBSERVATION_MISSING"),
        (0, 25, "EVIDENCE.RELATIONSHIP_TEMPORAL_UNCERTAINTY"),
        (0, 12, "EVIDENCE.RELATIONSHIP_TEMPORAL_UNCERTAINTY"),
    ],
)
def test_cross_source_refuses_missing_excessive_or_boundary_overlapping_evidence(
    offset: int,
    uncertainty: int,
    reason: str,
) -> None:
    start = event("start", "plc", "Start", 0)
    end = event("end", "scada", "End", 105)
    c = consumer()
    c.consume(envelope(start, observation(start, offset_ms=0, uncertainty_ms=0)))
    end_clock = (
        None
        if reason.endswith("MISSING")
        else observation(end, offset_ms=offset, uncertainty_ms=uncertainty)
    )
    result = c.consume(envelope(end, end_clock))
    assert result.measurements == ()
    assert result.refusals[0].reason_code == reason
    assert c.summary().stream_summary.timing_finding_count == 1


def test_different_reference_or_changed_raw_classification_refuses() -> None:
    start = event("start", "plc", "Start", 0)
    end = event("end", "scada", "End", 120)
    c = consumer()
    c.consume(envelope(start, observation(start, offset_ms=0, uncertainty_ms=2)))
    result = c.consume(
        envelope(end, observation(end, offset_ms=0, uncertainty_ms=2, reference="reference-2"))
    )
    assert result.refusals[0].reason_code == "EVIDENCE.RELATIONSHIP_CLOCK_REFERENCE_MISMATCH"

    c = consumer()
    c.consume(envelope(start, observation(start, offset_ms=0, uncertainty_ms=2)))
    result = c.consume(envelope(end, observation(end, offset_ms=50, uncertainty_ms=2)))
    assert result.refusals[0].reason_code == "EVIDENCE.RELATIONSHIP_TEMPORAL_UNCERTAINTY"


def test_clock_observation_cannot_be_attached_to_another_event() -> None:
    start = event("start", "plc", "Start", 0)
    other = event("other", "plc", "Start", 0)
    with pytest.raises(StreamInputError, match="exact event"):
        envelope(other, observation(start, offset_ms=0, uncertainty_ms=1))


def test_replay_cannot_satisfy_quantified_live_clock_requirement() -> None:
    with pytest.raises(ConditionProjectionError, match="unqualified replay"):
        project_replay_condition_signals(
            ReplaySummary(results=(), machine_profile=None, topology_edges=()),
            consumer().summary().bindings,
        )


def test_sustained_resolved_offset_slope_is_only_a_drift_candidate() -> None:
    samples = tuple(
        observation(
            event(f"sample-{i}", "plc", "Start", i * 1000),
            offset_ms=i * 0.02,
            uncertainty_ms=0.001,
        )
        for i in range(4)
    )
    trend = assess_clock_drift(samples, minimum_rate_ppm=10)
    assert trend.disposition == "DRIFT_CANDIDATE"
    assert trend.rate_ppm == pytest.approx(20, abs=0.01)
    assert len(trend.evidence_ids) == 4

    unresolved = tuple(
        observation(
            event(f"noisy-{i}", "plc", "Start", i * 1000),
            offset_ms=i * 0.02,
            uncertainty_ms=0.05,
        )
        for i in range(4)
    )
    assert assess_clock_drift(unresolved, minimum_rate_ppm=10).disposition == "INDETERMINATE"
    stepped = tuple(
        observation(
            event(f"step-{i}", "plc", "Start", i * 1000),
            offset_ms=(0, 0, 200, 200)[i],
            uncertainty_ms=0.1,
        )
        for i in range(4)
    )
    step = assess_clock_drift(stepped, minimum_rate_ppm=10)
    assert step.disposition == "STEP_CANDIDATE"
    assert step.rate_ppm is None
    with pytest.raises(ClockEvidenceError, match="one clock"):
        assess_clock_drift(
            samples[:2]
            + (
                observation(
                    event("other", "scada", "Start", 3000),
                    offset_ms=1,
                    uncertainty_ms=0.001,
                ),
            ),
            minimum_rate_ppm=10,
        )
