from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from linealert_core import (
    DeterministicStreamSimulator,
    LiveConditionConsumer,
    build_core_from_config,
    load_condition_signal_bindings,
    load_events,
)
from linealert_core.condition_projection import (
    TimingConditionBinding,
    project_timing_finding,
)
from linealert_core.events import EventQuality, MachineEvent
from linealert_core.functional_temporal import (
    EpistemicState,
    EvidenceValidity,
    FunctionalTemporalEvaluator,
    FunctionalTemporalModel,
    GuardDefinition,
    PhaseDefinition,
    TemporalCoverage,
    TransitionDefinition,
    TransitionDisposition,
)
from linealert_core.functional_temporal_source_binding import (
    EventEvidenceBinding,
    EvidenceSourceClassification,
    FunctionalTemporalEvidenceBinder,
    FunctionalTemporalSourceBindingError,
    TimingRelationshipEvidenceBinding,
    load_functional_temporal_source_bindings,
)
from linealert_core.live_condition import LiveClockEvidence, LiveConditionMeasurement
from linealert_core.timing import TimingFinding, TimingStatus

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TIME = datetime(2026, 9, 14, 15, 42, tzinfo=UTC)


def event_binding() -> EventEvidenceBinding:
    return EventEvidenceBinding(
        binding_id="event:bottle-detected",
        evidence_key="bottle_detected_event_observed",
        event_type="BottleDetected",
        component_id="infeed-photoeye",
        source_id="plc-labeler-demo",
        semantic=(
            "BottleDetected source event observed; this does not independently "
            "prove physical bottle presence."
        ),
    )


def relationship_binding() -> TimingRelationshipEvidenceBinding:
    return TimingRelationshipEvidenceBinding(
        binding_id="relationship:label-presentation",
        evidence_key="label_presentation_timing_within_envelope",
        relationship_id="relationship:label-presentation-delay",
        rule_id="label-presentation-delay",
        signal_name="label_presentation_delay_ms",
        semantic="measured_label_feed_command_to_label_at_peel_point_delay",
        scope="replay_measurement_candidate",
        unit="ms",
        start_source_id="plc-labeler-demo",
        end_source_id="plc-labeler-demo",
    )


def machine_event(
    *,
    quality: EventQuality = EventQuality.GOOD,
    source_id: str = "plc-labeler-demo",
    correlation_id: str = "cycle-42",
) -> MachineEvent:
    return MachineEvent(
        event_id="evt-bottle-detected-42",
        source_id=source_id,
        asset_id="LABELER-DEMO-01",
        component_id="infeed-photoeye",
        event_type="BottleDetected",
        timestamp=BASE_TIME,
        correlation_id=correlation_id,
        quality=quality,
        attributes={"operating_mode": "500ml-round-bottle"},
    )


def measurement(
    *,
    status: TimingStatus = TimingStatus.WITHIN,
    start_quality: EventQuality = EventQuality.GOOD,
    end_quality: EventQuality = EventQuality.GOOD,
    clock_basis: str = "same_source_relative_interval",
    start_source_id: str = "plc-labeler-demo",
    end_source_id: str = "plc-labeler-demo",
) -> LiveConditionMeasurement:
    finding = TimingFinding(
        rule_id="label-presentation-delay",
        asset_id="LABELER-DEMO-01",
        correlation_id="cycle-42",
        start_timestamp=BASE_TIME,
        end_timestamp=BASE_TIME + timedelta(milliseconds=155),
        delay_seconds=0.155 if status is TimingStatus.WITHIN else 0.55,
        min_delay_seconds=0.05,
        max_delay_seconds=0.35,
        status=status,
        topology_from="LabelFeedCommand",
        topology_to="LabelAtPeelPoint",
        start_event_id="evt-feed-command-42",
        end_event_id="evt-peel-42",
        start_source_id=start_source_id,
        end_source_id=end_source_id,
        start_quality=start_quality,
        end_quality=end_quality,
    )
    binding = TimingConditionBinding(
        signal_name="label_presentation_delay_ms",
        rule_id="label-presentation-delay",
        semantic="measured_label_feed_command_to_label_at_peel_point_delay",
        scope="replay_measurement_candidate",
        unit="ms",
    )
    return LiveConditionMeasurement(
        observation=project_timing_finding(finding, binding),
        clock_evidence=LiveClockEvidence(
            start_clock_quality="synchronized",
            end_clock_quality="synchronized",
            basis=clock_basis,
            retained_uncertainty="test clock evidence",
        ),
    )


def test_good_event_projects_occurrence_only_verified_point_evidence() -> None:
    binder = FunctionalTemporalEvidenceBinder((event_binding(),))

    projection = binder.project_event(machine_event(), cycle_id="cycle-42")

    assert projection.refusals == ()
    assert len(projection.observations) == 1
    bound = projection.observations[0]
    evidence = bound.observation
    assert bound.source_classification is EvidenceSourceClassification.MACHINE_EVENT_OCCURRENCE
    assert evidence.state is EpistemicState.VERIFIED
    assert evidence.validity is EvidenceValidity.CURRENT
    assert evidence.coverage is TemporalCoverage.POINT_ONLY
    assert evidence.source_id == "plc-labeler-demo"
    assert evidence.cycle_id == "cycle-42"
    assert evidence.reason_code == "EVIDENCE.EVENT_OCCURRENCE_OBSERVED"
    assert "does not independently prove" in bound.claim_boundary
    assert evidence.semantic == event_binding().semantic
    assert evidence.provenance["event_id"] == "evt-bottle-detected-42"
    assert evidence.provenance["event_source_id"] == "plc-labeler-demo"
    assert evidence.provenance["event_fingerprint"] == machine_event().fingerprint
    with pytest.raises(TypeError):
        evidence.provenance["event_id"] = "changed"  # type: ignore[index]


def test_suspect_event_remains_unresolved_not_verified() -> None:
    binder = FunctionalTemporalEvidenceBinder((event_binding(),))

    projection = binder.project_event(
        machine_event(quality=EventQuality.SUSPECT),
        cycle_id="cycle-42",
    )

    evidence = projection.observations[0].observation
    assert evidence.state is EpistemicState.UNRESOLVED
    assert evidence.reason_code == "EVIDENCE.EVENT_INPUT_SUSPECT"


def test_wrong_event_source_is_refused_without_admitting_evidence() -> None:
    binder = FunctionalTemporalEvidenceBinder((event_binding(),))

    projection = binder.project_event(
        machine_event(source_id="unexpected-source"),
        cycle_id="cycle-42",
    )

    assert projection.observations == ()
    assert projection.refusals[0].reason_code == "EVIDENCE.EVENT_SOURCE_MISMATCH"


def test_event_cycle_mismatch_is_refused() -> None:
    binder = FunctionalTemporalEvidenceBinder((event_binding(),))
    projection = binder.project_event(machine_event(), cycle_id="cycle-99")

    assert projection.observations == ()
    assert projection.refusals[0].reason_code == "EVIDENCE.EVENT_CYCLE_MISMATCH"


def test_within_timing_relationship_projects_verified_point_evidence() -> None:
    binder = FunctionalTemporalEvidenceBinder((relationship_binding(),))

    projection = binder.project_measurement(measurement(), cycle_id="cycle-42")

    bound = projection.observations[0]
    evidence = bound.observation
    assert projection.refusals == ()
    assert bound.source_classification is (
        EvidenceSourceClassification.CLOCK_QUALIFIED_TIMING_RELATIONSHIP
    )
    assert evidence.state is EpistemicState.VERIFIED
    assert evidence.coverage is TemporalCoverage.POINT_ONLY
    assert evidence.reason_code == "EVIDENCE.RELATIONSHIP_WITHIN_ENVELOPE"
    assert "does not prove physical" in bound.claim_boundary
    assert evidence.provenance["start_source_id"] == "plc-labeler-demo"
    assert evidence.provenance["end_source_id"] == "plc-labeler-demo"
    assert evidence.provenance["clock_basis"] == "same_source_relative_interval"
    assert evidence.provenance["value"] == "155.0"
    assert evidence.provenance["unit"] == "ms"
    assert evidence.provenance["min_value"] == "50.0"
    assert evidence.provenance["max_value"] == "350.0"
    assert evidence.provenance["temporal_rule_status"] == "within"


def test_late_timing_relationship_projects_violation_not_root_cause() -> None:
    binder = FunctionalTemporalEvidenceBinder((relationship_binding(),))

    projection = binder.project_measurement(
        measurement(status=TimingStatus.LATE),
        cycle_id="cycle-42",
    )

    evidence = projection.observations[0].observation
    assert evidence.state is EpistemicState.VIOLATED
    assert evidence.reason_code == "EVIDENCE.RELATIONSHIP_OUTSIDE_ENVELOPE"
    assert "physical root cause" in evidence.retained_uncertainty


def test_suspect_relationship_input_is_unresolved_even_when_status_within() -> None:
    binder = FunctionalTemporalEvidenceBinder((relationship_binding(),))

    projection = binder.project_measurement(
        measurement(end_quality=EventQuality.SUSPECT),
        cycle_id="cycle-42",
    )

    evidence = projection.observations[0].observation
    assert evidence.state is EpistemicState.UNRESOLVED
    assert evidence.reason_code == "EVIDENCE.RELATIONSHIP_INPUT_SUSPECT"


def test_unqualified_clock_basis_cannot_verify_relationship() -> None:
    binder = FunctionalTemporalEvidenceBinder((relationship_binding(),))

    projection = binder.project_measurement(
        measurement(clock_basis="unknown"),
        cycle_id="cycle-42",
    )

    evidence = projection.observations[0].observation
    assert evidence.state is EpistemicState.UNRESOLVED
    assert evidence.reason_code == "EVIDENCE.RELATIONSHIP_CLOCK_BASIS_UNQUALIFIED"


def test_relationship_source_identity_mismatch_is_refused() -> None:
    binder = FunctionalTemporalEvidenceBinder((relationship_binding(),))

    projection = binder.project_measurement(
        measurement(end_source_id="other-plc"),
        cycle_id="cycle-42",
    )

    assert projection.observations == ()
    assert projection.refusals[0].reason_code == ("EVIDENCE.RELATIONSHIP_END_SOURCE_MISMATCH")


def test_project_many_refuses_silent_latest_wins_for_same_evidence_key() -> None:
    binder = FunctionalTemporalEvidenceBinder((event_binding(),))
    first = machine_event()
    second = MachineEvent(
        event_id="evt-bottle-detected-42-second",
        source_id=first.source_id,
        asset_id=first.asset_id,
        component_id=first.component_id,
        event_type=first.event_type,
        timestamp=first.timestamp + timedelta(milliseconds=10),
        correlation_id=first.correlation_id,
        quality=first.quality,
        attributes=first.attributes,
    )

    with pytest.raises(
        FunctionalTemporalSourceBindingError,
        match="multiple distinct observations",
    ):
        binder.project_many(
            cycle_id="cycle-42",
            events=(first, second),
        )


def test_loader_reads_explicit_labeler_source_bindings() -> None:
    bindings = load_functional_temporal_source_bindings(
        PROJECT_ROOT / "examples" / "labeler_functional_temporal_source_bindings.json"
    )

    assert len(bindings) == 2
    assert isinstance(bindings[0], EventEvidenceBinding)
    assert isinstance(bindings[1], TimingRelationshipEvidenceBinding)
    assert bindings[0].source_id == "plc-labeler-demo"
    assert bindings[1].relationship_id == "relationship:label-presentation-delay"


def test_loader_rejects_duplicate_evidence_keys(tmp_path: Path) -> None:
    document = {
        "schema_version": "linealert.functional-temporal-source-bindings.v1",
        "bindings": [
            {
                "binding_id": "one",
                "source_kind": "machine_event_occurrence",
                "evidence_key": "same",
                "event_type": "A",
                "component_id": "component-a",
                "source_id": "source-a",
                "semantic": "event A observed",
            },
            {
                "binding_id": "two",
                "source_kind": "machine_event_occurrence",
                "evidence_key": "same",
                "event_type": "B",
                "component_id": "component-b",
                "source_id": "source-b",
                "semantic": "event B observed",
            },
        ],
    }
    path = tmp_path / "bindings.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(FunctionalTemporalSourceBindingError, match="evidence keys"):
        load_functional_temporal_source_bindings(path)


def test_all_v1_projected_source_evidence_is_point_only() -> None:
    binder = FunctionalTemporalEvidenceBinder((event_binding(), relationship_binding()))
    projection = binder.project_many(
        cycle_id="cycle-42",
        events=(machine_event(),),
        measurements=(measurement(),),
    )

    assert len(projection.observations) == 2
    assert all(
        item.observation.coverage is TemporalCoverage.POINT_ONLY for item in projection.observations
    )


def test_evidence_map_returns_exact_keys_without_mutability() -> None:
    binder = FunctionalTemporalEvidenceBinder((event_binding(), relationship_binding()))
    projection = binder.project_many(
        cycle_id="cycle-42",
        events=(machine_event(),),
        measurements=(measurement(),),
    )

    evidence = projection.evidence_map()
    assert set(evidence) == {
        "bottle_detected_event_observed",
        "label_presentation_timing_within_envelope",
    }
    with pytest.raises(TypeError):
        evidence["new"] = evidence["bottle_detected_event_observed"]  # type: ignore[index]


def _single_guard_model(evidence_key: str) -> FunctionalTemporalModel:
    return FunctionalTemporalModel(
        phases=(
            PhaseDefinition("BEFORE", "Before", "source"),
            PhaseDefinition("AFTER", "After", "target"),
        ),
        transitions=(
            TransitionDefinition(
                "BEFORE_TO_AFTER",
                "BEFORE",
                "AFTER",
                "Advance",
                ("GUARD_SOURCE",),
            ),
        ),
        guards=(
            GuardDefinition(
                "GUARD_SOURCE",
                (evidence_key,),
                TemporalCoverage.POINT_ONLY,
            ),
        ),
        invariants=(),
    )


def test_suspect_bound_event_reason_survives_guard_evaluation() -> None:
    binder = FunctionalTemporalEvidenceBinder((event_binding(),))
    projection = binder.project_event(
        machine_event(quality=EventQuality.SUSPECT),
        cycle_id="cycle-42",
    )
    evaluator = FunctionalTemporalEvaluator(_single_guard_model("bottle_detected_event_observed"))

    result = evaluator.evaluate_transition(
        "BEFORE",
        "Advance",
        projection.evidence_map(),
    )

    assert result.disposition is TransitionDisposition.UNRESOLVED
    assert result.guard_results[0].state is EpistemicState.UNRESOLVED
    assert result.guard_results[0].reasons == (
        "bottle_detected_event_observed source evidence: EVIDENCE.EVENT_INPUT_SUSPECT",
    )


def test_out_of_envelope_relationship_can_reject_relationship_guard_only() -> None:
    binder = FunctionalTemporalEvidenceBinder((relationship_binding(),))
    projection = binder.project_measurement(
        measurement(status=TimingStatus.LATE),
        cycle_id="cycle-42",
    )
    evaluator = FunctionalTemporalEvaluator(
        _single_guard_model("label_presentation_timing_within_envelope")
    )

    result = evaluator.evaluate_transition(
        "BEFORE",
        "Advance",
        projection.evidence_map(),
    )

    assert result.disposition is TransitionDisposition.REJECTED
    assert result.guard_results[0].state is EpistemicState.VIOLATED
    assert result.guard_results[0].reasons == (
        "label_presentation_timing_within_envelope source evidence: "
        "EVIDENCE.RELATIONSHIP_OUTSIDE_ENVELOPE",
    )
    evidence = projection.observations[0].observation
    assert "does not prove physical root cause" in evidence.retained_uncertainty


def test_source_binding_types_are_exported_from_public_api() -> None:
    import linealert_core

    assert linealert_core.FunctionalTemporalEvidenceBinder is FunctionalTemporalEvidenceBinder
    assert linealert_core.EventEvidenceBinding is EventEvidenceBinding
    assert linealert_core.TimingRelationshipEvidenceBinding is TimingRelationshipEvidenceBinding
    assert (
        linealert_core.load_functional_temporal_source_bindings
        is load_functional_temporal_source_bindings
    )


def test_example_bindings_match_existing_labeler_event_and_live_relationship() -> None:
    bindings = load_functional_temporal_source_bindings(
        PROJECT_ROOT / "examples" / "labeler_functional_temporal_source_bindings.json"
    )
    binder = FunctionalTemporalEvidenceBinder(bindings)
    events = load_events(PROJECT_ROOT / "examples" / "labeler_demo_events.jsonl")

    event_projection = binder.project_event(events[0], cycle_id="cycle-1001")
    assert event_projection.observations[0].observation.state is EpistemicState.VERIFIED

    consumer = LiveConditionConsumer(
        build_core_from_config(PROJECT_ROOT / "examples" / "labeler_demo_config.json"),
        load_condition_signal_bindings(
            PROJECT_ROOT / "examples" / "condition_signal_bindings.json"
        ),
    )
    emitted: list[LiveConditionMeasurement] = []
    for envelope in DeterministicStreamSimulator(
        events=events,
        session_id="source-binding-demo",
        ingestion_delay_seconds=0.0,
        clock_quality="synchronized",
    ):
        result = consumer.consume(envelope)
        emitted.extend(result.measurements)

    assert len(emitted) == 1
    timing_projection = binder.project_measurement(
        emitted[0],
        cycle_id="cycle-1001",
    )
    timing_evidence = timing_projection.observations[0].observation
    assert timing_evidence.state is EpistemicState.VIOLATED
    assert timing_evidence.reason_code == "EVIDENCE.RELATIONSHIP_OUTSIDE_ENVELOPE"
    assert timing_evidence.provenance["start_event_id"] == "labeler-cycle-1001-05"
    assert timing_evidence.provenance["end_event_id"] == "labeler-cycle-1001-06"
