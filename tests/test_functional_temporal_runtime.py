from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from linealert_core import (
    FunctionalTemporalRuntime,
    FunctionalTemporalRuntimeError,
)
from linealert_core.events import EventQuality, MachineEvent
from linealert_core.functional_temporal import (
    EpistemicState,
    EvidenceObservation,
    EvidenceValidity,
    FunctionalTemporalModel,
    GuardDefinition,
    InvariantDefinition,
    PhaseDefinition,
    TemporalCoverage,
    TransitionDefinition,
    TransitionDisposition,
)
from linealert_core.historian import (
    FunctionalTemporalRecordKind,
    HistorianOperatingContext,
)

BASE_TIME = datetime(2026, 9, 14, 15, 42, tzinfo=UTC)


def model() -> FunctionalTemporalModel:
    return FunctionalTemporalModel(
        phases=(
            PhaseDefinition("INDEXED", "Bottle indexed", "indexer"),
            PhaseDefinition(
                "CAPTURED",
                "Bottle captured",
                "capture",
                invariant_ids=("INV_CAPTURE_RESTRAINT",),
            ),
            PhaseDefinition(
                "WRAP",
                "Wrap active",
                "wrapper",
                invariant_ids=("INV_WRAP_READY",),
            ),
        ),
        transitions=(
            TransitionDefinition(
                "INDEXED_TO_CAPTURED",
                "INDEXED",
                "CAPTURED",
                "CaptureEstablished",
                ("GUARD_BOTTLE_PRESENT", "GUARD_CAPTURE_READY"),
            ),
            TransitionDefinition(
                "CAPTURED_TO_WRAP",
                "CAPTURED",
                "WRAP",
                "WrapBegin",
                ("GUARD_CAPTURE_READY",),
            ),
        ),
        guards=(
            GuardDefinition(
                "GUARD_BOTTLE_PRESENT",
                ("bottle_present",),
                TemporalCoverage.POINT_ONLY,
            ),
            GuardDefinition(
                "GUARD_CAPTURE_READY",
                ("capture_ready",),
                TemporalCoverage.POINT_ONLY,
                depends_on_requirement_ids=("GUARD_BOTTLE_PRESENT",),
            ),
        ),
        invariants=(
            InvariantDefinition(
                "INV_CAPTURE_RESTRAINT",
                ("capture_restraint",),
                TemporalCoverage.THROUGHOUT_SCOPE,
            ),
            InvariantDefinition(
                "INV_WRAP_READY",
                ("wrap_relationship",),
                TemporalCoverage.THROUGHOUT_SCOPE,
                depends_on_requirement_ids=("INV_CAPTURE_RESTRAINT",),
            ),
        ),
    )


def context() -> HistorianOperatingContext:
    return HistorianOperatingContext(
        asset_id="LABELER-DEMO-01",
        component_id="capture-runtime",
        profile_id="speedway-labeler-demo-v1",
        operating_mode="production",
        configuration_version="plc-config-4.2.1",
        firmware_version="servo-fw-3.7",
        calibration_id="CAL-104",
        sampling_profile_id="profile-20ms-v1",
        recipe_id="500ml-round",
        product_id="bottle-500ml",
    )


def event(
    event_type: str = "CaptureEstablished",
    *,
    event_id: str = "event-stop-extended-42",
    timestamp: datetime = BASE_TIME,
    asset_id: str = "LABELER-DEMO-01",
    component_id: str = "stop-actuator",
) -> MachineEvent:
    return MachineEvent(
        event_id=event_id,
        source_id="plc-labeler-demo",
        asset_id=asset_id,
        component_id=component_id,
        event_type=event_type,
        timestamp=timestamp,
        correlation_id="corr-cycle-42",
        quality=EventQuality.GOOD,
        attributes={"operating_mode": "production"},
    )


def observation(
    key: str,
    *,
    state: EpistemicState = EpistemicState.VERIFIED,
    validity: EvidenceValidity = EvidenceValidity.CURRENT,
    coverage: TemporalCoverage = TemporalCoverage.POINT_ONLY,
    cycle_id: str = "cycle-42",
) -> EvidenceObservation:
    return EvidenceObservation(
        evidence_id=f"E:{key}",
        evidence_key=key,
        state=state,
        validity=validity,
        coverage=coverage,
        source_id="classified-condition-runtime",
        cycle_id=cycle_id,
    )


def runtime() -> FunctionalTemporalRuntime:
    return FunctionalTemporalRuntime(model(), initial_phase_id="INDEXED")


def admission_evidence() -> dict[str, EvidenceObservation]:
    return {
        "bottle_present": observation("bottle_present"),
        "capture_ready": observation("capture_ready"),
    }


def test_admitted_transition_advances_cycle_and_projects_guard_transition_phase() -> None:
    result = runtime().process_event(
        event(),
        episode_id="incident-2026-09-14",
        cycle_id="cycle-42",
        evidence=admission_evidence(),
        operating_context=context(),
        clock_evidence={"quality": "synchronized"},
    )

    assert result.previous_phase_id == "INDEXED"
    assert result.current_phase_id == "CAPTURED"
    assert result.transition.disposition is TransitionDisposition.ADMITTED
    assert [record.record_kind for record in result.history_records] == [
        FunctionalTemporalRecordKind.GUARD,
        FunctionalTemporalRecordKind.GUARD,
        FunctionalTemporalRecordKind.TRANSITION,
        FunctionalTemporalRecordKind.PHASE,
    ]
    phase_record = result.history_records[-1]
    assert phase_record.phase_id == "CAPTURED"
    assert phase_record.details["record_semantic"] == "phase_admission"
    assert phase_record.operating_context.component_id == "capture"
    assert phase_record.coverage is TemporalCoverage.POINT_ONLY


def test_transition_record_preserves_exact_trigger_event_provenance() -> None:
    trigger = event()
    result = runtime().process_event(
        trigger,
        episode_id="incident",
        cycle_id="cycle-42",
        evidence=admission_evidence(),
        operating_context=context(),
    )

    transition = next(
        item
        for item in result.history_records
        if item.record_kind is FunctionalTemporalRecordKind.TRANSITION
    )
    assert transition.trigger_event_id == trigger.event_id
    assert transition.details["trigger_event_source_id"] == trigger.source_id
    assert transition.details["trigger_event_fingerprint"] == trigger.fingerprint
    assert transition.details["correlation_id"] == trigger.correlation_id
    assert transition.operating_context.component_id == trigger.component_id


def test_unresolved_transition_is_recorded_but_does_not_advance_phase() -> None:
    rt = runtime()
    result = rt.process_event(
        event(),
        episode_id="incident",
        cycle_id="cycle-42",
        evidence={"bottle_present": observation("bottle_present")},
        operating_context=context(),
    )

    assert result.transition.disposition is TransitionDisposition.UNRESOLVED
    assert result.current_phase_id == "INDEXED"
    assert rt.current_phase("cycle-42") == "INDEXED"
    assert all(
        record.details["record_semantic"] != "phase_admission" for record in result.history_records
    )
    transition = result.history_records[-1]
    assert transition.record_kind is FunctionalTemporalRecordKind.TRANSITION
    assert transition.state is EpistemicState.EXPOSED
    assert transition.validity is EvidenceValidity.UNKNOWN


def test_rejected_transition_does_not_advance_phase() -> None:
    rt = runtime()
    evidence = admission_evidence()
    evidence["bottle_present"] = observation("bottle_present", state=EpistemicState.VIOLATED)

    result = rt.process_event(
        event(),
        episode_id="incident",
        cycle_id="cycle-42",
        evidence=evidence,
        operating_context=context(),
    )

    assert result.transition.disposition is TransitionDisposition.REJECTED
    assert result.current_phase_id == "INDEXED"
    assert not any(
        record.record_kind is FunctionalTemporalRecordKind.PHASE
        for record in result.history_records
    )


def test_unrelated_event_does_not_create_history_or_mutate_cycle() -> None:
    rt = runtime()
    result = rt.process_event(
        event("BottleDetected", event_id="event-bottle-42"),
        episode_id="incident",
        cycle_id="cycle-42",
        evidence={},
        operating_context=context(),
    )

    assert result.transition.disposition is TransitionDisposition.NOT_TRIGGERED
    assert result.history_records == ()
    assert rt.current_phase("cycle-42") == "INDEXED"


def test_active_phase_assessment_projects_invariant_and_summary_without_state_change() -> None:
    rt = runtime()
    rt.process_event(
        event(),
        episode_id="incident",
        cycle_id="cycle-42",
        evidence=admission_evidence(),
        operating_context=context(),
    )
    observed_at = BASE_TIME + timedelta(milliseconds=300)
    assessment = rt.assess_active_phase(
        episode_id="incident",
        cycle_id="cycle-42",
        observed_at=observed_at,
        evidence={
            "capture_restraint": observation(
                "capture_restraint",
                coverage=TemporalCoverage.THROUGHOUT_SCOPE,
            )
        },
        operating_context=context(),
        clock_evidence={"quality": "synchronized"},
    )

    assert assessment.phase_id == "CAPTURED"
    assert assessment.evaluation.state is EpistemicState.VERIFIED
    assert rt.current_phase("cycle-42") == "CAPTURED"
    assert [record.record_kind for record in assessment.history_records] == [
        FunctionalTemporalRecordKind.INVARIANT,
        FunctionalTemporalRecordKind.PHASE,
    ]
    invariant, phase = assessment.history_records
    assert invariant.coverage is TemporalCoverage.THROUGHOUT_SCOPE
    assert phase.coverage is TemporalCoverage.POINT_ONLY
    assert phase.details["record_semantic"] == "phase_assessment"
    assert phase.details["phase_entered_at"] == BASE_TIME.isoformat()


def test_phase_assessment_keeps_insufficient_interval_evidence_unresolved() -> None:
    rt = runtime()
    rt.process_event(
        event(),
        episode_id="incident",
        cycle_id="cycle-42",
        evidence=admission_evidence(),
        operating_context=context(),
    )

    assessment = rt.assess_active_phase(
        episode_id="incident",
        cycle_id="cycle-42",
        observed_at=BASE_TIME + timedelta(milliseconds=200),
        evidence={"capture_restraint": observation("capture_restraint")},
        operating_context=context(),
    )

    assert assessment.evaluation.state is EpistemicState.UNRESOLVED
    invariant = assessment.history_records[0]
    assert invariant.state is EpistemicState.UNRESOLVED
    assert invariant.coverage is TemporalCoverage.THROUGHOUT_SCOPE
    backing = invariant.details["backing_evidence"]["capture_restraint"]
    assert backing["coverage"] == "POINT_ONLY"


def test_stale_guard_evidence_projects_stale_validity_without_phase_admission() -> None:
    rt = runtime()
    evidence = admission_evidence()
    evidence["bottle_present"] = observation("bottle_present", validity=EvidenceValidity.STALE)

    result = rt.process_event(
        event(),
        episode_id="incident",
        cycle_id="cycle-42",
        evidence=evidence,
        operating_context=context(),
    )

    transition = result.history_records[-1]
    assert result.transition.disposition is TransitionDisposition.UNRESOLVED
    assert transition.validity is EvidenceValidity.STALE
    assert rt.current_phase("cycle-42") == "INDEXED"


def test_cycle_mismatched_evidence_fails_closed() -> None:
    evidence = admission_evidence()
    evidence["capture_ready"] = observation("capture_ready", cycle_id="cycle-99")

    with pytest.raises(FunctionalTemporalRuntimeError, match="belongs to cycle"):
        runtime().process_event(
            event(),
            episode_id="incident",
            cycle_id="cycle-42",
            evidence=evidence,
            operating_context=context(),
        )


def test_event_asset_must_match_operating_context() -> None:
    with pytest.raises(FunctionalTemporalRuntimeError, match="does not match"):
        runtime().process_event(
            event(asset_id="OTHER-ASSET"),
            episode_id="incident",
            cycle_id="cycle-42",
            evidence=admission_evidence(),
            operating_context=context(),
        )


def test_cycles_keep_independent_phase_state() -> None:
    rt = runtime()
    rt.process_event(
        event(event_id="event-cycle-42"),
        episode_id="incident",
        cycle_id="cycle-42",
        evidence=admission_evidence(),
        operating_context=context(),
    )

    assert rt.current_phase("cycle-42") == "CAPTURED"
    assert rt.current_phase("cycle-43") == "INDEXED"


def test_second_admitted_transition_advances_from_current_phase() -> None:
    rt = runtime()
    rt.process_event(
        event(),
        episode_id="incident",
        cycle_id="cycle-42",
        evidence=admission_evidence(),
        operating_context=context(),
    )
    wrap = rt.process_event(
        event(
            "WrapBegin",
            event_id="event-wrap-42",
            timestamp=BASE_TIME + timedelta(milliseconds=400),
            component_id="wrapper-drive",
        ),
        episode_id="incident",
        cycle_id="cycle-42",
        evidence=admission_evidence(),
        operating_context=context(),
    )

    assert wrap.previous_phase_id == "CAPTURED"
    assert wrap.current_phase_id == "WRAP"
    assert wrap.transition.transition_id == "CAPTURED_TO_WRAP"


def test_history_record_ids_are_deterministic_for_replayed_evidence() -> None:
    rt1 = runtime()
    rt2 = runtime()
    args = {
        "episode_id": "incident",
        "cycle_id": "cycle-42",
        "evidence": admission_evidence(),
        "operating_context": context(),
    }

    first = rt1.process_event(event(), **args)
    second = rt2.process_event(event(), **args)

    assert [item.record_id for item in first.history_records] == [
        item.record_id for item in second.history_records
    ]


def test_cycle_rejects_mid_cycle_configuration_drift() -> None:
    rt = runtime()
    rt.process_event(
        event(),
        episode_id="incident",
        cycle_id="cycle-42",
        evidence=admission_evidence(),
        operating_context=context(),
    )
    changed = HistorianOperatingContext(
        asset_id="LABELER-DEMO-01",
        component_id="capture-runtime",
        profile_id="speedway-labeler-demo-v1",
        operating_mode="production",
        configuration_version="plc-config-4.2.2",
        firmware_version="servo-fw-3.7",
        calibration_id="CAL-104",
        sampling_profile_id="profile-20ms-v1",
        recipe_id="500ml-round",
        product_id="bottle-500ml",
    )

    with pytest.raises(FunctionalTemporalRuntimeError, match="changed within cycle"):
        rt.assess_active_phase(
            episode_id="incident",
            cycle_id="cycle-42",
            observed_at=BASE_TIME + timedelta(milliseconds=250),
            evidence={
                "capture_restraint": observation(
                    "capture_restraint",
                    coverage=TemporalCoverage.THROUGHOUT_SCOPE,
                )
            },
            operating_context=changed,
        )


def test_event_operating_mode_must_match_context() -> None:
    trigger = MachineEvent(
        event_id="event-mode-mismatch",
        source_id="plc-labeler-demo",
        asset_id="LABELER-DEMO-01",
        component_id="stop-actuator",
        event_type="CaptureEstablished",
        timestamp=BASE_TIME,
        correlation_id="corr-cycle-42",
        quality=EventQuality.GOOD,
        attributes={"operating_mode": "maintenance"},
    )

    with pytest.raises(FunctionalTemporalRuntimeError, match="operating mode"):
        runtime().process_event(
            trigger,
            episode_id="incident",
            cycle_id="cycle-42",
            evidence=admission_evidence(),
            operating_context=context(),
        )
