"""Thin orchestration across source binding, phase runtime, and historian durability."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol

from .functional_temporal import EvidenceObservation
from .functional_temporal_runtime import (
    FunctionalTemporalPhaseAssessment,
    FunctionalTemporalRuntime,
    FunctionalTemporalRuntimeResult,
)
from .functional_temporal_source_binding import (
    EvidenceBindingProjection,
    FunctionalTemporalEvidenceBinder,
)
from .historian import FunctionalTemporalHistoryRecord, HistorianOperatingContext
from .live_condition import LiveConditionResult
from .streaming import StreamDisposition


class FunctionalTemporalOrchestrationError(RuntimeError):
    """Raised when one bounded orchestration unit cannot complete safely."""


class OrchestrationDisposition(StrEnum):
    """Outcome of one admitted or skipped live-condition result."""

    PROCESSED = "PROCESSED"
    SKIPPED_TRANSPORT_REJECTED = "SKIPPED_TRANSPORT_REJECTED"
    SKIPPED_DUPLICATE_EVENT = "SKIPPED_DUPLICATE_EVENT"


class FunctionalTemporalHistoryBatchSink(Protocol):
    """Minimal historian contract required by the orchestrator."""

    def record_functional_temporal_evidence_batch(
        self,
        records: tuple[FunctionalTemporalHistoryRecord, ...],
    ) -> tuple[dict[str, Any], ...]: ...


@dataclass(frozen=True, slots=True)
class FunctionalTemporalOrchestrationResult:
    """One atomic live-condition orchestration result."""

    disposition: OrchestrationDisposition
    cycle_id: str
    event_id: str
    source_projection: EvidenceBindingProjection | None
    phase_assessment: FunctionalTemporalPhaseAssessment | None
    runtime_result: FunctionalTemporalRuntimeResult | None
    persisted_record_ids: tuple[str, ...]
    live_refusal_reason_codes: tuple[str, ...]


class FunctionalTemporalOrchestrator:
    """Join existing governed evidence layers without adding new interpretation rules."""

    def __init__(
        self,
        *,
        binder: FunctionalTemporalEvidenceBinder,
        runtime: FunctionalTemporalRuntime,
        historian: FunctionalTemporalHistoryBatchSink,
    ) -> None:
        self.binder = binder
        self.runtime = runtime
        self.historian = historian
        self._evidence_by_cycle: dict[str, dict[str, EvidenceObservation]] = {}
        self._lock = threading.RLock()

    def cycle_evidence(self, cycle_id: str) -> Mapping[str, EvidenceObservation]:
        """Return a detached read-only view of admitted bound evidence for one cycle."""

        _require_text(cycle_id, "cycle_id")
        with self._lock:
            return MappingProxyType(dict(self._evidence_by_cycle.get(cycle_id, {})))

    def process_live_result(
        self,
        result: LiveConditionResult,
        *,
        episode_id: str,
        operating_context: HistorianOperatingContext,
    ) -> FunctionalTemporalOrchestrationResult:
        """Bind one accepted event and its same-step measurements before phase evaluation."""

        _require_text(episode_id, "episode_id")
        stream_result = result.stream_result
        event = stream_result.envelope.event
        cycle_id = event.correlation_id

        if stream_result.receipt.disposition is not StreamDisposition.ACCEPTED:
            return FunctionalTemporalOrchestrationResult(
                disposition=OrchestrationDisposition.SKIPPED_TRANSPORT_REJECTED,
                cycle_id=cycle_id,
                event_id=event.event_id,
                source_projection=None,
                phase_assessment=None,
                runtime_result=None,
                persisted_record_ids=(),
                live_refusal_reason_codes=tuple(refusal.reason_code for refusal in result.refusals),
            )

        pipeline_result = stream_result.pipeline_result
        if pipeline_result is None:
            raise FunctionalTemporalOrchestrationError(
                "accepted transport result must include a pipeline result"
            )
        if pipeline_result.receipt.duplicate:
            return FunctionalTemporalOrchestrationResult(
                disposition=OrchestrationDisposition.SKIPPED_DUPLICATE_EVENT,
                cycle_id=cycle_id,
                event_id=event.event_id,
                source_projection=None,
                phase_assessment=None,
                runtime_result=None,
                persisted_record_ids=(),
                live_refusal_reason_codes=tuple(refusal.reason_code for refusal in result.refusals),
            )

        projection = self.binder.project_many(
            cycle_id=cycle_id,
            events=(event,),
            measurements=result.measurements,
        )
        with self._lock:
            evidence_before = dict(self._evidence_by_cycle.get(cycle_id, {}))
            runtime_checkpoint = self.runtime.snapshot_state()
            try:
                evidence = dict(evidence_before)
                self._merge_projection(evidence, projection)
                self._evidence_by_cycle[cycle_id] = evidence

                clock_evidence = _clock_evidence(result)
                phase_assessment = self._assess_phase_at_candidate_transition(
                    event_type=event.event_type,
                    observed_at=event.timestamp,
                    episode_id=episode_id,
                    cycle_id=cycle_id,
                    evidence=evidence,
                    operating_context=operating_context,
                    clock_evidence=clock_evidence,
                )
                runtime_result = self.runtime.process_event(
                    event,
                    episode_id=episode_id,
                    cycle_id=cycle_id,
                    evidence=evidence,
                    operating_context=operating_context,
                    clock_evidence=clock_evidence,
                )
                records = tuple(
                    record
                    for group in (
                        phase_assessment.history_records if phase_assessment else (),
                        runtime_result.history_records,
                    )
                    for record in group
                )
                _validate_record_batch(records)
                if records:
                    self.historian.record_functional_temporal_evidence_batch(records)
            except Exception as exc:
                self.runtime.restore_state(runtime_checkpoint)
                if evidence_before:
                    self._evidence_by_cycle[cycle_id] = evidence_before
                else:
                    self._evidence_by_cycle.pop(cycle_id, None)
                raise FunctionalTemporalOrchestrationError(
                    f"functional-temporal orchestration failed for event {event.event_id!r}"
                ) from exc

            return FunctionalTemporalOrchestrationResult(
                disposition=OrchestrationDisposition.PROCESSED,
                cycle_id=cycle_id,
                event_id=event.event_id,
                source_projection=projection,
                phase_assessment=phase_assessment,
                runtime_result=runtime_result,
                persisted_record_ids=tuple(record.record_id for record in records),
                live_refusal_reason_codes=tuple(refusal.reason_code for refusal in result.refusals),
            )

    def assess_cycle(
        self,
        *,
        episode_id: str,
        cycle_id: str,
        observed_at: datetime,
        operating_context: HistorianOperatingContext,
        clock_evidence: Mapping[str, Any] | None = None,
    ) -> FunctionalTemporalPhaseAssessment:
        """Explicitly assess active-phase invariants from accumulated bound evidence."""

        _require_text(episode_id, "episode_id")
        _require_text(cycle_id, "cycle_id")
        with self._lock:
            runtime_checkpoint = self.runtime.snapshot_state()
            evidence = dict(self._evidence_by_cycle.get(cycle_id, {}))
            try:
                assessment = self.runtime.assess_active_phase(
                    episode_id=episode_id,
                    cycle_id=cycle_id,
                    observed_at=observed_at,
                    evidence=evidence,
                    operating_context=operating_context,
                    clock_evidence=clock_evidence or {},
                )
                _validate_record_batch(assessment.history_records)
                if assessment.history_records:
                    self.historian.record_functional_temporal_evidence_batch(
                        assessment.history_records
                    )
                return assessment
            except Exception as exc:
                self.runtime.restore_state(runtime_checkpoint)
                raise FunctionalTemporalOrchestrationError(
                    f"phase assessment failed for cycle {cycle_id!r}"
                ) from exc

    def _assess_phase_at_candidate_transition(
        self,
        *,
        event_type: str,
        observed_at: datetime,
        episode_id: str,
        cycle_id: str,
        evidence: Mapping[str, EvidenceObservation],
        operating_context: HistorianOperatingContext,
        clock_evidence: Mapping[str, Any],
    ) -> FunctionalTemporalPhaseAssessment | None:
        current_phase = self.runtime.current_phase(cycle_id)
        is_candidate = any(
            transition.from_phase_id == current_phase
            and transition.trigger_event_type == event_type
            for transition in self.runtime.model.transitions
        )
        if not is_candidate:
            return None
        phase = next(item for item in self.runtime.model.phases if item.phase_id == current_phase)
        if not phase.invariant_ids:
            return None
        return self.runtime.assess_active_phase(
            episode_id=episode_id,
            cycle_id=cycle_id,
            observed_at=observed_at,
            evidence=evidence,
            operating_context=operating_context,
            clock_evidence=clock_evidence,
        )

    @staticmethod
    def _merge_projection(
        evidence: dict[str, EvidenceObservation],
        projection: EvidenceBindingProjection,
    ) -> None:
        for key, observation in projection.evidence_map().items():
            previous = evidence.get(key)
            if previous is None:
                evidence[key] = observation
                continue
            if previous != observation:
                raise FunctionalTemporalOrchestrationError(
                    f"cycle already contains distinct evidence for key {key!r}; "
                    "explicit temporal selection is required"
                )


def _clock_evidence(result: LiveConditionResult) -> dict[str, Any]:
    envelope = result.stream_result.envelope
    return {
        "transport_source_id": envelope.event.source_id,
        "transport_session_id": envelope.session_id,
        "transport_sequence_number": envelope.sequence_number,
        "transport_clock_quality": envelope.clock_quality,
        "measurement_clock_bases": [
            measurement.clock_evidence.basis for measurement in result.measurements
        ],
        "live_refusal_reason_codes": [refusal.reason_code for refusal in result.refusals],
    }


def _validate_record_batch(
    records: tuple[FunctionalTemporalHistoryRecord, ...],
) -> None:
    identities = [(record.observed_at, record.record_id) for record in records]
    if len(identities) != len(set(identities)):
        raise FunctionalTemporalOrchestrationError(
            "orchestration produced duplicate historian record identities"
        )


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FunctionalTemporalOrchestrationError(f"{field_name} must be a non-empty string")
