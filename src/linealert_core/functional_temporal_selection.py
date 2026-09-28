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
