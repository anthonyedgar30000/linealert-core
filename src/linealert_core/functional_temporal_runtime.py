"""Stateful functional-temporal runtime projection without persistence side effects."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Any

from .events import MachineEvent
from .functional_temporal import (
    EvidenceObservation,
    EvidenceValidity,
    FunctionalTemporalEvaluator,
    FunctionalTemporalModel,
    PhaseEvaluation,
    RequirementDefinition,
    RequirementEvaluation,
    TemporalCoverage,
    TransitionDisposition,
    TransitionEvaluation,
)
from .historian import (
    FunctionalTemporalHistoryRecord,
    FunctionalTemporalRecordKind,
    HistorianOperatingContext,
)


class FunctionalTemporalRuntimeError(ValueError):
    """Raised when runtime projection inputs violate declared identity or scope."""


@dataclass(frozen=True, slots=True)
class FunctionalTemporalRuntimeResult:
    """Deterministic result of evaluating one trigger event against one cycle."""

    cycle_id: str
    previous_phase_id: str
    current_phase_id: str
    transition: TransitionEvaluation
    history_records: tuple[FunctionalTemporalHistoryRecord, ...]


@dataclass(frozen=True, slots=True)
class FunctionalTemporalPhaseAssessment:
    """Deterministic active-phase assessment plus historian-ready records."""

    cycle_id: str
    phase_id: str
    evaluation: PhaseEvaluation
    history_records: tuple[FunctionalTemporalHistoryRecord, ...]


@dataclass(frozen=True, slots=True)
class FunctionalTemporalRuntimeCheckpoint:
    """Detached runtime state used only for bounded orchestration rollback."""

    phase_by_cycle: Mapping[str, str]
    phase_entered_at: Mapping[str, datetime]
    phase_trigger_event_id: Mapping[str, str]
    context_identity_by_cycle: Mapping[str, tuple[object, ...]]


class FunctionalTemporalRuntime:
    """Track admitted phases while projecting evaluator outputs into history records.

    The runtime never derives EvidenceObservation objects from raw PLC values and never
    writes to the historian. Callers provide already-classified evidence and may persist
    the returned records after this deterministic operation completes.
    """

    def __init__(
        self,
        model: FunctionalTemporalModel,
        *,
        initial_phase_id: str,
        projection_source_id: str = "linealert-functional-temporal-runtime-v1",
    ) -> None:
        if not initial_phase_id.strip():
            raise FunctionalTemporalRuntimeError("initial_phase_id must not be empty")
        phase_ids = {item.phase_id for item in model.phases}
        if initial_phase_id not in phase_ids:
            raise FunctionalTemporalRuntimeError(
                f"initial phase {initial_phase_id!r} is not declared by the model"
            )
        if not projection_source_id.strip():
            raise FunctionalTemporalRuntimeError("projection_source_id must not be empty")

        self.model = model
        self.evaluator = FunctionalTemporalEvaluator(model)
        self.initial_phase_id = initial_phase_id
        self.projection_source_id = projection_source_id
        self._phase_by_cycle: dict[str, str] = {}
        self._phase_entered_at: dict[str, datetime] = {}
        self._phase_trigger_event_id: dict[str, str] = {}
        self._context_identity_by_cycle: dict[str, tuple[object, ...]] = {}
        self._phases = MappingProxyType({item.phase_id: item for item in model.phases})
        self._requirements = MappingProxyType(
            {item.requirement_id: item for item in (*model.guards, *model.invariants)}
        )
        self._lock = threading.RLock()

    def current_phase(self, cycle_id: str) -> str:
        """Return the admitted phase for a cycle, defaulting to the declared initial phase."""

        _require_text(cycle_id, "cycle_id")
        with self._lock:
            return self._phase_by_cycle.get(cycle_id, self.initial_phase_id)

    def snapshot_state(self) -> FunctionalTemporalRuntimeCheckpoint:
        """Return detached state so an outer persistence boundary can roll back safely."""

        with self._lock:
            return FunctionalTemporalRuntimeCheckpoint(
                phase_by_cycle=MappingProxyType(dict(self._phase_by_cycle)),
                phase_entered_at=MappingProxyType(dict(self._phase_entered_at)),
                phase_trigger_event_id=MappingProxyType(dict(self._phase_trigger_event_id)),
                context_identity_by_cycle=MappingProxyType(dict(self._context_identity_by_cycle)),
            )

    def restore_state(self, checkpoint: FunctionalTemporalRuntimeCheckpoint) -> None:
        """Restore a checkpoint after an outer orchestration step fails."""

        if not isinstance(checkpoint, FunctionalTemporalRuntimeCheckpoint):
            raise FunctionalTemporalRuntimeError(
                "checkpoint must be FunctionalTemporalRuntimeCheckpoint"
            )
        with self._lock:
            self._phase_by_cycle = dict(checkpoint.phase_by_cycle)
            self._phase_entered_at = dict(checkpoint.phase_entered_at)
            self._phase_trigger_event_id = dict(checkpoint.phase_trigger_event_id)
            self._context_identity_by_cycle = dict(checkpoint.context_identity_by_cycle)

    def process_event(
        self,
        event: MachineEvent,
        *,
        episode_id: str,
        cycle_id: str,
        evidence: Mapping[str, EvidenceObservation],
        operating_context: HistorianOperatingContext,
        clock_evidence: Mapping[str, Any] | None = None,
    ) -> FunctionalTemporalRuntimeResult:
        """Evaluate one event and advance phase only when the transition is ADMITTED."""

        _require_text(episode_id, "episode_id")
        _require_text(cycle_id, "cycle_id")
        self._validate_event_context(event, cycle_id, evidence, operating_context)

        with self._lock:
            self._bind_or_validate_cycle_context(cycle_id, operating_context)
            previous_phase = self._phase_by_cycle.get(cycle_id, self.initial_phase_id)
            transition = self.evaluator.evaluate_transition(
                previous_phase,
                event.event_type,
                evidence,
            )
            if transition.disposition is TransitionDisposition.NOT_TRIGGERED:
                return FunctionalTemporalRuntimeResult(
                    cycle_id=cycle_id,
                    previous_phase_id=previous_phase,
                    current_phase_id=previous_phase,
                    transition=transition,
                    history_records=(),
                )

            records = self._transition_records(
                event=event,
                episode_id=episode_id,
                cycle_id=cycle_id,
                evidence=evidence,
                operating_context=operating_context,
                clock_evidence=clock_evidence or {},
                evaluation=transition,
            )
            current_phase = previous_phase
            if transition.disposition is TransitionDisposition.ADMITTED:
                current_phase = transition.to_phase_id
                self._phase_by_cycle[cycle_id] = current_phase
                self._phase_entered_at[cycle_id] = event.timestamp
                self._phase_trigger_event_id[cycle_id] = event.event_id

            return FunctionalTemporalRuntimeResult(
                cycle_id=cycle_id,
                previous_phase_id=previous_phase,
                current_phase_id=current_phase,
                transition=transition,
                history_records=records,
            )

    def assess_active_phase(
        self,
        *,
        episode_id: str,
        cycle_id: str,
        observed_at: datetime,
        evidence: Mapping[str, EvidenceObservation],
        operating_context: HistorianOperatingContext,
        clock_evidence: Mapping[str, Any] | None = None,
    ) -> FunctionalTemporalPhaseAssessment:
        """Evaluate active-phase invariants without changing the admitted phase."""

        _require_text(episode_id, "episode_id")
        _require_text(cycle_id, "cycle_id")
        _require_aware(observed_at, "observed_at")
        self._validate_cycle_evidence(cycle_id, evidence)

        with self._lock:
            self._bind_or_validate_cycle_context(cycle_id, operating_context)
            phase_id = self._phase_by_cycle.get(cycle_id, self.initial_phase_id)
            evaluation = self.evaluator.evaluate_phase(phase_id, evidence)
            records = self._phase_assessment_records(
                episode_id=episode_id,
                cycle_id=cycle_id,
                observed_at=observed_at,
                evidence=evidence,
                operating_context=operating_context,
                clock_evidence=clock_evidence or {},
                evaluation=evaluation,
            )
            return FunctionalTemporalPhaseAssessment(
                cycle_id=cycle_id,
                phase_id=phase_id,
                evaluation=evaluation,
                history_records=records,
            )

    def _validate_event_context(
        self,
        event: MachineEvent,
        cycle_id: str,
        evidence: Mapping[str, EvidenceObservation],
        operating_context: HistorianOperatingContext,
    ) -> None:
        if event.asset_id != operating_context.asset_id:
            raise FunctionalTemporalRuntimeError(
                f"event asset {event.asset_id!r} does not match operating context asset "
                f"{operating_context.asset_id!r}"
            )
        event_mode = event.attributes.get("operating_mode")
        if event_mode is not None and event_mode != operating_context.operating_mode:
            raise FunctionalTemporalRuntimeError(
                f"event operating mode {event_mode!r} does not match operating context "
                f"{operating_context.operating_mode!r}"
            )
        self._validate_cycle_evidence(cycle_id, evidence)

    def _bind_or_validate_cycle_context(
        self,
        cycle_id: str,
        operating_context: HistorianOperatingContext,
    ) -> None:
        identity = _operating_context_identity(operating_context)
        previous = self._context_identity_by_cycle.get(cycle_id)
        if previous is None:
            self._context_identity_by_cycle[cycle_id] = identity
            return
        if previous != identity:
            raise FunctionalTemporalRuntimeError(
                f"operating context changed within cycle {cycle_id!r}"
            )

    @staticmethod
    def _validate_cycle_evidence(
        cycle_id: str,
        evidence: Mapping[str, EvidenceObservation],
    ) -> None:
        for key, observation in evidence.items():
            if key != observation.evidence_key:
                raise FunctionalTemporalRuntimeError(
                    f"evidence mapping key {key!r} does not match observation key "
                    f"{observation.evidence_key!r}"
                )
            if observation.cycle_id is not None and observation.cycle_id != cycle_id:
                raise FunctionalTemporalRuntimeError(
                    f"evidence {observation.evidence_id!r} belongs to cycle "
                    f"{observation.cycle_id!r}, not {cycle_id!r}"
                )

    def _transition_records(
        self,
        *,
        event: MachineEvent,
        episode_id: str,
        cycle_id: str,
        evidence: Mapping[str, EvidenceObservation],
        operating_context: HistorianOperatingContext,
        clock_evidence: Mapping[str, Any],
        evaluation: TransitionEvaluation,
    ) -> tuple[FunctionalTemporalHistoryRecord, ...]:
        records: list[FunctionalTemporalHistoryRecord] = []
        transition_definition = next(
            item
            for item in self.model.transitions
            if item.transition_id == evaluation.transition_id
        )
        for result in evaluation.guard_results:
            definition = self._requirements[result.requirement_id]
            records.append(
                self._requirement_record(
                    kind=FunctionalTemporalRecordKind.GUARD,
                    result=result,
                    definition=definition,
                    episode_id=episode_id,
                    cycle_id=cycle_id,
                    observed_at=event.timestamp,
                    phase_id=evaluation.to_phase_id,
                    event_id=event.event_id,
                    evidence=evidence,
                    operating_context=replace(
                        operating_context,
                        component_id=event.component_id,
                    ),
                    clock_evidence=clock_evidence,
                )
            )

        transition_validity = self._aggregate_requirement_validity(
            transition_definition.guard_ids,
            evidence,
        )
        transition_evidence_ids = _ordered_unique(
            evidence_id
            for result in evaluation.guard_results
            for evidence_id in result.evidence_ids
        )
        records.append(
            FunctionalTemporalHistoryRecord(
                observed_at=event.timestamp,
                record_id=(
                    f"FT:{episode_id}:{cycle_id}:transition:"
                    f"{evaluation.transition_id}:{event.event_id}"
                ),
                episode_id=episode_id,
                cycle_id=cycle_id,
                record_kind=FunctionalTemporalRecordKind.TRANSITION,
                state=evaluation.target_phase_admission_state,
                validity=transition_validity,
                coverage=TemporalCoverage.POINT_ONLY,
                source_id=self.projection_source_id,
                operating_context=replace(
                    operating_context,
                    component_id=event.component_id,
                ),
                transition_id=evaluation.transition_id,
                from_phase_id=evaluation.from_phase_id,
                to_phase_id=evaluation.to_phase_id,
                trigger_event_id=event.event_id,
                transition_disposition=evaluation.disposition,
                evidence_ids=transition_evidence_ids,
                reasons=_ordered_unique(
                    reason for result in evaluation.guard_results for reason in result.reasons
                ),
                clock_evidence=clock_evidence,
                details={
                    "record_semantic": "transition_evaluation",
                    "trigger_event_type": event.event_type,
                    "trigger_event_source_id": event.source_id,
                    "trigger_event_quality": event.quality.value,
                    "trigger_event_fingerprint": event.fingerprint,
                    "correlation_id": event.correlation_id,
                },
            )
        )
        if evaluation.disposition is TransitionDisposition.ADMITTED:
            phase = self._phases[evaluation.to_phase_id]
            records.append(
                FunctionalTemporalHistoryRecord(
                    observed_at=event.timestamp,
                    record_id=(
                        f"FT:{episode_id}:{cycle_id}:phase-admission:"
                        f"{evaluation.to_phase_id}:{event.event_id}"
                    ),
                    episode_id=episode_id,
                    cycle_id=cycle_id,
                    record_kind=FunctionalTemporalRecordKind.PHASE,
                    state=evaluation.target_phase_admission_state,
                    validity=transition_validity,
                    coverage=TemporalCoverage.POINT_ONLY,
                    source_id=self.projection_source_id,
                    operating_context=replace(
                        operating_context,
                        component_id=phase.owner_component_id,
                    ),
                    phase_id=evaluation.to_phase_id,
                    trigger_event_id=event.event_id,
                    evidence_ids=transition_evidence_ids,
                    reasons=(),
                    clock_evidence=clock_evidence,
                    details={
                        "record_semantic": "phase_admission",
                        "transition_id": evaluation.transition_id,
                        "from_phase_id": evaluation.from_phase_id,
                        "admission_basis": "transition_guards_verified",
                        "trigger_event_type": event.event_type,
                        "trigger_event_fingerprint": event.fingerprint,
                    },
                )
            )
        return tuple(records)

    def _phase_assessment_records(
        self,
        *,
        episode_id: str,
        cycle_id: str,
        observed_at: datetime,
        evidence: Mapping[str, EvidenceObservation],
        operating_context: HistorianOperatingContext,
        clock_evidence: Mapping[str, Any],
        evaluation: PhaseEvaluation,
    ) -> tuple[FunctionalTemporalHistoryRecord, ...]:
        phase = self._phases[evaluation.phase_id]
        records: list[FunctionalTemporalHistoryRecord] = []
        for result in evaluation.invariant_results:
            definition = self._requirements[result.requirement_id]
            records.append(
                self._requirement_record(
                    kind=FunctionalTemporalRecordKind.INVARIANT,
                    result=result,
                    definition=definition,
                    episode_id=episode_id,
                    cycle_id=cycle_id,
                    observed_at=observed_at,
                    phase_id=evaluation.phase_id,
                    event_id=None,
                    evidence=evidence,
                    operating_context=replace(
                        operating_context,
                        component_id=phase.owner_component_id,
                    ),
                    clock_evidence=clock_evidence,
                )
            )

        invariant_ids = tuple(item.requirement_id for item in evaluation.invariant_results)
        validity = self._aggregate_requirement_validity(invariant_ids, evidence)
        evidence_ids = _ordered_unique(
            evidence_id
            for result in evaluation.invariant_results
            for evidence_id in result.evidence_ids
        )
        entered_at = self._phase_entered_at.get(cycle_id)
        trigger_event_id = self._phase_trigger_event_id.get(cycle_id)
        records.append(
            FunctionalTemporalHistoryRecord(
                observed_at=observed_at,
                record_id=(
                    f"FT:{episode_id}:{cycle_id}:phase-assessment:"
                    f"{evaluation.phase_id}:{observed_at.isoformat()}"
                ),
                episode_id=episode_id,
                cycle_id=cycle_id,
                record_kind=FunctionalTemporalRecordKind.PHASE,
                state=evaluation.state,
                validity=validity,
                coverage=TemporalCoverage.POINT_ONLY,
                source_id=self.projection_source_id,
                operating_context=replace(
                    operating_context,
                    component_id=phase.owner_component_id,
                ),
                phase_id=evaluation.phase_id,
                trigger_event_id=trigger_event_id,
                evidence_ids=evidence_ids,
                reasons=_ordered_unique(
                    reason for result in evaluation.invariant_results for reason in result.reasons
                ),
                clock_evidence=clock_evidence,
                details={
                    "record_semantic": "phase_assessment",
                    "phase_entered_at": entered_at.isoformat() if entered_at else None,
                    "invariant_ids": list(invariant_ids),
                    "summary_coverage": "POINT_ONLY",
                    "invariant_coverage_preserved_on_invariant_records": True,
                },
            )
        )
        return tuple(records)

    def _requirement_record(
        self,
        *,
        kind: FunctionalTemporalRecordKind,
        result: RequirementEvaluation,
        definition: RequirementDefinition,
        episode_id: str,
        cycle_id: str,
        observed_at: datetime,
        phase_id: str,
        event_id: str | None,
        evidence: Mapping[str, EvidenceObservation],
        operating_context: HistorianOperatingContext,
        clock_evidence: Mapping[str, Any],
    ) -> FunctionalTemporalHistoryRecord:
        suffix = event_id or observed_at.isoformat()
        return FunctionalTemporalHistoryRecord(
            observed_at=observed_at,
            record_id=(
                f"FT:{episode_id}:{cycle_id}:{kind.value.lower()}:{result.requirement_id}:{suffix}"
            ),
            episode_id=episode_id,
            cycle_id=cycle_id,
            record_kind=kind,
            state=result.state,
            validity=self._requirement_validity(
                result.requirement_id,
                evidence,
                {},
            ),
            coverage=definition.required_coverage,
            source_id=self.projection_source_id,
            operating_context=operating_context,
            phase_id=phase_id,
            trigger_event_id=event_id,
            requirement_id=result.requirement_id,
            evidence_ids=result.evidence_ids,
            reasons=result.reasons,
            clock_evidence=clock_evidence,
            details={
                "record_semantic": (
                    "transition_guard"
                    if kind is FunctionalTemporalRecordKind.GUARD
                    else "phase_invariant"
                ),
                "required_coverage": definition.required_coverage.value,
                "depends_on_requirement_ids": list(definition.depends_on_requirement_ids),
                "backing_evidence": self._backing_evidence_details(definition, evidence),
            },
        )

    def _aggregate_requirement_validity(
        self,
        requirement_ids: tuple[str, ...],
        evidence: Mapping[str, EvidenceObservation],
    ) -> EvidenceValidity:
        cache: dict[str, EvidenceValidity] = {}
        values = tuple(
            self._requirement_validity(requirement_id, evidence, cache)
            for requirement_id in requirement_ids
        )
        return _aggregate_validity(values)

    def _requirement_validity(
        self,
        requirement_id: str,
        evidence: Mapping[str, EvidenceObservation],
        cache: dict[str, EvidenceValidity],
    ) -> EvidenceValidity:
        if requirement_id in cache:
            return cache[requirement_id]
        definition = self._requirements[requirement_id]
        local: list[EvidenceValidity] = []
        for key in definition.evidence_keys:
            observation = evidence.get(key)
            local.append(
                observation.validity if observation is not None else EvidenceValidity.UNKNOWN
            )
        dependencies = [
            self._requirement_validity(dependency, evidence, cache)
            for dependency in definition.depends_on_requirement_ids
        ]
        value = _aggregate_validity((*local, *dependencies))
        cache[requirement_id] = value
        return value

    @staticmethod
    def _backing_evidence_details(
        definition: RequirementDefinition,
        evidence: Mapping[str, EvidenceObservation],
    ) -> dict[str, Any]:
        details: dict[str, Any] = {}
        for key in definition.evidence_keys:
            observation = evidence.get(key)
            if observation is None:
                details[key] = {"present": False}
                continue
            details[key] = {
                "present": True,
                "evidence_id": observation.evidence_id,
                "source_id": observation.source_id,
                "state": observation.state.value,
                "validity": observation.validity.value,
                "coverage": observation.coverage.value,
                "cycle_id": observation.cycle_id,
                "phase_id": observation.phase_id,
                "semantic": observation.semantic,
                "source_classification": observation.source_classification,
                "reason_code": observation.reason_code,
                "retained_uncertainty": observation.retained_uncertainty,
                "provenance": dict(observation.provenance),
            }
        return details


def _operating_context_identity(
    context: HistorianOperatingContext,
) -> tuple[object, ...]:
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


def _aggregate_validity(values) -> EvidenceValidity:
    values = tuple(values)
    if not values or EvidenceValidity.UNKNOWN in values:
        return EvidenceValidity.UNKNOWN
    if EvidenceValidity.STALE in values:
        return EvidenceValidity.STALE
    return EvidenceValidity.CURRENT


def _ordered_unique(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FunctionalTemporalRuntimeError(f"{field_name} must be a non-empty string")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FunctionalTemporalRuntimeError(f"{field_name} must be timezone-aware")
