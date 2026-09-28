"""Explicit source bindings for functional-temporal evidence observations."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .events import EventQuality, MachineEvent
from .functional_temporal import (
    EpistemicState,
    EvidenceObservation,
    EvidenceValidity,
    TemporalCoverage,
)
from .live_condition import LiveConditionMeasurement
from .timing import TimingStatus


class FunctionalTemporalSourceBindingError(ValueError):
    """Raised when source-binding configuration or projection is invalid."""


class EvidenceSourceClassification(StrEnum):
    """Declared semantic class of evidence admitted by this binding layer."""

    MACHINE_EVENT_OCCURRENCE = "machine_event_occurrence"
    CLOCK_QUALIFIED_TIMING_RELATIONSHIP = "clock_qualified_timing_relationship"


@dataclass(frozen=True, slots=True)
class EventEvidenceBinding:
    """Bind one exact machine-event identity to an occurrence-only evidence key."""

    binding_id: str
    evidence_key: str
    event_type: str
    component_id: str
    source_id: str
    semantic: str

    def __post_init__(self) -> None:
        _require_text_fields(
            self,
            (
                "binding_id",
                "evidence_key",
                "event_type",
                "component_id",
                "source_id",
                "semantic",
            ),
        )


@dataclass(frozen=True, slots=True)
class TimingRelationshipEvidenceBinding:
    """Bind one exact clock-qualified timing relationship to an evidence key."""

    binding_id: str
    evidence_key: str
    relationship_id: str
    rule_id: str
    signal_name: str
    semantic: str
    scope: str
    unit: str
    start_source_id: str
    end_source_id: str

    def __post_init__(self) -> None:
        _require_text_fields(
            self,
            (
                "binding_id",
                "evidence_key",
                "relationship_id",
                "rule_id",
                "signal_name",
                "semantic",
                "scope",
                "unit",
                "start_source_id",
                "end_source_id",
            ),
        )


SourceEvidenceBinding = EventEvidenceBinding | TimingRelationshipEvidenceBinding


@dataclass(frozen=True, slots=True)
class EvidenceBindingRefusal:
    """Bounded explanation for why a candidate source could not yield evidence."""

    binding_id: str
    evidence_key: str
    reason_code: str
    source_reference: str
    retained_uncertainty: str


@dataclass(frozen=True, slots=True)
class BoundEvidenceObservation:
    """One classified observation plus the exact declaration that produced it."""

    binding_id: str
    source_classification: EvidenceSourceClassification
    observation: EvidenceObservation
    claim_boundary: str


@dataclass(frozen=True, slots=True)
class EvidenceBindingProjection:
    """Evidence and refusals produced by one explicit source-binding operation."""

    observations: tuple[BoundEvidenceObservation, ...]
    refusals: tuple[EvidenceBindingRefusal, ...]

    def evidence_map(self) -> Mapping[str, EvidenceObservation]:
        """Return exact evidence by key without silent latest-wins behavior."""

        projected: dict[str, EvidenceObservation] = {}
        for bound in self.observations:
            observation = bound.observation
            previous = projected.get(observation.evidence_key)
            if previous is None:
                projected[observation.evidence_key] = observation
                continue
            if previous != observation:
                raise FunctionalTemporalSourceBindingError(
                    f"multiple distinct observations project evidence key "
                    f"{observation.evidence_key!r}"
                )
        return MappingProxyType(projected)


class FunctionalTemporalEvidenceBinder:
    """Project only explicitly declared machine-event and timing evidence."""

    _QUALIFIED_CLOCK_BASES = frozenset(
        {"same_source_relative_interval", "synchronized_cross_source_interval"}
    )

    def __init__(self, bindings: tuple[SourceEvidenceBinding, ...]) -> None:
        if not bindings:
            raise FunctionalTemporalSourceBindingError(
                "at least one functional-temporal source binding is required"
            )
        binding_ids = [item.binding_id for item in bindings]
        evidence_keys = [item.evidence_key for item in bindings]
        if len(binding_ids) != len(set(binding_ids)):
            raise FunctionalTemporalSourceBindingError("binding IDs must be unique")
        if len(evidence_keys) != len(set(evidence_keys)):
            raise FunctionalTemporalSourceBindingError("binding evidence keys must be unique")
        self.bindings = bindings
        self._event_bindings = tuple(
            item for item in bindings if isinstance(item, EventEvidenceBinding)
        )
        self._timing_bindings = tuple(
            item for item in bindings if isinstance(item, TimingRelationshipEvidenceBinding)
        )

    def project_event(
        self,
        event: MachineEvent,
        *,
        cycle_id: str,
    ) -> EvidenceBindingProjection:
        """Project exact event-occurrence evidence without physical-state upgrade."""

        _require_text(cycle_id, "cycle_id")
        observations: list[BoundEvidenceObservation] = []
        refusals: list[EvidenceBindingRefusal] = []
        candidates = tuple(
            item for item in self._event_bindings if item.event_type == event.event_type
        )
        for binding in candidates:
            mismatch = _event_binding_mismatch(binding, event, cycle_id)
            if mismatch is not None:
                refusals.append(
                    EvidenceBindingRefusal(
                        binding_id=binding.binding_id,
                        evidence_key=binding.evidence_key,
                        reason_code=mismatch,
                        source_reference=event.event_id,
                        retained_uncertainty=(
                            "The observed event did not match the exact source binding; "
                            "no functional-temporal evidence was admitted."
                        ),
                    )
                )
                continue

            state, reason = _event_quality_state(event.quality)
            uncertainty = (
                "This evidence establishes only that the declared source event was "
                "observed. It does not independently prove the resulting physical state."
            )
            observations.append(
                BoundEvidenceObservation(
                    binding_id=binding.binding_id,
                    source_classification=(EvidenceSourceClassification.MACHINE_EVENT_OCCURRENCE),
                    observation=EvidenceObservation(
                        evidence_id=(
                            f"event:{binding.binding_id}:{event.event_id}:{event.fingerprint}"
                        ),
                        evidence_key=binding.evidence_key,
                        state=state,
                        validity=EvidenceValidity.CURRENT,
                        coverage=TemporalCoverage.POINT_ONLY,
                        source_id=event.source_id,
                        cycle_id=cycle_id,
                        semantic=binding.semantic,
                        source_classification=(
                            EvidenceSourceClassification.MACHINE_EVENT_OCCURRENCE.value
                        ),
                        reason_code=reason,
                        retained_uncertainty=uncertainty,
                        provenance={
                            "event_id": event.event_id,
                            "event_source_id": event.source_id,
                            "event_component_id": event.component_id,
                            "event_type": event.event_type,
                            "event_fingerprint": event.fingerprint,
                            "correlation_id": event.correlation_id,
                            "timestamp": event.timestamp.isoformat(),
                        },
                    ),
                    claim_boundary=uncertainty,
                )
            )
        return EvidenceBindingProjection(tuple(observations), tuple(refusals))

    def project_measurement(
        self,
        measurement: LiveConditionMeasurement,
        *,
        cycle_id: str,
    ) -> EvidenceBindingProjection:
        """Project one exact clock-qualified relationship observation."""

        _require_text(cycle_id, "cycle_id")
        observation = measurement.observation
        candidates = tuple(
            item
            for item in self._timing_bindings
            if item.relationship_id == observation.relationship_id
        )
        projected: list[BoundEvidenceObservation] = []
        refusals: list[EvidenceBindingRefusal] = []
        for binding in candidates:
            mismatch = _relationship_binding_mismatch(binding, measurement, cycle_id)
            if mismatch is not None:
                refusals.append(
                    EvidenceBindingRefusal(
                        binding_id=binding.binding_id,
                        evidence_key=binding.evidence_key,
                        reason_code=mismatch,
                        source_reference=observation.observation_id,
                        retained_uncertainty=(
                            "The measured relationship did not match the exact source "
                            "binding; no functional-temporal evidence was admitted."
                        ),
                    )
                )
                continue

            if measurement.clock_evidence.basis not in self._QUALIFIED_CLOCK_BASES:
                projected.append(
                    self._relationship_observation(
                        binding,
                        measurement,
                        cycle_id=cycle_id,
                        state=EpistemicState.UNRESOLVED,
                        reason_code="EVIDENCE.RELATIONSHIP_CLOCK_BASIS_UNQUALIFIED",
                        uncertainty=(
                            "The relationship measurement exists, but its retained clock "
                            "basis is not qualified for functional-temporal admission."
                        ),
                    )
                )
                continue

            state, reason = _relationship_state(observation)
            uncertainty = (
                "This evidence establishes only the clock-qualified event relationship "
                "relative to its declared timing envelope. It does not prove physical "
                "root cause or physical contact/state."
            )
            projected.append(
                self._relationship_observation(
                    binding,
                    measurement,
                    cycle_id=cycle_id,
                    state=state,
                    reason_code=reason,
                    uncertainty=uncertainty,
                )
            )
        return EvidenceBindingProjection(tuple(projected), tuple(refusals))

    @staticmethod
    def _relationship_observation(
        binding: TimingRelationshipEvidenceBinding,
        measurement: LiveConditionMeasurement,
        *,
        cycle_id: str,
        state: EpistemicState,
        reason_code: str,
        uncertainty: str,
    ) -> BoundEvidenceObservation:
        source = measurement.observation
        source_ids = tuple(
            dict.fromkeys(
                value
                for value in (source.start_source_id, source.end_source_id)
                if value is not None
            )
        )
        return BoundEvidenceObservation(
            binding_id=binding.binding_id,
            source_classification=(
                EvidenceSourceClassification.CLOCK_QUALIFIED_TIMING_RELATIONSHIP
            ),
            observation=EvidenceObservation(
                evidence_id=(f"relationship:{binding.binding_id}:{source.observation_id}"),
                evidence_key=binding.evidence_key,
                state=state,
                validity=EvidenceValidity.CURRENT,
                coverage=TemporalCoverage.POINT_ONLY,
                source_id="+".join(source_ids),
                cycle_id=cycle_id,
                semantic=binding.semantic,
                source_classification=(
                    EvidenceSourceClassification.CLOCK_QUALIFIED_TIMING_RELATIONSHIP.value
                ),
                reason_code=reason_code,
                retained_uncertainty=uncertainty,
                provenance={
                    "observation_id": source.observation_id,
                    "relationship_id": source.relationship_id,
                    "rule_id": source.rule_id,
                    "signal_name": source.signal_name,
                    "correlation_id": source.correlation_id,
                    "start_event_id": source.start_event_id or "not-retained",
                    "end_event_id": source.end_event_id or "not-retained",
                    "start_source_id": source.start_source_id or "not-retained",
                    "end_source_id": source.end_source_id or "not-retained",
                    "clock_basis": measurement.clock_evidence.basis,
                    "start_timestamp": source.start_timestamp,
                    "end_timestamp": source.end_timestamp,
                    "value": str(source.value),
                    "unit": source.unit,
                    "min_value": str(source.min_value),
                    "max_value": str(source.max_value),
                    "temporal_rule_status": source.temporal_rule_status,
                    "quality": source.quality,
                    "semantic": source.semantic,
                    "scope": source.scope,
                },
            ),
            claim_boundary=uncertainty,
        )

    def project_many(
        self,
        *,
        cycle_id: str,
        events: Iterable[MachineEvent] = (),
        measurements: Iterable[LiveConditionMeasurement] = (),
    ) -> EvidenceBindingProjection:
        """Project a bounded source set and preserve refusals without implicit merging."""

        observations: list[BoundEvidenceObservation] = []
        refusals: list[EvidenceBindingRefusal] = []
        for event in events:
            projection = self.project_event(event, cycle_id=cycle_id)
            observations.extend(projection.observations)
            refusals.extend(projection.refusals)
        for measurement in measurements:
            projection = self.project_measurement(measurement, cycle_id=cycle_id)
            observations.extend(projection.observations)
            refusals.extend(projection.refusals)
        result = EvidenceBindingProjection(tuple(observations), tuple(refusals))
        result.evidence_map()
        return result


def load_functional_temporal_source_bindings(
    path: str | Path,
) -> tuple[SourceEvidenceBinding, ...]:
    """Load explicit source bindings from a versioned JSON document."""

    source_path = Path(path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FunctionalTemporalSourceBindingError(
            f"{source_path}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(raw, dict):
        raise FunctionalTemporalSourceBindingError(
            f"{source_path}: binding document must be an object"
        )
    if raw.get("schema_version") != "linealert.functional-temporal-source-bindings.v1":
        raise FunctionalTemporalSourceBindingError(f"{source_path}: unsupported binding schema")
    bindings_raw = raw.get("bindings")
    if not isinstance(bindings_raw, list) or not bindings_raw:
        raise FunctionalTemporalSourceBindingError(
            f"{source_path}: bindings must be a non-empty list"
        )

    bindings: list[SourceEvidenceBinding] = []
    for index, item in enumerate(bindings_raw, start=1):
        location = f"{source_path}: binding {index}"
        if not isinstance(item, dict):
            raise FunctionalTemporalSourceBindingError(f"{location}: binding must be an object")
        source_kind = _required_text(item, "source_kind", location)
        if source_kind == EvidenceSourceClassification.MACHINE_EVENT_OCCURRENCE.value:
            bindings.append(
                EventEvidenceBinding(
                    binding_id=_required_text(item, "binding_id", location),
                    evidence_key=_required_text(item, "evidence_key", location),
                    event_type=_required_text(item, "event_type", location),
                    component_id=_required_text(item, "component_id", location),
                    source_id=_required_text(item, "source_id", location),
                    semantic=_required_text(item, "semantic", location),
                )
            )
        elif source_kind == (
            EvidenceSourceClassification.CLOCK_QUALIFIED_TIMING_RELATIONSHIP.value
        ):
            bindings.append(
                TimingRelationshipEvidenceBinding(
                    binding_id=_required_text(item, "binding_id", location),
                    evidence_key=_required_text(item, "evidence_key", location),
                    relationship_id=_required_text(item, "relationship_id", location),
                    rule_id=_required_text(item, "rule_id", location),
                    signal_name=_required_text(item, "signal_name", location),
                    semantic=_required_text(item, "semantic", location),
                    scope=_required_text(item, "scope", location),
                    unit=_required_text(item, "unit", location),
                    start_source_id=_required_text(item, "start_source_id", location),
                    end_source_id=_required_text(item, "end_source_id", location),
                )
            )
        else:
            raise FunctionalTemporalSourceBindingError(
                f"{location}: unsupported source_kind {source_kind!r}"
            )

    FunctionalTemporalEvidenceBinder(tuple(bindings))
    return tuple(bindings)


def _event_binding_mismatch(
    binding: EventEvidenceBinding,
    event: MachineEvent,
    cycle_id: str,
) -> str | None:
    if event.correlation_id != cycle_id:
        return "EVIDENCE.EVENT_CYCLE_MISMATCH"
    if event.component_id != binding.component_id:
        return "EVIDENCE.EVENT_COMPONENT_MISMATCH"
    if event.source_id != binding.source_id:
        return "EVIDENCE.EVENT_SOURCE_MISMATCH"
    return None


def _relationship_binding_mismatch(
    binding: TimingRelationshipEvidenceBinding,
    measurement: LiveConditionMeasurement,
    cycle_id: str,
) -> str | None:
    observation = measurement.observation
    checks = (
        (observation.correlation_id == cycle_id, "EVIDENCE.RELATIONSHIP_CYCLE_MISMATCH"),
        (observation.rule_id == binding.rule_id, "EVIDENCE.RELATIONSHIP_RULE_MISMATCH"),
        (
            observation.signal_name == binding.signal_name,
            "EVIDENCE.RELATIONSHIP_SIGNAL_MISMATCH",
        ),
        (observation.semantic == binding.semantic, "EVIDENCE.RELATIONSHIP_SEMANTIC_MISMATCH"),
        (observation.scope == binding.scope, "EVIDENCE.RELATIONSHIP_SCOPE_MISMATCH"),
        (observation.unit == binding.unit, "EVIDENCE.RELATIONSHIP_UNIT_MISMATCH"),
        (
            observation.start_source_id == binding.start_source_id,
            "EVIDENCE.RELATIONSHIP_START_SOURCE_MISMATCH",
        ),
        (
            observation.end_source_id == binding.end_source_id,
            "EVIDENCE.RELATIONSHIP_END_SOURCE_MISMATCH",
        ),
    )
    for matches, reason in checks:
        if not matches:
            return reason
    return None


def _event_quality_state(quality: EventQuality) -> tuple[EpistemicState, str]:
    if quality is EventQuality.GOOD:
        return EpistemicState.VERIFIED, "EVIDENCE.EVENT_OCCURRENCE_OBSERVED"
    return EpistemicState.UNRESOLVED, f"EVIDENCE.EVENT_INPUT_{quality.value.upper()}"


def _relationship_state(observation) -> tuple[EpistemicState, str]:
    if observation.quality != EventQuality.GOOD.value:
        return (
            EpistemicState.UNRESOLVED,
            f"EVIDENCE.RELATIONSHIP_INPUT_{observation.quality.upper()}",
        )
    try:
        status = TimingStatus(observation.temporal_rule_status)
    except ValueError as exc:
        raise FunctionalTemporalSourceBindingError(
            f"unsupported temporal_rule_status {observation.temporal_rule_status!r}"
        ) from exc
    if status is TimingStatus.WITHIN:
        return EpistemicState.VERIFIED, "EVIDENCE.RELATIONSHIP_WITHIN_ENVELOPE"
    return EpistemicState.VIOLATED, "EVIDENCE.RELATIONSHIP_OUTSIDE_ENVELOPE"


def _require_text_fields(instance: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        _require_text(getattr(instance, field_name), field_name)


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FunctionalTemporalSourceBindingError(f"{field_name} must be a non-empty string")
    return value.strip()


def _required_text(raw: dict[str, Any], field: str, location: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FunctionalTemporalSourceBindingError(
            f"{location}: {field} must be a non-empty string"
        )
    return value.strip()
