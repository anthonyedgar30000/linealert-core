"""Bounded read-only streaming ingestion for LineAlert Core."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from .events import MachineEvent
from .machine import MachineProfile
from .pipeline import LineAlertCore, PipelineResult
from .topology import DependencyEdge


class StreamInputError(ValueError):
    """Raised when streaming transport evidence is malformed."""


class StreamDisposition(StrEnum):
    """Whether one transport envelope was admitted to the reasoning core."""

    ACCEPTED = "accepted"
    REJECTED_SEQUENCE_GAP = "rejected_sequence_gap"
    REJECTED_OUT_OF_ORDER = "rejected_out_of_order"
    REJECTED_SESSION_REUSE = "rejected_session_reuse"
    REJECTED_SESSION_START = "rejected_session_start"


@dataclass(frozen=True, slots=True)
class StreamEnvelope:
    """One event plus transport evidence that must not alter event meaning."""

    session_id: str
    sequence_number: int
    received_at: datetime
    event: MachineEvent
    clock_quality: str = "unknown"
    transport_attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise StreamInputError("session_id must be a non-empty string")
        if not isinstance(self.sequence_number, int) or isinstance(self.sequence_number, bool):
            raise StreamInputError("sequence_number must be an integer")
        if self.sequence_number < 0:
            raise StreamInputError("sequence_number must be non-negative")
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            raise StreamInputError("received_at must be timezone-aware")
        if not isinstance(self.clock_quality, str) or not self.clock_quality.strip():
            raise StreamInputError("clock_quality must be a non-empty string")
        object.__setattr__(
            self,
            "transport_attributes",
            MappingProxyType(dict(self.transport_attributes)),
        )


@dataclass(frozen=True, slots=True)
class StreamReceipt:
    """Deterministic admission evidence for one stream envelope."""

    source_id: str
    session_id: str
    sequence_number: int
    expected_sequence_number: int
    received_at: datetime
    event_id: str
    event_fingerprint: str
    disposition: StreamDisposition
    session_transition: bool
    retained_uncertainty: str


@dataclass(frozen=True, slots=True)
class StreamResult:
    """Transport evidence and optional core result for one envelope."""

    envelope: StreamEnvelope
    receipt: StreamReceipt
    pipeline_result: PipelineResult | None


@dataclass(frozen=True, slots=True)
class StreamSummary:
    """All deterministic transport and reasoning results from one stream run."""

    results: tuple[StreamResult, ...]
    machine_profile: MachineProfile | None
    topology_edges: tuple[DependencyEdge, ...]

    @property
    def accepted_events(self) -> int:
        return sum(
            result.receipt.disposition is StreamDisposition.ACCEPTED
            for result in self.results
        )

    @property
    def rejected_events(self) -> int:
        return len(self.results) - self.accepted_events

    @property
    def pipeline_results(self) -> tuple[PipelineResult, ...]:
        return tuple(
            result.pipeline_result
            for result in self.results
            if result.pipeline_result is not None
        )

    @property
    def event_fingerprints(self) -> tuple[str, ...]:
        return tuple(
            result.receipt.event_fingerprint
            for result in self.results
            if result.pipeline_result is not None
        )

    @property
    def duplicate_events(self) -> int:
        return sum(result.receipt.duplicate for result in self.pipeline_results)

    @property
    def timing_finding_count(self) -> int:
        return sum(len(result.timing_findings) for result in self.pipeline_results)

    @property
    def recommendation_count(self) -> int:
        return sum(len(result.recommendations) for result in self.pipeline_results)

    @property
    def transport_integrity_complete(self) -> bool:
        return self.rejected_events == 0


class StreamConsumer:
    """Admit integrity-valid envelopes to an unchanged LineAlert Core instance."""

    def __init__(self, core: LineAlertCore) -> None:
        self.core = core
        self._active_session_by_source: dict[str, str] = {}
        self._seen_sessions_by_source: dict[str, set[str]] = {}
        self._next_sequence_by_session: dict[tuple[str, str], int] = {}
        self._results: list[StreamResult] = []

    def consume(self, envelope: StreamEnvelope) -> StreamResult:
        """Process one envelope without repairing sequence or session evidence."""

        source_id = envelope.event.source_id
        active_session = self._active_session_by_source.get(source_id)
        seen_sessions = self._seen_sessions_by_source.setdefault(source_id, set())
        session_transition = active_session != envelope.session_id

        if active_session is None:
            if envelope.sequence_number != 0:
                return self._reject(
                    envelope,
                    StreamDisposition.REJECTED_SESSION_START,
                    expected=0,
                    session_transition=True,
                    uncertainty=(
                        "The first observed source session did not begin at sequence zero; "
                        "prior transport history may be missing."
                    ),
                )
            self._activate_session(source_id, envelope.session_id, seen_sessions)
        elif active_session != envelope.session_id:
            if envelope.session_id in seen_sessions:
                return self._reject(
                    envelope,
                    StreamDisposition.REJECTED_SESSION_REUSE,
                    expected=self._next_sequence_by_session.get(
                        (source_id, envelope.session_id),
                        0,
                    ),
                    session_transition=True,
                    uncertainty=(
                        "A previously superseded source session reappeared; continuity "
                        "with the active source session is not accepted."
                    ),
                )
            if envelope.sequence_number != 0:
                return self._reject(
                    envelope,
                    StreamDisposition.REJECTED_SESSION_START,
                    expected=0,
                    session_transition=True,
                    uncertainty=(
                        "A new source session did not begin at sequence zero; events "
                        "before this envelope may be missing."
                    ),
                )
            self._activate_session(source_id, envelope.session_id, seen_sessions)

        key = (source_id, envelope.session_id)
        expected = self._next_sequence_by_session[key]
        if envelope.sequence_number < expected:
            return self._reject(
                envelope,
                StreamDisposition.REJECTED_OUT_OF_ORDER,
                expected=expected,
                session_transition=session_transition,
                uncertainty=(
                    "The envelope sequence is older than the next accepted position; "
                    "the event was not silently reordered or admitted."
                ),
            )
        if envelope.sequence_number > expected:
            return self._reject(
                envelope,
                StreamDisposition.REJECTED_SEQUENCE_GAP,
                expected=expected,
                session_transition=session_transition,
                uncertainty=(
                    "One or more transport envelopes are missing; the event was not "
                    "admitted because downstream findings could otherwise omit evidence."
                ),
            )

        pipeline_result = self.core.ingest(envelope.event)
        self._next_sequence_by_session[key] = expected + 1
        receipt = StreamReceipt(
            source_id=source_id,
            session_id=envelope.session_id,
            sequence_number=envelope.sequence_number,
            expected_sequence_number=expected,
            received_at=envelope.received_at,
            event_id=envelope.event.event_id,
            event_fingerprint=envelope.event.fingerprint,
            disposition=StreamDisposition.ACCEPTED,
            session_transition=session_transition,
            retained_uncertainty=(
                "Transport admission proves only sequence and session integrity for the "
                "supplied envelope. The source timestamp and sensor value remain source evidence."
            ),
        )
        result = StreamResult(envelope=envelope, receipt=receipt, pipeline_result=pipeline_result)
        self._results.append(result)
        return result

    def consume_all(self, envelopes: Iterable[StreamEnvelope]) -> StreamSummary:
        for envelope in envelopes:
            self.consume(envelope)
        return self.summary()

    def summary(self) -> StreamSummary:
        return StreamSummary(
            results=tuple(self._results),
            machine_profile=self.core.machine_profile,
            topology_edges=self.core.topology.edges,
        )

    def _activate_session(
        self,
        source_id: str,
        session_id: str,
        seen_sessions: set[str],
    ) -> None:
        self._active_session_by_source[source_id] = session_id
        seen_sessions.add(session_id)
        self._next_sequence_by_session[(source_id, session_id)] = 0

    def _reject(
        self,
        envelope: StreamEnvelope,
        disposition: StreamDisposition,
        *,
        expected: int,
        session_transition: bool,
        uncertainty: str,
    ) -> StreamResult:
        receipt = StreamReceipt(
            source_id=envelope.event.source_id,
            session_id=envelope.session_id,
            sequence_number=envelope.sequence_number,
            expected_sequence_number=expected,
            received_at=envelope.received_at,
            event_id=envelope.event.event_id,
            event_fingerprint=envelope.event.fingerprint,
            disposition=disposition,
            session_transition=session_transition,
            retained_uncertainty=uncertainty,
        )
        result = StreamResult(envelope=envelope, receipt=receipt, pipeline_result=None)
        self._results.append(result)
        return result


def consume_stream(core: LineAlertCore, envelopes: Iterable[StreamEnvelope]) -> StreamSummary:
    """Consume one bounded stream using a fresh source-session tracker."""

    return StreamConsumer(core).consume_all(envelopes)


def stream_summary_to_dict(summary: StreamSummary) -> dict[str, Any]:
    """Return a machine-readable stream and deterministic-analysis report."""

    return {
        "machine_profile": _profile_to_dict(summary.machine_profile),
        "process_topology": {
            "dependencies": [
                {"from": edge.upstream, "to": edge.downstream}
                for edge in summary.topology_edges
            ]
        },
        "summary": {
            "transport_envelopes": len(summary.results),
            "accepted_events": summary.accepted_events,
            "rejected_events": summary.rejected_events,
            "duplicate_events": summary.duplicate_events,
            "timing_findings": summary.timing_finding_count,
            "recommendations": summary.recommendation_count,
            "transport_integrity_complete": summary.transport_integrity_complete,
        },
        "envelopes": [_stream_result_to_dict(result) for result in summary.results],
    }


def _profile_to_dict(profile: MachineProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "profile_id": profile.profile_id,
        "asset_id": profile.asset_id,
        "operating_modes": sorted(profile.operating_modes),
        "components": [
            {
                "component_id": component.component_id,
                "name": component.name,
                "component_type": component.component_type,
            }
            for component in profile.components
        ],
        "component_dependencies": [
            {
                "from": dependency.upstream_component,
                "to": dependency.downstream_component,
                "relationship": dependency.relationship,
            }
            for dependency in profile.component_dependencies
        ],
        "event_bindings": [
            {
                "event_type": binding.event_type,
                "component_id": binding.component_id,
            }
            for binding in profile.event_bindings
        ],
    }


def _stream_result_to_dict(result: StreamResult) -> dict[str, Any]:
    pipeline = result.pipeline_result
    return {
        "transport": {
            "source_id": result.receipt.source_id,
            "session_id": result.receipt.session_id,
            "sequence_number": result.receipt.sequence_number,
            "expected_sequence_number": result.receipt.expected_sequence_number,
            "received_at": result.receipt.received_at.isoformat(),
            "source_timestamp": result.envelope.event.timestamp.isoformat(),
            "clock_quality": result.envelope.clock_quality,
            "transport_attributes": dict(result.envelope.transport_attributes),
            "event_id": result.receipt.event_id,
            "event_fingerprint": result.receipt.event_fingerprint,
            "disposition": result.receipt.disposition.value,
            "session_transition": result.receipt.session_transition,
            "retained_uncertainty": result.receipt.retained_uncertainty,
        },
        "event": result.envelope.event.canonical_payload(),
        "pipeline_result": _pipeline_result_to_dict(pipeline) if pipeline is not None else None,
    }


def _pipeline_result_to_dict(result: PipelineResult) -> dict[str, Any]:
    return {
        "receipt": {
            "event_id": result.receipt.event_id,
            "delivered_to": list(result.receipt.delivered_to),
            "duplicate": result.receipt.duplicate,
        },
        "timing_findings": [
            {
                "rule_id": finding.rule_id,
                "asset_id": finding.asset_id,
                "correlation_id": finding.correlation_id,
                "start_timestamp": finding.start_timestamp.isoformat(),
                "end_timestamp": finding.end_timestamp.isoformat(),
                "delay_seconds": finding.delay_seconds,
                "min_delay_seconds": finding.min_delay_seconds,
                "max_delay_seconds": finding.max_delay_seconds,
                "status": finding.status.value,
                "topology_from": finding.topology_from,
                "topology_to": finding.topology_to,
            }
            for finding in result.timing_findings
        ],
        "recommendations": [
            {
                "rule_id": recommendation.rule_id,
                "summary": recommendation.summary,
                "interpretation": recommendation.interpretation,
                "topology": {
                    "upstream": recommendation.topology.upstream,
                    "downstream": recommendation.topology.downstream,
                    "upstream_dependencies": list(
                        recommendation.topology.upstream_dependencies
                    ),
                    "downstream_dependencies": list(
                        recommendation.topology.downstream_dependencies
                    ),
                },
                "recommended_checks": list(recommendation.recommended_checks),
                "retained_uncertainty": recommendation.retained_uncertainty,
            }
            for recommendation in result.recommendations
        ],
    }
