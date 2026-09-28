"""Deterministic comparison of explicit functional-temporal historian selections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from .functional_temporal import EpistemicState, EvidenceValidity, TemporalCoverage
from .historian import (
    FunctionalTemporalHistoryRecord,
    FunctionalTemporalRecordKind,
    HistorianOperatingContext,
)


class FunctionalTemporalComparisonError(ValueError):
    """Raised when comparison input is malformed rather than merely incompatible."""


class ComparisonDisposition(StrEnum):
    """Whether the requested comparison was admitted."""

    ADMITTED = "ADMITTED"
    REFUSED_EMPTY_REFERENCE = "REFUSED_EMPTY_REFERENCE"
    REFUSED_EMPTY_SELECTED = "REFUSED_EMPTY_SELECTED"
    REFUSED_REFERENCE_AMBIGUOUS = "REFUSED_REFERENCE_AMBIGUOUS"
    REFUSED_CONTEXT_AMBIGUOUS = "REFUSED_CONTEXT_AMBIGUOUS"
    REFUSED_CONTEXT_MISMATCH = "REFUSED_CONTEXT_MISMATCH"
    REFUSED_INSUFFICIENT_EVIDENCE = "REFUSED_INSUFFICIENT_EVIDENCE"


class ComparisonPointDisposition(StrEnum):
    """Outcome for one semantic identity within an admitted comparison."""

    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"
    UNRESOLVED = "UNRESOLVED"
    MISSING_SELECTED = "MISSING_SELECTED"
    NEW_SELECTED_EVIDENCE = "NEW_SELECTED_EVIDENCE"


@dataclass(frozen=True, slots=True)
class FunctionalTemporalIdentity:
    """Stable semantic identity used to compare like with like."""

    record_kind: FunctionalTemporalRecordKind
    component_id: str
    phase_id: str | None
    requirement_id: str | None
    transition_id: str | None
    from_phase_id: str | None
    to_phase_id: str | None
    record_semantic: str

    @property
    def key(self) -> str:
        parts = (
            self.record_kind.value,
            self.component_id,
            self.phase_id or "-",
            self.requirement_id or "-",
            self.transition_id or "-",
            self.from_phase_id or "-",
            self.to_phase_id or "-",
            self.record_semantic,
        )
        return "|".join(parts)


@dataclass(frozen=True, slots=True)
class SourceMetricDelta:
    """Exact numeric delta for one retained source metric."""

    evidence_key: str
    semantic: str | None
    unit: str
    reference_value: float
    selected_value: float
    delta: float
    reference_status: str | None
    selected_status: str | None


@dataclass(frozen=True, slots=True)
class FunctionalTemporalComparisonPoint:
    """Reference-to-selected change for one semantic identity."""

    identity: FunctionalTemporalIdentity
    disposition: ComparisonPointDisposition
    reference_record_id: str | None
    selected_record_id: str | None
    reference_observed_at: datetime | None
    selected_observed_at: datetime | None
    reference_cycle_id: str | None
    selected_cycle_id: str | None
    reference_state: EpistemicState | None
    selected_state: EpistemicState | None
    reference_validity: EvidenceValidity | None
    selected_validity: EvidenceValidity | None
    reference_coverage: TemporalCoverage | None
    selected_coverage: TemporalCoverage | None
    reference_transition_disposition: str | None
    selected_transition_disposition: str | None
    first_divergence_at: datetime | None
    metric_deltas: tuple[SourceMetricDelta, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComparisonRefusal:
    reason_code: str
    detail: str
    fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FunctionalTemporalComparisonResult:
    """Bounded reference-vs-selected comparison result."""

    disposition: ComparisonDisposition
    reference_label: str
    selected_label: str
    points: tuple[FunctionalTemporalComparisonPoint, ...]
    refusals: tuple[ComparisonRefusal, ...]
    context: HistorianOperatingContext | None
    reference_start: datetime | None
    reference_end: datetime | None
    selected_start: datetime | None
    selected_end: datetime | None
    claim_boundary: str = (
        "Comparison reports differences in retained operational evidence under an exact "
        "compatible context. A difference is not by itself a fault, physical root cause, "
        "safe production change, or authorized action."
    )

    @property
    def changed_count(self) -> int:
        return sum(
            point.disposition is ComparisonPointDisposition.CHANGED
            for point in self.points
        )

    @property
    def unresolved_count(self) -> int:
        return sum(
            point.disposition
            in {
                ComparisonPointDisposition.UNRESOLVED,
                ComparisonPointDisposition.MISSING_SELECTED,
                ComparisonPointDisposition.NEW_SELECTED_EVIDENCE,
            }
            for point in self.points
        )


class FunctionalTemporalComparator:
    """Compare one explicit reference selection to a selected historical sequence."""

    def compare(
        self,
        reference_records: tuple[FunctionalTemporalHistoryRecord, ...],
        selected_records: tuple[FunctionalTemporalHistoryRecord, ...],
        *,
        reference_label: str = "commissioned_reference",
        selected_label: str = "selected_time",
    ) -> FunctionalTemporalComparisonResult:
        _require_text(reference_label, "reference_label")
        _require_text(selected_label, "selected_label")
        if not reference_records:
            return _refused(
                ComparisonDisposition.REFUSED_EMPTY_REFERENCE,
                reference_label,
                selected_label,
                ComparisonRefusal(
                    "COMPARISON.REFERENCE_EMPTY",
                    "The reference selection contains no functional-temporal evidence.",
                ),
            )
        if not selected_records:
            return _refused(
                ComparisonDisposition.REFUSED_EMPTY_SELECTED,
                reference_label,
                selected_label,
                ComparisonRefusal(
                    "COMPARISON.SELECTED_EMPTY",
                    "The selected-time window contains no functional-temporal evidence.",
                ),
                reference_records=reference_records,
            )

        reference_context, reference_context_refusal = _resolve_context(reference_records)
        selected_context, selected_context_refusal = _resolve_context(selected_records)
        if reference_context_refusal or selected_context_refusal:
            refusals = tuple(
                item
                for item in (reference_context_refusal, selected_context_refusal)
                if item is not None
            )
            return _refused(
                ComparisonDisposition.REFUSED_CONTEXT_AMBIGUOUS,
                reference_label,
                selected_label,
                *refusals,
                reference_records=reference_records,
                selected_records=selected_records,
            )
        if reference_context is None or selected_context is None:
            raise AssertionError("non-empty record selections must resolve a context")

        mismatches = _context_mismatches(reference_context, selected_context)
        if mismatches:
            return _refused(
                ComparisonDisposition.REFUSED_CONTEXT_MISMATCH,
                reference_label,
                selected_label,
                ComparisonRefusal(
                    "COMPARISON.OPERATING_CONTEXT_MISMATCH",
                    "Reference and selected evidence were captured under different "
                    "operating contexts.",
                    tuple(mismatches),
                ),
                reference_records=reference_records,
                selected_records=selected_records,
            )

        reference_index, ambiguous = _index_reference(reference_records)
        if ambiguous:
            return _refused(
                ComparisonDisposition.REFUSED_REFERENCE_AMBIGUOUS,
                reference_label,
                selected_label,
                ComparisonRefusal(
                    "COMPARISON.REFERENCE_IDENTITY_AMBIGUOUS",
                    "The reference selection contains multiple records for the same "
                    "semantic identity; select a narrower commissioned/reference window.",
                    tuple(identity.key for identity in ambiguous),
                ),
                reference_records=reference_records,
                selected_records=selected_records,
            )

        selected_index = _index_selected(selected_records)
        identities = sorted(
            set(reference_index) | set(selected_index),
            key=lambda identity: identity.key,
        )
        points = tuple(
            _compare_identity(
                identity,
                reference_index.get(identity),
                selected_index.get(identity, ()),
            )
            for identity in identities
        )
        comparable = tuple(
            point
            for point in points
            if point.disposition
            in {
                ComparisonPointDisposition.UNCHANGED,
                ComparisonPointDisposition.CHANGED,
            }
        )
        if not comparable:
            return FunctionalTemporalComparisonResult(
                disposition=ComparisonDisposition.REFUSED_INSUFFICIENT_EVIDENCE,
                reference_label=reference_label,
                selected_label=selected_label,
                points=points,
                refusals=(
                    ComparisonRefusal(
                        "COMPARISON.NO_CURRENT_COMPARABLE_EVIDENCE",
                        "No semantic identity has current evidence on both sides.",
                    ),
                ),
                context=reference_context,
                reference_start=_start(reference_records),
                reference_end=_end(reference_records),
                selected_start=_start(selected_records),
                selected_end=_end(selected_records),
            )

        return FunctionalTemporalComparisonResult(
            disposition=ComparisonDisposition.ADMITTED,
            reference_label=reference_label,
            selected_label=selected_label,
            points=points,
            refusals=(),
            context=reference_context,
            reference_start=_start(reference_records),
            reference_end=_end(reference_records),
            selected_start=_start(selected_records),
            selected_end=_end(selected_records),
        )


def _identity(record: FunctionalTemporalHistoryRecord) -> FunctionalTemporalIdentity:
    semantic = record.details.get("record_semantic", "unspecified")
    if not isinstance(semantic, str) or not semantic.strip():
        semantic = "unspecified"
    return FunctionalTemporalIdentity(
        record_kind=record.record_kind,
        component_id=record.operating_context.component_id,
        phase_id=record.phase_id,
        requirement_id=record.requirement_id,
        transition_id=record.transition_id,
        from_phase_id=record.from_phase_id,
        to_phase_id=record.to_phase_id,
        record_semantic=semantic,
    )


def _index_reference(
    records: tuple[FunctionalTemporalHistoryRecord, ...],
) -> tuple[
    dict[FunctionalTemporalIdentity, FunctionalTemporalHistoryRecord],
    tuple[FunctionalTemporalIdentity, ...],
]:
    grouped: dict[FunctionalTemporalIdentity, list[FunctionalTemporalHistoryRecord]] = {}
    for record in records:
        grouped.setdefault(_identity(record), []).append(record)
    ambiguous = tuple(
        identity for identity, items in grouped.items() if len(items) != 1
    )
    return (
        {identity: items[0] for identity, items in grouped.items() if len(items) == 1},
        ambiguous,
    )


def _index_selected(
    records: tuple[FunctionalTemporalHistoryRecord, ...],
) -> dict[FunctionalTemporalIdentity, tuple[FunctionalTemporalHistoryRecord, ...]]:
    grouped: dict[FunctionalTemporalIdentity, list[FunctionalTemporalHistoryRecord]] = {}
    for record in records:
        grouped.setdefault(_identity(record), []).append(record)
    return {
        identity: tuple(sorted(items, key=lambda item: (item.observed_at, item.record_id)))
        for identity, items in grouped.items()
    }


def _compare_identity(
    identity: FunctionalTemporalIdentity,
    reference: FunctionalTemporalHistoryRecord | None,
    selected: tuple[FunctionalTemporalHistoryRecord, ...],
) -> FunctionalTemporalComparisonPoint:
    if reference is None:
        latest = selected[-1]
        return _point(
            identity,
            ComparisonPointDisposition.NEW_SELECTED_EVIDENCE,
            None,
            latest,
            None,
            (),
            ("No matching semantic identity exists in the reference selection.",),
        )
    if not selected:
        return _point(
            identity,
            ComparisonPointDisposition.MISSING_SELECTED,
            reference,
            None,
            None,
            (),
            ("No matching semantic identity exists in the selected-time window.",),
        )

    latest = selected[-1]
    if (
        reference.validity is not EvidenceValidity.CURRENT
        or latest.validity is not EvidenceValidity.CURRENT
    ):
        return _point(
            identity,
            ComparisonPointDisposition.UNRESOLVED,
            reference,
            latest,
            _first_divergence(reference, selected),
            (),
            (
                "Reference and selected evidence must both be CURRENT before a "
                "state/value difference is admitted.",
            ),
        )

    metric_deltas = _metric_deltas(reference, latest)
    changed = _record_signature(reference) != _record_signature(latest) or any(
        delta.delta != 0.0 for delta in metric_deltas
    )
    return _point(
        identity,
        ComparisonPointDisposition.CHANGED
        if changed
        else ComparisonPointDisposition.UNCHANGED,
        reference,
        latest,
        _first_divergence(reference, selected),
        metric_deltas,
        (),
    )


def _point(
    identity: FunctionalTemporalIdentity,
    disposition: ComparisonPointDisposition,
    reference: FunctionalTemporalHistoryRecord | None,
    selected: FunctionalTemporalHistoryRecord | None,
    first_divergence_at: datetime | None,
    metric_deltas: tuple[SourceMetricDelta, ...],
    reasons: tuple[str, ...],
) -> FunctionalTemporalComparisonPoint:
    return FunctionalTemporalComparisonPoint(
        identity=identity,
        disposition=disposition,
        reference_record_id=reference.record_id if reference else None,
        selected_record_id=selected.record_id if selected else None,
        reference_observed_at=reference.observed_at if reference else None,
        selected_observed_at=selected.observed_at if selected else None,
        reference_cycle_id=reference.cycle_id if reference else None,
        selected_cycle_id=selected.cycle_id if selected else None,
        reference_state=reference.state if reference else None,
        selected_state=selected.state if selected else None,
        reference_validity=reference.validity if reference else None,
        selected_validity=selected.validity if selected else None,
        reference_coverage=reference.coverage if reference else None,
        selected_coverage=selected.coverage if selected else None,
        reference_transition_disposition=(
            reference.transition_disposition.value
            if reference and reference.transition_disposition is not None
            else None
        ),
        selected_transition_disposition=(
            selected.transition_disposition.value
            if selected and selected.transition_disposition is not None
            else None
        ),
        first_divergence_at=first_divergence_at,
        metric_deltas=metric_deltas,
        reasons=reasons,
    )


def _record_signature(record: FunctionalTemporalHistoryRecord) -> tuple[object, ...]:
    return (
        record.state,
        record.coverage,
        record.transition_disposition,
    )


def _first_divergence(
    reference: FunctionalTemporalHistoryRecord,
    selected: tuple[FunctionalTemporalHistoryRecord, ...],
) -> datetime | None:
    reference_metrics = _metrics(reference)
    for record in selected:
        if record.validity is not EvidenceValidity.CURRENT:
            continue
        if _record_signature(reference) != _record_signature(record):
            return record.observed_at
        if _metrics_changed(reference_metrics, _metrics(record)):
            return record.observed_at
    return None


def _metric_deltas(
    reference: FunctionalTemporalHistoryRecord,
    selected: FunctionalTemporalHistoryRecord,
) -> tuple[SourceMetricDelta, ...]:
    reference_metrics = _metrics(reference)
    selected_metrics = _metrics(selected)
    deltas: list[SourceMetricDelta] = []
    for evidence_key in sorted(set(reference_metrics) & set(selected_metrics)):
        ref = reference_metrics[evidence_key]
        sel = selected_metrics[evidence_key]
        if ref["unit"] != sel["unit"]:
            continue
        deltas.append(
            SourceMetricDelta(
                evidence_key=evidence_key,
                semantic=ref["semantic"],
                unit=ref["unit"],
                reference_value=ref["value"],
                selected_value=sel["value"],
                delta=sel["value"] - ref["value"],
                reference_status=ref["status"],
                selected_status=sel["status"],
            )
        )
    return tuple(deltas)


def _metrics(
    record: FunctionalTemporalHistoryRecord,
) -> MappingProxyType[str, dict[str, Any]]:
    backing = record.details.get("backing_evidence", {})
    if not isinstance(backing, dict):
        return MappingProxyType({})
    result: dict[str, dict[str, Any]] = {}
    for evidence_key, evidence_detail in backing.items():
        if not isinstance(evidence_key, str) or not isinstance(evidence_detail, dict):
            continue
        provenance = evidence_detail.get("provenance", {})
        if not isinstance(provenance, dict):
            continue
        try:
            value = float(provenance["value"])
        except (KeyError, TypeError, ValueError):
            continue
        unit = provenance.get("unit")
        if not isinstance(unit, str) or not unit.strip():
            continue
        semantic = provenance.get("semantic")
        status = provenance.get("temporal_rule_status")
        result[evidence_key] = {
            "value": value,
            "unit": unit,
            "semantic": semantic if isinstance(semantic, str) else None,
            "status": status if isinstance(status, str) else None,
        }
    return MappingProxyType(result)


def _metrics_changed(
    reference: MappingProxyType[str, dict[str, Any]],
    selected: MappingProxyType[str, dict[str, Any]],
) -> bool:
    common = set(reference) & set(selected)
    for key in common:
        ref = reference[key]
        sel = selected[key]
        if ref["unit"] == sel["unit"] and ref["value"] != sel["value"]:
            return True
    return False


def _resolve_context(
    records: tuple[FunctionalTemporalHistoryRecord, ...],
) -> tuple[HistorianOperatingContext | None, ComparisonRefusal | None]:
    first = records[0].operating_context
    first_identity = _context_identity(first)
    for record in records[1:]:
        if _context_identity(record.operating_context) != first_identity:
            return None, ComparisonRefusal(
                "COMPARISON.SELECTION_CONTEXT_AMBIGUOUS",
                "One selected window contains more than one operating context.",
            )
    return first, None


def _context_identity(context: HistorianOperatingContext) -> tuple[object, ...]:
    return (
        context.asset_id,
        context.profile_id,
        context.operating_mode,
        context.configuration_version,
        context.firmware_version,
        context.calibration_id,
        context.sampling_profile_id,
        context.recipe_id,
        context.product_id,
        tuple(sorted(context.context_tags.items())),
    )


def _context_mismatches(
    reference: HistorianOperatingContext,
    selected: HistorianOperatingContext,
) -> list[str]:
    pairs = {
        "asset_id": (reference.asset_id, selected.asset_id),
        "profile_id": (reference.profile_id, selected.profile_id),
        "operating_mode": (reference.operating_mode, selected.operating_mode),
        "configuration_version": (
            reference.configuration_version,
            selected.configuration_version,
        ),
        "firmware_version": (reference.firmware_version, selected.firmware_version),
        "calibration_id": (reference.calibration_id, selected.calibration_id),
        "sampling_profile_id": (
            reference.sampling_profile_id,
            selected.sampling_profile_id,
        ),
        "recipe_id": (reference.recipe_id, selected.recipe_id),
        "product_id": (reference.product_id, selected.product_id),
        "context_tags": (
            tuple(sorted(reference.context_tags.items())),
            tuple(sorted(selected.context_tags.items())),
        ),
    }
    return [field for field, values in pairs.items() if values[0] != values[1]]


def _refused(
    disposition: ComparisonDisposition,
    reference_label: str,
    selected_label: str,
    *refusals: ComparisonRefusal,
    reference_records: tuple[FunctionalTemporalHistoryRecord, ...] = (),
    selected_records: tuple[FunctionalTemporalHistoryRecord, ...] = (),
) -> FunctionalTemporalComparisonResult:
    return FunctionalTemporalComparisonResult(
        disposition=disposition,
        reference_label=reference_label,
        selected_label=selected_label,
        points=(),
        refusals=tuple(refusals),
        context=None,
        reference_start=_start(reference_records),
        reference_end=_end(reference_records),
        selected_start=_start(selected_records),
        selected_end=_end(selected_records),
    )


def _start(records: tuple[FunctionalTemporalHistoryRecord, ...]) -> datetime | None:
    return min((record.observed_at for record in records), default=None)


def _end(records: tuple[FunctionalTemporalHistoryRecord, ...]) -> datetime | None:
    return max((record.observed_at for record in records), default=None)


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FunctionalTemporalComparisonError(
            f"{field_name} must be a non-empty string"
        )
