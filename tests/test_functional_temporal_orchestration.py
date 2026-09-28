from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from linealert_core import (
    DeterministicStreamSimulator,
    LiveConditionConsumer,
    build_core_from_config,
    load_condition_signal_bindings,
    load_events,
)
from linealert_core.functional_temporal import (
    EpistemicState,
    FunctionalTemporalModel,
    GuardDefinition,
    InvariantDefinition,
    PhaseDefinition,
    TemporalCoverage,
    TransitionDefinition,
    TransitionDisposition,
)
from linealert_core.functional_temporal_orchestration import (
    FunctionalTemporalOrchestrationError,
    FunctionalTemporalOrchestrator,
    OrchestrationDisposition,
)
from linealert_core.functional_temporal_runtime import FunctionalTemporalRuntime
from linealert_core.functional_temporal_source_binding import (
    FunctionalTemporalEvidenceBinder,
    load_functional_temporal_source_bindings,
)
from linealert_core.historian import (
    FunctionalTemporalHistoryRecord,
    FunctionalTemporalRecordKind,
    HistorianOperatingContext,
)
from linealert_core.live_condition import LiveConditionResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RecordingSink:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.batches: list[tuple[FunctionalTemporalHistoryRecord, ...]] = []

    def record_functional_temporal_evidence_batch(
        self,
        records: tuple[FunctionalTemporalHistoryRecord, ...],
    ) -> tuple[dict[str, object], ...]:
        if self.fail:
            raise RuntimeError("historian unavailable")
        self.batches.append(records)
        return tuple({"record_id": record.record_id} for record in records)


def model(*, with_entry_invariant: bool = False) -> FunctionalTemporalModel:
    return FunctionalTemporalModel(
        phases=(
            PhaseDefinition(
                "BEFORE_LABEL_PRESENTATION",
                "Before label presentation",
                "label-feed-servo",
                invariant_ids=("INV_BOTTLE_EVENT",) if with_entry_invariant else (),
            ),
            PhaseDefinition(
                "LABEL_PRESENTED",
                "Label presented",
                "label-present-sensor",
            ),
        ),
        transitions=(
            TransitionDefinition(
                "LABEL_PRESENTATION",
                "BEFORE_LABEL_PRESENTATION",
                "LABEL_PRESENTED",
                "LabelAtPeelPoint",
                ("GUARD_LABEL_PRESENTATION_TIMING",),
            ),
        ),
        guards=(
            GuardDefinition(
                "GUARD_LABEL_PRESENTATION_TIMING",
                ("label_presentation_timing_within_envelope",),
                TemporalCoverage.POINT_ONLY,
            ),
        ),
        invariants=(
            InvariantDefinition(
                "INV_BOTTLE_EVENT",
                ("bottle_detected_event_observed",),
                TemporalCoverage.POINT_ONLY,
            ),
        )
        if with_entry_invariant
        else (),
    )


def context() -> HistorianOperatingContext:
    return HistorianOperatingContext(
        asset_id="LABELER-DEMO-01",
        component_id="functional-temporal-orchestrator",
        profile_id="generic-pressure-sensitive-labeler-demo-v1",
        operating_mode="500ml-round-bottle",
        configuration_version="synthetic-labeler-config-v1",
        firmware_version="synthetic-controller-fw-v1",
        calibration_id="synthetic-calibration-v1",
        sampling_profile_id="event-stream-source-timestamps-v1",
        recipe_id="500ml-round-bottle",
        product_id="synthetic-500ml-bottle",
        context_tags={"environment": "synthetic-demo"},
    )


def binder() -> FunctionalTemporalEvidenceBinder:
    return FunctionalTemporalEvidenceBinder(
        load_functional_temporal_source_bindings(
            PROJECT_ROOT / "examples" / "labeler_functional_temporal_source_bindings.json"
        )
    )


def orchestrator(
    sink: RecordingSink,
    *,
    with_entry_invariant: bool = False,
) -> FunctionalTemporalOrchestrator:
    return FunctionalTemporalOrchestrator(
        binder=binder(),
        runtime=FunctionalTemporalRuntime(
            model(with_entry_invariant=with_entry_invariant),
            initial_phase_id="BEFORE_LABEL_PRESENTATION",
        ),
        historian=sink,
    )


def live_results(path: str, *, count: int | None = None) -> list[LiveConditionResult]:
    events = list(load_events(PROJECT_ROOT / "examples" / path))
    if count is not None:
        events = events[:count]
    consumer = LiveConditionConsumer(
        build_core_from_config(PROJECT_ROOT / "examples" / "labeler_demo_config.json"),
        load_condition_signal_bindings(
            PROJECT_ROOT / "examples" / "condition_signal_bindings.json"
        ),
    )
    results: list[LiveConditionResult] = []
    for envelope in DeterministicStreamSimulator(
        events=events,
        session_id=f"orchestration-{path}",
        ingestion_delay_seconds=0,
        clock_quality="synchronized",
    ):
        results.append(consumer.consume(envelope))
    return results


def test_same_live_result_binds_completed_measurement_before_transition_evaluation() -> None:
    sink = RecordingSink()
    service = orchestrator(sink)
    results = live_results("labeler_condition_drift_events.jsonl", count=2)

    first = service.process_live_result(
        results[0], episode_id="episode-drift-2001", operating_context=context()
    )
    second = service.process_live_result(
        results[1], episode_id="episode-drift-2001", operating_context=context()
    )

    assert first.runtime_result is not None
    assert first.runtime_result.transition.disposition is TransitionDisposition.NOT_TRIGGERED
    assert first.persisted_record_ids == ()
    assert second.runtime_result is not None
    assert second.runtime_result.transition.disposition is TransitionDisposition.ADMITTED
    assert second.runtime_result.current_phase_id == "LABEL_PRESENTED"
    assert second.source_projection is not None
    evidence = second.source_projection.evidence_map()
    assert evidence["label_presentation_timing_within_envelope"].state is EpistemicState.VERIFIED
    assert [record.record_kind for record in sink.batches[0]] == [
        FunctionalTemporalRecordKind.GUARD,
        FunctionalTemporalRecordKind.TRANSITION,
        FunctionalTemporalRecordKind.PHASE,
    ]


def test_existing_550ms_demo_relationship_rejects_transition_without_diagnosis() -> None:
    sink = RecordingSink()
    service = orchestrator(sink)
    results = live_results("labeler_demo_events.jsonl")

    final = None
    for result in results:
        final = service.process_live_result(
            result,
            episode_id="episode-demo-1001",
            operating_context=context(),
        )

    assert final is not None and final.runtime_result is not None
    assert final.runtime_result.transition.disposition is TransitionDisposition.NOT_TRIGGERED
    # Re-run only to capture the LabelAtPeelPoint orchestration result cleanly.
    sink2 = RecordingSink()
    service2 = orchestrator(sink2)
    label_orchestration = None
    for result in results:
        current = service2.process_live_result(
            result,
            episode_id="episode-demo-1001",
            operating_context=context(),
        )
        if result.stream_result.envelope.event.event_type == "LabelAtPeelPoint":
            label_orchestration = current
    assert label_orchestration is not None
    assert label_orchestration.runtime_result is not None
    assert (
        label_orchestration.runtime_result.transition.disposition is TransitionDisposition.REJECTED
    )
    assert label_orchestration.runtime_result.current_phase_id == "BEFORE_LABEL_PRESENTATION"
    assert not any(
        record.details.get("record_semantic") == "phase_admission" for record in sink2.batches[0]
    )
    guard = sink2.batches[0][0]
    assert guard.state is EpistemicState.VIOLATED
    backing = guard.details["backing_evidence"]["label_presentation_timing_within_envelope"]
    assert backing["reason_code"] == "EVIDENCE.RELATIONSHIP_OUTSIDE_ENVELOPE"
    assert "physical root cause" in backing["retained_uncertainty"]


def test_candidate_transition_assesses_current_phase_invariant_before_transition() -> None:
    sink = RecordingSink()
    service = orchestrator(sink, with_entry_invariant=True)
    results = live_results("labeler_demo_events.jsonl")

    label_result = None
    for result in results:
        current = service.process_live_result(
            result,
            episode_id="episode-demo-1001",
            operating_context=context(),
        )
        if result.stream_result.envelope.event.event_type == "LabelAtPeelPoint":
            label_result = current

    assert label_result is not None
    assert label_result.phase_assessment is not None
    assert label_result.phase_assessment.phase_id == "BEFORE_LABEL_PRESENTATION"
    assert label_result.phase_assessment.evaluation.state is EpistemicState.VERIFIED
    batch = next(batch for batch in sink.batches if len(batch) == 4)
    assert [record.record_kind for record in batch] == [
        FunctionalTemporalRecordKind.INVARIANT,
        FunctionalTemporalRecordKind.PHASE,
        FunctionalTemporalRecordKind.GUARD,
        FunctionalTemporalRecordKind.TRANSITION,
    ]


def test_persistence_failure_rolls_back_runtime_and_cycle_evidence_for_retry() -> None:
    sink = RecordingSink(fail=True)
    service = orchestrator(sink)
    results = live_results("labeler_condition_drift_events.jsonl", count=2)
    service.process_live_result(
        results[0], episode_id="episode-drift-2001", operating_context=context()
    )

    with pytest.raises(FunctionalTemporalOrchestrationError, match="orchestration failed"):
        service.process_live_result(
            results[1],
            episode_id="episode-drift-2001",
            operating_context=context(),
        )

    assert service.runtime.current_phase("drift-cycle-2001") == "BEFORE_LABEL_PRESENTATION"
    assert "label_presentation_timing_within_envelope" not in service.cycle_evidence(
        "drift-cycle-2001"
    )

    sink.fail = False
    retried = service.process_live_result(
        results[1], episode_id="episode-drift-2001", operating_context=context()
    )
    assert retried.runtime_result is not None
    assert retried.runtime_result.transition.disposition is TransitionDisposition.ADMITTED
    assert service.runtime.current_phase("drift-cycle-2001") == "LABEL_PRESENTED"
    assert len(sink.batches) == 1


def test_duplicate_event_is_skipped_without_reapplying_phase_state() -> None:
    sink = RecordingSink()
    service = orchestrator(sink)
    events = list(load_events(PROJECT_ROOT / "examples" / "labeler_condition_drift_events.jsonl"))[
        :2
    ]
    consumer = LiveConditionConsumer(
        build_core_from_config(PROJECT_ROOT / "examples" / "labeler_demo_config.json"),
        load_condition_signal_bindings(
            PROJECT_ROOT / "examples" / "condition_signal_bindings.json"
        ),
    )
    simulator = list(
        DeterministicStreamSimulator(
            events=events,
            session_id="duplicate-test",
            ingestion_delay_seconds=0,
            clock_quality="synchronized",
        )
    )
    first = consumer.consume(simulator[0])
    second = consumer.consume(simulator[1])
    service.process_live_result(first, episode_id="episode", operating_context=context())
    service.process_live_result(second, episode_id="episode", operating_context=context())

    duplicate_envelope = simulator[1]
    duplicate_envelope = type(duplicate_envelope)(
        session_id=duplicate_envelope.session_id,
        sequence_number=2,
        received_at=duplicate_envelope.received_at,
        event=duplicate_envelope.event,
        clock_quality=duplicate_envelope.clock_quality,
        transport_attributes=duplicate_envelope.transport_attributes,
    )
    duplicate = consumer.consume(duplicate_envelope)
    result = service.process_live_result(
        duplicate, episode_id="episode", operating_context=context()
    )

    assert result.disposition is OrchestrationDisposition.SKIPPED_DUPLICATE_EVENT
    assert result.persisted_record_ids == ()
    assert len(sink.batches) == 1


def test_rejected_transport_is_skipped_without_evidence_or_runtime_mutation() -> None:
    sink = RecordingSink()
    service = orchestrator(sink)
    event = load_events(PROJECT_ROOT / "examples" / "labeler_demo_events.jsonl")[0]
    from linealert_core.streaming import StreamEnvelope

    consumer = LiveConditionConsumer(
        build_core_from_config(PROJECT_ROOT / "examples" / "labeler_demo_config.json"),
        load_condition_signal_bindings(
            PROJECT_ROOT / "examples" / "condition_signal_bindings.json"
        ),
    )
    bad = consumer.consume(
        StreamEnvelope(
            session_id="gap-test",
            sequence_number=3,
            received_at=datetime(2026, 9, 28, 4, 0, tzinfo=UTC),
            event=event,
            clock_quality="synchronized",
        )
    )

    result = service.process_live_result(bad, episode_id="episode", operating_context=context())

    assert result.disposition is OrchestrationDisposition.SKIPPED_TRANSPORT_REJECTED
    assert service.cycle_evidence(event.correlation_id) == {}
    assert sink.batches == []


def test_explicit_cycle_assessment_persists_invariant_records_atomically() -> None:
    sink = RecordingSink()
    service = orchestrator(sink, with_entry_invariant=True)
    bottle_result = live_results("labeler_demo_events.jsonl", count=1)[0]
    service.process_live_result(
        bottle_result,
        episode_id="episode-demo-1001",
        operating_context=context(),
    )

    assessment = service.assess_cycle(
        episode_id="episode-demo-1001",
        cycle_id="cycle-1001",
        observed_at=bottle_result.stream_result.envelope.event.timestamp,
        operating_context=context(),
        clock_evidence={"basis": "explicit_test_assessment"},
    )

    assert assessment.evaluation.state is EpistemicState.VERIFIED
    assert [record.record_kind for record in sink.batches[0]] == [
        FunctionalTemporalRecordKind.INVARIANT,
        FunctionalTemporalRecordKind.PHASE,
    ]
    assert sink.batches[0][0].clock_evidence["basis"] == "explicit_test_assessment"


def test_orchestration_types_are_exported_from_public_api() -> None:
    import linealert_core

    assert linealert_core.FunctionalTemporalOrchestrator is FunctionalTemporalOrchestrator
    assert (
        linealert_core.FunctionalTemporalOrchestrationError is FunctionalTemporalOrchestrationError
    )
    assert linealert_core.OrchestrationDisposition is OrchestrationDisposition
