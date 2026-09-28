from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from linealert_core.functional_temporal import (
    EpistemicState,
    EvidenceValidity,
    TemporalCoverage,
)
from linealert_core.functional_temporal_comparison import ComparisonDisposition
from linealert_core.functional_temporal_selection import (
    FunctionalTemporalHistorianSelector,
    FunctionalTemporalSelectionError,
    FunctionalTemporalSelectionSpec,
    SelectionHandoffDisposition,
    functional_temporal_selected_comparison_to_dict,
)
from linealert_core.historian import (
    FunctionalTemporalHistoryRecord,
    FunctionalTemporalRecordKind,
    HistorianOperatingContext,
)

BASE = datetime(2026, 3, 12, 14, 30, tzinfo=UTC)


def context() -> HistorianOperatingContext:
    return HistorianOperatingContext(
        asset_id="LABELER-DEMO-01",
        component_id="label-present-sensor",
        profile_id="generic-pressure-sensitive-labeler-demo-v1",
        operating_mode="500ml-round-bottle",
        configuration_version="config-v1",
        firmware_version="fw-v1",
        calibration_id="cal-v1",
        sampling_profile_id="sample-v1",
        recipe_id="500ml-round-bottle",
        product_id="synthetic-500ml-bottle",
        context_tags={"line": "demo"},
    )


def guard_record(
    *,
    record_id: str,
    observed_at: datetime,
    cycle_id: str,
    state: EpistemicState = EpistemicState.VERIFIED,
) -> FunctionalTemporalHistoryRecord:
    return FunctionalTemporalHistoryRecord(
        observed_at=observed_at,
        record_id=record_id,
        episode_id=f"episode-{cycle_id}",
        cycle_id=cycle_id,
        record_kind=FunctionalTemporalRecordKind.GUARD,
        state=state,
        validity=EvidenceValidity.CURRENT,
        coverage=TemporalCoverage.POINT_ONLY,
        source_id="linealert-functional-temporal-runtime-v1",
        operating_context=context(),
        phase_id="LABEL_PRESENTED",
        requirement_id="GUARD_LABEL_PRESENTATION_TIMING",
        evidence_ids=(f"E:{cycle_id}",),
        details={"record_semantic": "transition_guard"},
    )


class FakeSelectionRepository:
    def __init__(
        self,
        responses: list[tuple[tuple[FunctionalTemporalHistoryRecord, ...], bool]],
    ) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def select_functional_temporal_records(
        self,
        *,
        limit: int = 240,
        asset_id: str | None = None,
        episode_id: str | None = None,
        cycle_id: str | None = None,
        phase_id: str | None = None,
        record_kind: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> tuple[tuple[FunctionalTemporalHistoryRecord, ...], bool]:
        self.calls.append(
            {
                "limit": limit,
                "asset_id": asset_id,
                "episode_id": episode_id,
                "cycle_id": cycle_id,
                "phase_id": phase_id,
                "record_kind": record_kind,
                "from_time": from_time,
                "to_time": to_time,
            }
        )
        return self.responses.pop(0)


def test_selection_spec_requires_explicit_bounded_scope() -> None:
    with pytest.raises(FunctionalTemporalSelectionError, match="requires"):
        FunctionalTemporalSelectionSpec(
            label="reference",
            asset_id="LABELER-DEMO-01",
        )

    bounded = FunctionalTemporalSelectionSpec(
        label="reference",
        asset_id="LABELER-DEMO-01",
        from_time=BASE,
        to_time=BASE + timedelta(minutes=1),
    )
    assert bounded.cycle_id is None


def test_selection_spec_rejects_naive_or_inverted_time_and_bad_limit() -> None:
    with pytest.raises(FunctionalTemporalSelectionError, match="timezone-aware"):
        FunctionalTemporalSelectionSpec(
            label="selected",
            asset_id="LABELER-DEMO-01",
            cycle_id="cycle-1",
            from_time=datetime(2026, 3, 12, 14, 30),
        )
    with pytest.raises(FunctionalTemporalSelectionError, match="less than or equal"):
        FunctionalTemporalSelectionSpec(
            label="selected",
            asset_id="LABELER-DEMO-01",
            from_time=BASE + timedelta(minutes=1),
            to_time=BASE,
        )
    with pytest.raises(FunctionalTemporalSelectionError, match="between 1 and 5000"):
        FunctionalTemporalSelectionSpec(
            label="selected",
            asset_id="LABELER-DEMO-01",
            cycle_id="cycle-1",
            limit=5001,
        )


def test_selector_forwards_exact_filters_and_returns_typed_records() -> None:
    record = guard_record(
        record_id="selected",
        observed_at=BASE,
        cycle_id="cycle-42",
    )
    repository = FakeSelectionRepository([((record,), False)])
    selector = FunctionalTemporalHistorianSelector(repository)
    spec = FunctionalTemporalSelectionSpec(
        label="incident-window",
        asset_id="LABELER-DEMO-01",
        episode_id="episode-cycle-42",
        cycle_id="cycle-42",
        phase_id="LABEL_PRESENTED",
        record_kind=FunctionalTemporalRecordKind.GUARD,
        from_time=BASE - timedelta(seconds=1),
        to_time=BASE + timedelta(seconds=1),
        limit=50,
    )

    selection = selector.select(spec)

    assert selection.records == (record,)
    assert selection.complete is True
    assert repository.calls == [
        {
            "limit": 50,
            "asset_id": "LABELER-DEMO-01",
            "episode_id": "episode-cycle-42",
            "cycle_id": "cycle-42",
            "phase_id": "LABEL_PRESENTED",
            "record_kind": "GUARD",
            "from_time": BASE - timedelta(seconds=1),
            "to_time": BASE + timedelta(seconds=1),
        }
    ]


def test_truncated_reference_refuses_comparator_handoff() -> None:
    reference = guard_record(
        record_id="ref",
        observed_at=BASE,
        cycle_id="ref-cycle",
    )
    selected = guard_record(
        record_id="selected",
        observed_at=BASE + timedelta(days=1),
        cycle_id="selected-cycle",
    )
    repository = FakeSelectionRepository(
        [
            ((reference,), True),
            ((selected,), False),
        ]
    )
    selector = FunctionalTemporalHistorianSelector(repository)

    result = selector.compare(
        FunctionalTemporalSelectionSpec(
            label="explicit-reference",
            asset_id="LABELER-DEMO-01",
            cycle_id="ref-cycle",
        ),
        FunctionalTemporalSelectionSpec(
            label="incident",
            asset_id="LABELER-DEMO-01",
            cycle_id="selected-cycle",
        ),
    )

    assert result.disposition is (SelectionHandoffDisposition.REFUSED_REFERENCE_TRUNCATED)
    assert result.comparison is None
    assert result.reason_code == "SELECTION.REFERENCE_TRUNCATED"


def test_truncated_selected_window_refuses_comparator_handoff() -> None:
    reference = guard_record(
        record_id="ref",
        observed_at=BASE,
        cycle_id="ref-cycle",
    )
    selected = guard_record(
        record_id="selected",
        observed_at=BASE + timedelta(days=1),
        cycle_id="selected-cycle",
    )
    repository = FakeSelectionRepository(
        [
            ((reference,), False),
            ((selected,), True),
        ]
    )
    selector = FunctionalTemporalHistorianSelector(repository)

    result = selector.compare(
        FunctionalTemporalSelectionSpec(
            label="explicit-reference",
            asset_id="LABELER-DEMO-01",
            cycle_id="ref-cycle",
        ),
        FunctionalTemporalSelectionSpec(
            label="incident",
            asset_id="LABELER-DEMO-01",
            cycle_id="selected-cycle",
        ),
    )

    assert result.disposition is (SelectionHandoffDisposition.REFUSED_SELECTED_TRUNCATED)
    assert result.comparison is None
    assert result.reason_code == "SELECTION.SELECTED_TRUNCATED"


def test_complete_selections_feed_comparator_without_reference_inference() -> None:
    reference = guard_record(
        record_id="ref",
        observed_at=BASE,
        cycle_id="ref-cycle",
    )
    selected = guard_record(
        record_id="selected",
        observed_at=BASE + timedelta(days=1),
        cycle_id="selected-cycle",
        state=EpistemicState.VIOLATED,
    )
    repository = FakeSelectionRepository(
        [
            ((reference,), False),
            ((selected,), False),
        ]
    )
    selector = FunctionalTemporalHistorianSelector(repository)
    reference_spec = FunctionalTemporalSelectionSpec(
        label="operator-approved-reference-2026-03-12",
        asset_id="LABELER-DEMO-01",
        cycle_id="ref-cycle",
    )
    selected_spec = FunctionalTemporalSelectionSpec(
        label="incident-2026-09-08",
        asset_id="LABELER-DEMO-01",
        cycle_id="selected-cycle",
    )

    result = selector.compare(reference_spec, selected_spec)

    assert result.disposition is SelectionHandoffDisposition.READY
    assert result.comparison is not None
    assert result.comparison.disposition is ComparisonDisposition.ADMITTED
    assert result.comparison.reference_label == reference_spec.label
    assert result.comparison.selected_label == selected_spec.label
    assert result.reference.spec.label == "operator-approved-reference-2026-03-12"


def test_selection_types_are_exported_from_public_api() -> None:
    import linealert_core

    assert linealert_core.FunctionalTemporalHistorianSelector is FunctionalTemporalHistorianSelector
    assert linealert_core.FunctionalTemporalSelectionSpec is FunctionalTemporalSelectionSpec
    assert linealert_core.SelectionHandoffDisposition is SelectionHandoffDisposition


def test_selected_comparison_serializer_preserves_governed_result() -> None:
    reference = guard_record(
        record_id="ref",
        observed_at=BASE,
        cycle_id="ref-cycle",
    )
    selected = guard_record(
        record_id="selected",
        observed_at=BASE + timedelta(days=1),
        cycle_id="selected-cycle",
        state=EpistemicState.VIOLATED,
    )
    selector = FunctionalTemporalHistorianSelector(
        FakeSelectionRepository(
            [
                ((reference,), False),
                ((selected,), False),
            ]
        )
    )
    result = selector.compare(
        FunctionalTemporalSelectionSpec(
            label="Reference cycle ref-cycle",
            asset_id="LABELER-DEMO-01",
            cycle_id="ref-cycle",
        ),
        FunctionalTemporalSelectionSpec(
            label="Selected cycle selected-cycle",
            asset_id="LABELER-DEMO-01",
            cycle_id="selected-cycle",
        ),
    )

    payload = functional_temporal_selected_comparison_to_dict(result)

    assert payload["schema_version"] == ("linealert.functional-temporal-selected-comparison.v1")
    assert payload["disposition"] == "READY"
    comparison = payload["comparison"]
    assert isinstance(comparison, dict)
    assert comparison["disposition"] == "ADMITTED"
    assert comparison["changed_count"] == 1
    assert comparison["reference_label"] == "Reference cycle ref-cycle"
    assert comparison["selected_label"] == "Selected cycle selected-cycle"
    points = comparison["points"]
    assert isinstance(points, list)
    assert points[0]["disposition"] == "CHANGED"
    assert points[0]["reference_state"] == "VERIFIED"
    assert points[0]["selected_state"] == "VIOLATED"
    assert payload["reference"]["cycle_id"] == "ref-cycle"
    assert payload["selected"]["cycle_id"] == "selected-cycle"


def test_selected_comparison_serializer_preserves_selection_refusal() -> None:
    reference = guard_record(
        record_id="ref",
        observed_at=BASE,
        cycle_id="ref-cycle",
    )
    selected = guard_record(
        record_id="selected",
        observed_at=BASE + timedelta(days=1),
        cycle_id="selected-cycle",
    )
    selector = FunctionalTemporalHistorianSelector(
        FakeSelectionRepository(
            [
                ((reference,), True),
                ((selected,), False),
            ]
        )
    )
    result = selector.compare(
        FunctionalTemporalSelectionSpec(
            label="Reference",
            asset_id="LABELER-DEMO-01",
            cycle_id="ref-cycle",
        ),
        FunctionalTemporalSelectionSpec(
            label="Selected",
            asset_id="LABELER-DEMO-01",
            cycle_id="selected-cycle",
        ),
    )

    payload = functional_temporal_selected_comparison_to_dict(result)

    assert payload["disposition"] == "REFUSED_REFERENCE_TRUNCATED"
    assert payload["reason_code"] == "SELECTION.REFERENCE_TRUNCATED"
    assert payload["comparison"] is None
    assert payload["reference"]["truncated"] is True
