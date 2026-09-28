"""Read-only historian selection for functional-temporal comparison."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from .functional_temporal_comparison import (
    FunctionalTemporalComparator,
    FunctionalTemporalComparisonResult,
)
from .historian import (
    FunctionalTemporalHistoryRecord,
    FunctionalTemporalRecordKind,
)


class FunctionalTemporalSelectionError(ValueError):
    """Raised when a requested historian selection is not explicitly bounded."""


class SelectionHandoffDisposition(StrEnum):
    """Whether two historian selections are complete enough for comparison."""

    READY = "READY"
    REFUSED_REFERENCE_TRUNCATED = "REFUSED_REFERENCE_TRUNCATED"
    REFUSED_SELECTED_TRUNCATED = "REFUSED_SELECTED_TRUNCATED"


@dataclass(frozen=True, slots=True)
class FunctionalTemporalSelectionSpec:
    """Explicit bounded historian selection; never an inferred commissioning designation."""

    label: str
    asset_id: str
    limit: int = 1000
    episode_id: str | None = None
    cycle_id: str | None = None
    phase_id: str | None = None
    record_kind: FunctionalTemporalRecordKind | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.label, "label")
        _require_text(self.asset_id, "asset_id")
        if self.limit < 1 or self.limit > 5000:
            raise FunctionalTemporalSelectionError("limit must be between 1 and 5000")
        for field_name in ("episode_id", "cycle_id", "phase_id"):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(value, field_name)
        _require_aware(self.from_time, "from_time")
        _require_aware(self.to_time, "to_time")
        if (
            self.from_time is not None
            and self.to_time is not None
            and self.from_time > self.to_time
        ):
            raise FunctionalTemporalSelectionError(
                "from_time must be less than or equal to to_time"
            )
        if self.episode_id is None and self.cycle_id is None:
            if self.from_time is None or self.to_time is None:
                raise FunctionalTemporalSelectionError(
                    "selection requires episode_id, cycle_id, or both from_time and to_time"
                )


@dataclass(frozen=True, slots=True)
class FunctionalTemporalHistorySelection:
    """Typed selected historian evidence with visible truncation state."""

    spec: FunctionalTemporalSelectionSpec
    records: tuple[FunctionalTemporalHistoryRecord, ...]
    truncated: bool

    @property
    def complete(self) -> bool:
        return not self.truncated


@dataclass(frozen=True, slots=True)
class FunctionalTemporalSelectedComparison:
    """Selection metadata plus the unchanged #132 comparator result."""

    disposition: SelectionHandoffDisposition
    reference: FunctionalTemporalHistorySelection
    selected: FunctionalTemporalHistorySelection
    comparison: FunctionalTemporalComparisonResult | None
    reason_code: str | None = None
    detail: str | None = None


class FunctionalTemporalSelectionRepository(Protocol):
    """Minimal typed historian read contract required by the selector."""

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
    ) -> tuple[tuple[FunctionalTemporalHistoryRecord, ...], bool]: ...


class FunctionalTemporalHistorianSelector:
    """Select exact historian records and hand complete selections to the comparator."""

    def __init__(
        self,
        repository: FunctionalTemporalSelectionRepository,
        *,
        comparator: FunctionalTemporalComparator | None = None,
    ) -> None:
        self.repository = repository
        self.comparator = comparator or FunctionalTemporalComparator()

    def select(
        self,
        spec: FunctionalTemporalSelectionSpec,
    ) -> FunctionalTemporalHistorySelection:
        records, truncated = self.repository.select_functional_temporal_records(
            limit=spec.limit,
            asset_id=spec.asset_id,
            episode_id=spec.episode_id,
            cycle_id=spec.cycle_id,
            phase_id=spec.phase_id,
            record_kind=spec.record_kind.value if spec.record_kind is not None else None,
            from_time=spec.from_time,
            to_time=spec.to_time,
        )
        return FunctionalTemporalHistorySelection(
            spec=spec,
            records=records,
            truncated=truncated,
        )

    def compare(
        self,
        reference_spec: FunctionalTemporalSelectionSpec,
        selected_spec: FunctionalTemporalSelectionSpec,
    ) -> FunctionalTemporalSelectedComparison:
        reference = self.select(reference_spec)
        selected = self.select(selected_spec)

        if reference.truncated:
            return FunctionalTemporalSelectedComparison(
                disposition=SelectionHandoffDisposition.REFUSED_REFERENCE_TRUNCATED,
                reference=reference,
                selected=selected,
                comparison=None,
                reason_code="SELECTION.REFERENCE_TRUNCATED",
                detail=(
                    "The reference selection exceeded its explicit limit; comparison is "
                    "refused because older matching records were omitted."
                ),
            )
        if selected.truncated:
            return FunctionalTemporalSelectedComparison(
                disposition=SelectionHandoffDisposition.REFUSED_SELECTED_TRUNCATED,
                reference=reference,
                selected=selected,
                comparison=None,
                reason_code="SELECTION.SELECTED_TRUNCATED",
                detail=(
                    "The selected-time selection exceeded its explicit limit; comparison "
                    "is refused because older matching records were omitted."
                ),
            )

        comparison = self.comparator.compare(
            reference.records,
            selected.records,
            reference_label=reference.spec.label,
            selected_label=selected.spec.label,
        )
        return FunctionalTemporalSelectedComparison(
            disposition=SelectionHandoffDisposition.READY,
            reference=reference,
            selected=selected,
            comparison=comparison,
        )


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FunctionalTemporalSelectionError(f"{field_name} must be a non-empty string")


def _require_aware(value: datetime | None, field_name: str) -> None:
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() is None:
        raise FunctionalTemporalSelectionError(f"{field_name} must be timezone-aware")


def functional_temporal_selected_comparison_to_dict(
    value: FunctionalTemporalSelectedComparison,
) -> dict[str, object]:
    """Serialize the governed selection/comparison result without reinterpreting it."""

    return {
        "schema_version": "linealert.functional-temporal-selected-comparison.v1",
        "disposition": value.disposition.value,
        "reason_code": value.reason_code,
        "detail": value.detail,
        "reference": _history_selection_to_dict(value.reference),
        "selected": _history_selection_to_dict(value.selected),
        "comparison": (
            _comparison_result_to_dict(value.comparison) if value.comparison is not None else None
        ),
    }


def _history_selection_to_dict(
    value: FunctionalTemporalHistorySelection,
) -> dict[str, object]:
    return {
        "label": value.spec.label,
        "asset_id": value.spec.asset_id,
        "episode_id": value.spec.episode_id,
        "cycle_id": value.spec.cycle_id,
        "phase_id": value.spec.phase_id,
        "record_kind": (
            value.spec.record_kind.value if value.spec.record_kind is not None else None
        ),
        "from_time": (
            value.spec.from_time.isoformat() if value.spec.from_time is not None else None
        ),
        "to_time": value.spec.to_time.isoformat() if value.spec.to_time is not None else None,
        "limit": value.spec.limit,
        "record_count": len(value.records),
        "truncated": value.truncated,
    }


def _comparison_result_to_dict(
    value: FunctionalTemporalComparisonResult,
) -> dict[str, object]:
    return {
        "disposition": value.disposition.value,
        "reference_label": value.reference_label,
        "selected_label": value.selected_label,
        "changed_count": value.changed_count,
        "unresolved_count": value.unresolved_count,
        "reference_start": (
            value.reference_start.isoformat() if value.reference_start is not None else None
        ),
        "reference_end": (
            value.reference_end.isoformat() if value.reference_end is not None else None
        ),
        "selected_start": (
            value.selected_start.isoformat() if value.selected_start is not None else None
        ),
        "selected_end": value.selected_end.isoformat() if value.selected_end is not None else None,
        "claim_boundary": value.claim_boundary,
        "refusals": [
            {
                "reason_code": refusal.reason_code,
                "detail": refusal.detail,
                "fields": list(refusal.fields),
            }
            for refusal in value.refusals
        ],
        "points": [
            {
                "identity": {
                    "key": point.identity.key,
                    "record_kind": point.identity.record_kind.value,
                    "component_id": point.identity.component_id,
                    "phase_id": point.identity.phase_id,
                    "requirement_id": point.identity.requirement_id,
                    "transition_id": point.identity.transition_id,
                    "from_phase_id": point.identity.from_phase_id,
                    "to_phase_id": point.identity.to_phase_id,
                    "record_semantic": point.identity.record_semantic,
                },
                "disposition": point.disposition.value,
                "reference_record_id": point.reference_record_id,
                "selected_record_id": point.selected_record_id,
                "reference_observed_at": (
                    point.reference_observed_at.isoformat()
                    if point.reference_observed_at is not None
                    else None
                ),
                "selected_observed_at": (
                    point.selected_observed_at.isoformat()
                    if point.selected_observed_at is not None
                    else None
                ),
                "reference_cycle_id": point.reference_cycle_id,
                "selected_cycle_id": point.selected_cycle_id,
                "reference_state": (
                    point.reference_state.value if point.reference_state is not None else None
                ),
                "selected_state": (
                    point.selected_state.value if point.selected_state is not None else None
                ),
                "reference_validity": (
                    point.reference_validity.value if point.reference_validity is not None else None
                ),
                "selected_validity": (
                    point.selected_validity.value if point.selected_validity is not None else None
                ),
                "reference_coverage": (
                    point.reference_coverage.value if point.reference_coverage is not None else None
                ),
                "selected_coverage": (
                    point.selected_coverage.value if point.selected_coverage is not None else None
                ),
                "reference_transition_disposition": point.reference_transition_disposition,
                "selected_transition_disposition": point.selected_transition_disposition,
                "first_divergence_at": (
                    point.first_divergence_at.isoformat()
                    if point.first_divergence_at is not None
                    else None
                ),
                "metric_deltas": [
                    {
                        "evidence_key": metric.evidence_key,
                        "semantic": metric.semantic,
                        "unit": metric.unit,
                        "reference_value": metric.reference_value,
                        "selected_value": metric.selected_value,
                        "delta": metric.delta,
                        "reference_status": metric.reference_status,
                        "selected_status": metric.selected_status,
                    }
                    for metric in point.metric_deltas
                ],
                "reasons": list(point.reasons),
            }
            for point in value.points
        ],
    }
