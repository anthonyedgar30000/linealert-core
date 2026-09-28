"""Read-only condition-history selection for persistent dependency localization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from .condition_localization import (
    ConditionHistorySample,
    DependencyLocalizationResult,
    PersistenceRule,
    PersistentDependencyLocalizer,
    dependency_localization_to_dict,
)
from .historian import ConditionHistoryRecord
from .topology import TopologyGraph


class ConditionHistorySelectionError(ValueError):
    """Raised when a condition-history selection is not safely bounded."""


class ConditionLocalizationHandoffDisposition(StrEnum):
    """Whether a selected condition history may be localized."""

    READY = "READY"
    REFUSED_TRUNCATED = "REFUSED_TRUNCATED"
    REFUSED_EMPTY = "REFUSED_EMPTY"
    REFUSED_TARGET_NOT_PRESENT = "REFUSED_TARGET_NOT_PRESENT"
    REFUSED_RELATIONSHIP_FILTERED = "REFUSED_RELATIONSHIP_FILTERED"
    REFUSED_CONTEXT_AMBIGUOUS = "REFUSED_CONTEXT_AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class ConditionHistorySelectionSpec:
    """Explicit bounded condition-history selection."""

    label: str
    asset_id: str
    limit: int = 1000
    relationship_id: str | None = None
    episode_id: str | None = None
    cycle_id: str | None = None
    phase_id: str | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.label, "label")
        _require_text(self.asset_id, "asset_id")
        if self.limit < 1 or self.limit > 5000:
            raise ConditionHistorySelectionError("limit must be between 1 and 5000")
        for field_name in (
            "relationship_id",
            "episode_id",
            "cycle_id",
            "phase_id",
        ):
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
            raise ConditionHistorySelectionError("from_time must be less than or equal to to_time")
        if self.episode_id is None and self.cycle_id is None:
            if self.from_time is None or self.to_time is None:
                raise ConditionHistorySelectionError(
                    "selection requires episode_id, cycle_id, or both from_time and to_time"
                )


@dataclass(frozen=True, slots=True)
class ConditionHistorySelection:
    """Typed selected condition history with visible truncation state."""

    spec: ConditionHistorySelectionSpec
    records: tuple[ConditionHistoryRecord, ...]
    truncated: bool

    @property
    def complete(self) -> bool:
        return not self.truncated


@dataclass(frozen=True, slots=True)
class SelectedConditionLocalization:
    """Selection metadata plus unchanged persistent-localizer output."""

    disposition: ConditionLocalizationHandoffDisposition
    selection: ConditionHistorySelection
    localization: DependencyLocalizationResult | None
    reason_code: str | None = None
    detail: str | None = None


class ConditionHistorySelectionRepository(Protocol):
    """Minimal historian read contract required by the condition selector."""

    def select_condition_history_records(
        self,
        *,
        limit: int = 240,
        asset_id: str | None = None,
        relationship_id: str | None = None,
        episode_id: str | None = None,
        cycle_id: str | None = None,
        phase_id: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> tuple[tuple[ConditionHistoryRecord, ...], bool]: ...


class ConditionHistorianSelector:
    """Select complete condition history before persistent localization."""

    def __init__(self, repository: ConditionHistorySelectionRepository) -> None:
        self.repository = repository

    def select(self, spec: ConditionHistorySelectionSpec) -> ConditionHistorySelection:
        records, truncated = self.repository.select_condition_history_records(
            limit=spec.limit,
            asset_id=spec.asset_id,
            relationship_id=spec.relationship_id,
            episode_id=spec.episode_id,
            cycle_id=spec.cycle_id,
            phase_id=spec.phase_id,
            from_time=spec.from_time,
            to_time=spec.to_time,
        )
        for record in records:
            if record.asset_id != spec.asset_id:
                raise ConditionHistorySelectionError(
                    "historian selection returned a different asset_id"
                )
            if spec.relationship_id is not None and record.relationship_id != spec.relationship_id:
                raise ConditionHistorySelectionError(
                    "historian selection returned a different relationship_id"
                )
        return ConditionHistorySelection(
            spec=spec,
            records=records,
            truncated=truncated,
        )

    def localize(
        self,
        spec: ConditionHistorySelectionSpec,
        *,
        target_relationship_id: str,
        persistence_rule: PersistenceRule,
        topology: TopologyGraph,
    ) -> SelectedConditionLocalization:
        _require_text(target_relationship_id, "target_relationship_id")
        if spec.relationship_id is not None:
            return SelectedConditionLocalization(
                disposition=(ConditionLocalizationHandoffDisposition.REFUSED_RELATIONSHIP_FILTERED),
                selection=ConditionHistorySelection(
                    spec=spec,
                    records=(),
                    truncated=False,
                ),
                localization=None,
                reason_code="SELECTION.RELATIONSHIP_FILTER_HIDES_DEPENDENCIES",
                detail=(
                    "Persistent dependency localization requires the complete bounded "
                    "condition selection across related relationships; remove the "
                    "relationship_id filter."
                ),
            )

        selection = self.select(spec)
        if selection.truncated:
            return SelectedConditionLocalization(
                disposition=ConditionLocalizationHandoffDisposition.REFUSED_TRUNCATED,
                selection=selection,
                localization=None,
                reason_code="SELECTION.CONDITION_HISTORY_TRUNCATED",
                detail=(
                    "The selected condition history exceeded its explicit limit; "
                    "localization is refused because older matching records were omitted."
                ),
            )
        if not selection.records:
            return SelectedConditionLocalization(
                disposition=ConditionLocalizationHandoffDisposition.REFUSED_EMPTY,
                selection=selection,
                localization=None,
                reason_code="SELECTION.CONDITION_HISTORY_EMPTY",
                detail="The selected condition history contains no persisted measurements.",
            )
        if not any(
            record.relationship_id == target_relationship_id for record in selection.records
        ):
            return SelectedConditionLocalization(
                disposition=(ConditionLocalizationHandoffDisposition.REFUSED_TARGET_NOT_PRESENT),
                selection=selection,
                localization=None,
                reason_code="SELECTION.TARGET_RELATIONSHIP_NOT_PRESENT",
                detail=(
                    "The selected condition history does not contain the requested target "
                    "relationship."
                ),
            )

        contexts = {_context_fingerprint(record.operating_context) for record in selection.records}
        if len(contexts) > 1:
            return SelectedConditionLocalization(
                disposition=(ConditionLocalizationHandoffDisposition.REFUSED_CONTEXT_AMBIGUOUS),
                selection=selection,
                localization=None,
                reason_code="SELECTION.CONDITION_CONTEXT_AMBIGUOUS",
                detail=(
                    "The selected condition history spans more than one operating context; "
                    "persistent localization requires one exact context."
                ),
            )

        samples = tuple(_to_localization_sample(record) for record in selection.records)
        localization = PersistentDependencyLocalizer(topology).localize(
            samples,
            target_relationship_id=target_relationship_id,
            persistence_rule=persistence_rule,
        )
        return SelectedConditionLocalization(
            disposition=ConditionLocalizationHandoffDisposition.READY,
            selection=selection,
            localization=localization,
        )


def _to_localization_sample(record: ConditionHistoryRecord) -> ConditionHistorySample:
    return ConditionHistorySample(
        observed_at=record.observed_at,
        observation_id=record.observation_id,
        episode_id=record.episode_id,
        asset_id=record.asset_id,
        relationship_id=record.relationship_id,
        signal=record.signal,
        value=record.value,
        unit=record.unit,
        min_value=record.min_value,
        max_value=record.max_value,
        temporal_rule_status=record.temporal_rule_status,
        quality=record.quality,
        correlation_id=record.correlation_id,
        cycle_id=record.cycle_id,
        topology_from=record.topology_from,
        topology_to=record.topology_to,
    )


def _context_fingerprint(context: Mapping[str, object]) -> str:
    try:
        return json.dumps(
            dict(context),
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ConditionHistorySelectionError(
            "condition operating_context must be JSON-serializable"
        ) from exc


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConditionHistorySelectionError(f"{field_name} must be a non-empty string")


def _require_aware(value: datetime | None, field_name: str) -> None:
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() is None:
        raise ConditionHistorySelectionError(f"{field_name} must be timezone-aware")


def selected_condition_localization_to_dict(
    value: SelectedConditionLocalization,
) -> dict[str, object]:
    """Serialize selection and #135 localization without reinterpretation."""

    spec = value.selection.spec
    return {
        "schema_version": "linealert.selected-condition-localization.v1",
        "disposition": value.disposition.value,
        "reason_code": value.reason_code,
        "detail": value.detail,
        "selection": {
            "label": spec.label,
            "asset_id": spec.asset_id,
            "relationship_id": spec.relationship_id,
            "episode_id": spec.episode_id,
            "cycle_id": spec.cycle_id,
            "phase_id": spec.phase_id,
            "from_time": (spec.from_time.isoformat() if spec.from_time is not None else None),
            "to_time": spec.to_time.isoformat() if spec.to_time is not None else None,
            "limit": spec.limit,
            "record_count": len(value.selection.records),
            "truncated": value.selection.truncated,
        },
        "localization": (
            dependency_localization_to_dict(value.localization)
            if value.localization is not None
            else None
        ),
    }
