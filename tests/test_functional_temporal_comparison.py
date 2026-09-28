from __future__ import annotations

from datetime import UTC, datetime, timedelta

from linealert_core.functional_temporal import (
    EpistemicState,
    EvidenceValidity,
    TemporalCoverage,
    TransitionDisposition,
)
from linealert_core.functional_temporal_comparison import (
    ComparisonDisposition,
    ComparisonPointDisposition,
    FunctionalTemporalComparator,
)
from linealert_core.historian import (
    FunctionalTemporalHistoryRecord,
    FunctionalTemporalRecordKind,
    HistorianOperatingContext,
)


BASE = datetime(2026, 3, 12, 14, 30, tzinfo=UTC)


def context(**overrides: object) -> HistorianOperatingContext:
    values: dict[str, object] = {
        "asset_id": "LABELER-DEMO-01",
        "component_id": "label-present-sensor",
        "profile_id": "generic-pressure-sensitive-labeler-demo-v1",
        "operating_mode": "500ml-round-bottle",
        "configuration_version": "config-v1",
        "firmware_version": "fw-v1",
        "calibration_id": "cal-v1",
        "sampling_profile_id": "sample-v1",
        "recipe_id": "500ml-round-bottle",
        "product_id": "synthetic-500ml-bottle",
        "context_tags": {"line": "demo"},
    }
    values.update(overrides)
    return HistorianOperatingContext(**values)  # type: ignore[arg-type]


def guard_record(
    *,
    record_id: str,
    observed_at: datetime,
    cycle_id: str,
    value: float,
    state: EpistemicState,
    validity: EvidenceValidity = EvidenceValidity.CURRENT,
    status: str = "within",
    operating_context: HistorianOperatingContext | None = None,
) -> FunctionalTemporalHistoryRecord:
    return FunctionalTemporalHistoryRecord(
        observed_at=observed_at,
        record_id=record_id,
        episode_id=f"episode-{cycle_id}",
        cycle_id=cycle_id,
        record_kind=FunctionalTemporalRecordKind.GUARD,
        state=state,
        validity=validity,
        coverage=TemporalCoverage.POINT_ONLY,
        source_id="linealert-functional-temporal-runtime-v1",
        operating_context=operating_context or context(),
        phase_id="LABEL_PRESENTED",
        requirement_id="GUARD_LABEL_PRESENTATION_TIMING",
        evidence_ids=(f"E:{cycle_id}",),
        details={
            "record_semantic": "transition_guard",
            "required_coverage": "POINT_ONLY",
            "backing_evidence": {
                "label_presentation_timing_within_envelope": {
                    "present": True,
                    "provenance": {
                        "value": str(value),
                        "unit": "ms",
                        "min_value": "50.0",
                        "max_value": "350.0",
                        "temporal_rule_status": status,
                        "semantic": (
                            "measured_label_feed_command_to_label_at_peel_point_delay"
                        ),
                    },
                }
            },
        },
    )


def transition_record(
    *,
    record_id: str,
    observed_at: datetime,
    cycle_id: str,
    state: EpistemicState,
    disposition: TransitionDisposition,
    operating_context: HistorianOperatingContext | None = None,
) -> FunctionalTemporalHistoryRecord:
    return FunctionalTemporalHistoryRecord(
        observed_at=observed_at,
        record_id=record_id,
        episode_id=f"episode-{cycle_id}",
        cycle_id=cycle_id,
        record_kind=FunctionalTemporalRecordKind.TRANSITION,
        state=state,
        validity=EvidenceValidity.CURRENT,
        coverage=TemporalCoverage.POINT_ONLY,
        source_id="linealert-functional-temporal-runtime-v1",
        operating_context=operating_context or context(),
        transition_id="LABEL_PRESENTATION",
        from_phase_id="BEFORE_LABEL_PRESENTATION",
        to_phase_id="LABEL_PRESENTED",
        trigger_event_id=f"event-{cycle_id}",
        transition_disposition=disposition,
        details={"record_semantic": "transition_evaluation"},
    )


def test_compare_reports_first_state_and_metric_divergence() -> None:
    reference = (
        guard_record(
            record_id="ref-guard",
            observed_at=BASE,
            cycle_id="commissioned-1",
            value=240.0,
            state=EpistemicState.VERIFIED,
        ),
    )
    selected = (
        guard_record(
            record_id="selected-1",
            observed_at=BASE + timedelta(days=180),
            cycle_id="incident-1",
            value=240.0,
            state=EpistemicState.VERIFIED,
        ),
        guard_record(
            record_id="selected-2",
            observed_at=BASE + timedelta(days=180, seconds=5),
            cycle_id="incident-2",
            value=550.0,
            state=EpistemicState.VIOLATED,
            status="late",
        ),
    )

    result = FunctionalTemporalComparator().compare(reference, selected)

    assert result.disposition is ComparisonDisposition.ADMITTED
    assert result.changed_count == 1
    point = result.points[0]
    assert point.disposition is ComparisonPointDisposition.CHANGED
    assert point.reference_state is EpistemicState.VERIFIED
    assert point.selected_state is EpistemicState.VIOLATED
    assert point.first_divergence_at == selected[1].observed_at
    assert len(point.metric_deltas) == 1
    metric = point.metric_deltas[0]
    assert metric.reference_value == 240.0
    assert metric.selected_value == 550.0
    assert metric.delta == 310.0
    assert metric.unit == "ms"
    assert metric.reference_status == "within"
    assert metric.selected_status == "late"


def test_value_change_with_same_epistemic_state_is_still_reported_changed() -> None:
    reference = (
        guard_record(
            record_id="ref",
            observed_at=BASE,
            cycle_id="ref-cycle",
            value=240.0,
            state=EpistemicState.VERIFIED,
        ),
    )
    selected = (
        guard_record(
            record_id="selected",
            observed_at=BASE + timedelta(days=1),
            cycle_id="selected-cycle",
            value=300.0,
            state=EpistemicState.VERIFIED,
        ),
    )

    result = FunctionalTemporalComparator().compare(reference, selected)

    point = result.points[0]
    assert point.disposition is ComparisonPointDisposition.CHANGED
    assert point.reference_state is point.selected_state is EpistemicState.VERIFIED
    assert point.metric_deltas[0].delta == 60.0
    assert point.first_divergence_at == selected[0].observed_at


def test_unchanged_reference_and_selected_evidence_is_not_overinterpreted() -> None:
    reference = (
        transition_record(
            record_id="ref",
            observed_at=BASE,
            cycle_id="ref-cycle",
            state=EpistemicState.VERIFIED,
            disposition=TransitionDisposition.ADMITTED,
        ),
    )
    selected = (
        transition_record(
            record_id="selected",
            observed_at=BASE + timedelta(days=1),
            cycle_id="selected-cycle",
            state=EpistemicState.VERIFIED,
            disposition=TransitionDisposition.ADMITTED,
        ),
    )

    result = FunctionalTemporalComparator().compare(reference, selected)

    assert result.disposition is ComparisonDisposition.ADMITTED
    assert result.points[0].disposition is ComparisonPointDisposition.UNCHANGED
    assert result.points[0].first_divergence_at is None
    assert "not by itself a fault" in result.claim_boundary


def test_configuration_mismatch_refuses_comparison() -> None:
    reference = (
        guard_record(
            record_id="ref",
            observed_at=BASE,
            cycle_id="ref-cycle",
            value=240.0,
            state=EpistemicState.VERIFIED,
        ),
    )
    selected = (
        guard_record(
            record_id="selected",
            observed_at=BASE + timedelta(days=1),
            cycle_id="selected-cycle",
            value=550.0,
            state=EpistemicState.VIOLATED,
            operating_context=context(configuration_version="config-v2"),
        ),
    )

    result = FunctionalTemporalComparator().compare(reference, selected)

    assert result.disposition is ComparisonDisposition.REFUSED_CONTEXT_MISMATCH
    assert result.points == ()
    assert result.refusals[0].fields == ("configuration_version",)


def test_reference_with_repeated_semantic_identity_is_refused_as_ambiguous() -> None:
    reference = (
        guard_record(
            record_id="ref-1",
            observed_at=BASE,
            cycle_id="ref-1",
            value=230.0,
            state=EpistemicState.VERIFIED,
        ),
        guard_record(
            record_id="ref-2",
            observed_at=BASE + timedelta(seconds=1),
            cycle_id="ref-2",
            value=240.0,
            state=EpistemicState.VERIFIED,
        ),
    )
    selected = (
        guard_record(
            record_id="selected",
            observed_at=BASE + timedelta(days=1),
            cycle_id="selected",
            value=550.0,
            state=EpistemicState.VIOLATED,
        ),
    )

    result = FunctionalTemporalComparator().compare(reference, selected)

    assert result.disposition is ComparisonDisposition.REFUSED_REFERENCE_AMBIGUOUS
    assert result.points == ()
    assert result.refusals[0].reason_code == (
        "COMPARISON.REFERENCE_IDENTITY_AMBIGUOUS"
    )


def test_mixed_context_inside_selected_window_is_refused() -> None:
    reference = (
        guard_record(
            record_id="ref",
            observed_at=BASE,
            cycle_id="ref",
            value=240.0,
            state=EpistemicState.VERIFIED,
        ),
    )
    selected = (
        guard_record(
            record_id="selected-1",
            observed_at=BASE + timedelta(days=1),
            cycle_id="selected-1",
            value=250.0,
            state=EpistemicState.VERIFIED,
        ),
        guard_record(
            record_id="selected-2",
            observed_at=BASE + timedelta(days=1, seconds=1),
            cycle_id="selected-2",
            value=260.0,
            state=EpistemicState.VERIFIED,
            operating_context=context(firmware_version="fw-v2"),
        ),
    )

    result = FunctionalTemporalComparator().compare(reference, selected)

    assert result.disposition is ComparisonDisposition.REFUSED_CONTEXT_AMBIGUOUS


def test_stale_selected_evidence_is_unresolved_and_cannot_carry_comparison() -> None:
    reference = (
        guard_record(
            record_id="ref",
            observed_at=BASE,
            cycle_id="ref",
            value=240.0,
            state=EpistemicState.VERIFIED,
        ),
    )
    selected = (
        guard_record(
            record_id="selected",
            observed_at=BASE + timedelta(days=1),
            cycle_id="selected",
            value=550.0,
            state=EpistemicState.VIOLATED,
            validity=EvidenceValidity.STALE,
        ),
    )

    result = FunctionalTemporalComparator().compare(reference, selected)

    assert result.disposition is ComparisonDisposition.REFUSED_INSUFFICIENT_EVIDENCE
    assert result.points[0].disposition is ComparisonPointDisposition.UNRESOLVED
    assert result.points[0].selected_validity is EvidenceValidity.STALE


def test_missing_and_new_semantic_identities_are_preserved_not_paired() -> None:
    reference_guard = guard_record(
        record_id="ref-guard",
        observed_at=BASE,
        cycle_id="ref",
        value=240.0,
        state=EpistemicState.VERIFIED,
    )
    selected_transition = transition_record(
        record_id="selected-transition",
        observed_at=BASE + timedelta(days=1),
        cycle_id="selected",
        state=EpistemicState.VERIFIED,
        disposition=TransitionDisposition.ADMITTED,
    )

    result = FunctionalTemporalComparator().compare(
        (reference_guard,),
        (selected_transition,),
    )

    assert result.disposition is ComparisonDisposition.REFUSED_INSUFFICIENT_EVIDENCE
    assert {point.disposition for point in result.points} == {
        ComparisonPointDisposition.MISSING_SELECTED,
        ComparisonPointDisposition.NEW_SELECTED_EVIDENCE,
    }


def test_component_id_is_semantic_identity_not_global_context() -> None:
    reference = (
        guard_record(
            record_id="ref",
            observed_at=BASE,
            cycle_id="ref",
            value=240.0,
            state=EpistemicState.VERIFIED,
        ),
    )
    selected = (
        guard_record(
            record_id="selected",
            observed_at=BASE + timedelta(days=1),
            cycle_id="selected",
            value=240.0,
            state=EpistemicState.VERIFIED,
            operating_context=context(component_id="different-component"),
        ),
    )

    result = FunctionalTemporalComparator().compare(reference, selected)

    assert result.disposition is ComparisonDisposition.REFUSED_INSUFFICIENT_EVIDENCE
    assert result.refusals[0].reason_code == "COMPARISON.NO_CURRENT_COMPARABLE_EVIDENCE"


def test_empty_reference_and_selected_are_explicit_refusals() -> None:
    comparator = FunctionalTemporalComparator()
    selected = (
        guard_record(
            record_id="selected",
            observed_at=BASE,
            cycle_id="selected",
            value=240.0,
            state=EpistemicState.VERIFIED,
        ),
    )

    assert comparator.compare((), selected).disposition is (
        ComparisonDisposition.REFUSED_EMPTY_REFERENCE
    )
    assert comparator.compare(selected, ()).disposition is (
        ComparisonDisposition.REFUSED_EMPTY_SELECTED
    )


def test_comparison_types_are_exported_from_public_api() -> None:
    import linealert_core

    assert linealert_core.FunctionalTemporalComparator is FunctionalTemporalComparator
    assert linealert_core.ComparisonDisposition is ComparisonDisposition
    assert linealert_core.ComparisonPointDisposition is ComparisonPointDisposition
