"""Incremental condition-signal projection for admitted machine-event streams."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .condition_projection import (
    ConditionProjectionError,
    ConditionSignalObservation,
    ConditionSignalProjection,
    TimingConditionBinding,
    condition_signal_projection_to_dict,
    project_timing_finding,
)
from .pipeline import LineAlertCore
from .streaming import (
    StreamConsumer,
    StreamEnvelope,
    StreamResult,
    StreamSummary,
    stream_summary_to_dict,
)
from .timing import TimingFinding


@dataclass(frozen=True, slots=True)
class LiveClockEvidence:
    """Clock evidence retained alongside one measured event-pair interval."""

    start_clock_quality: str
    end_clock_quality: str
    basis: str
    retained_uncertainty: str


@dataclass(frozen=True, slots=True)
class LiveConditionMeasurement:
    """One condition observation plus the transport-clock basis used to admit it."""

    observation: ConditionSignalObservation
    clock_evidence: LiveClockEvidence


@dataclass(frozen=True, slots=True)
class LiveConditionRefusal:
    """Evidence explaining why a timing finding was not promoted to a live signal."""

    rule_id: str
    correlation_id: str
    start_event_id: str | None
    end_event_id: str | None
    start_source_id: str | None
    end_source_id: str | None
    start_clock_quality: str | None
    end_clock_quality: str | None
    reason_code: str
    retained_uncertainty: str


@dataclass(frozen=True, slots=True)
class LiveConditionResult:
    """One admitted or rejected stream envelope and any condition evidence it produced."""

    stream_result: StreamResult
    measurements: tuple[LiveConditionMeasurement, ...]
    refusals: tuple[LiveConditionRefusal, ...]


@dataclass(frozen=True, slots=True)
class LiveConditionSummary:
    """Accumulated transport, timing, and bounded condition evidence from one live run."""

    results: tuple[LiveConditionResult, ...]
    stream_summary: StreamSummary
    bindings: tuple[TimingConditionBinding, ...]

    @property
    def measurements(self) -> tuple[LiveConditionMeasurement, ...]:
        return tuple(
            measurement
            for result in self.results
            for measurement in result.measurements
        )

    @property
    def refusals(self) -> tuple[LiveConditionRefusal, ...]:
        return tuple(refusal for result in self.results for refusal in result.refusals)

    @property
    def measurement_count(self) -> int:
        return len(self.measurements)

    @property
    def refusal_count(self) -> int:
        return len(self.refusals)


class LiveConditionConsumer:
    """Project exact timing findings as they emerge from an integrity-checked event stream."""

    def __init__(
        self,
        core: LineAlertCore,
        bindings: tuple[TimingConditionBinding, ...],
    ) -> None:
        if not bindings:
            raise ConditionProjectionError("at least one condition signal binding is required")
        by_rule = {binding.rule_id: binding for binding in bindings}
        by_signal = {binding.signal_name: binding for binding in bindings}
        if len(by_rule) != len(bindings):
            raise ConditionProjectionError("condition signal rule IDs must be unique")
        if len(by_signal) != len(bindings):
            raise ConditionProjectionError("condition signal names must be unique")

        self._stream = StreamConsumer(core)
        self._bindings = bindings
        self._bindings_by_rule = by_rule
        self._event_transport: dict[str, tuple[str, str]] = {}
        self._results: list[LiveConditionResult] = []

    def consume(self, envelope: StreamEnvelope) -> LiveConditionResult:
        """Consume one transport envelope and project newly completed timing relationships."""

        stream_result = self._stream.consume(envelope)
        pipeline_result = stream_result.pipeline_result
        if pipeline_result is None:
            result = LiveConditionResult(stream_result, (), ())
            self._results.append(result)
            return result

        if not pipeline_result.receipt.duplicate:
            self._event_transport[envelope.event.event_id] = (
                envelope.event.source_id,
                envelope.clock_quality,
            )

        measurements: list[LiveConditionMeasurement] = []
        refusals: list[LiveConditionRefusal] = []
        for finding in pipeline_result.timing_findings:
            binding = self._bindings_by_rule.get(finding.rule_id)
            if binding is None:
                continue
            clock_evidence, refusal = self._qualify_clock_basis(finding)
            if refusal is not None:
                refusals.append(refusal)
                continue
            if clock_evidence is None:
                raise AssertionError("clock qualification returned no evidence or refusal")
            measurements.append(
                LiveConditionMeasurement(
                    observation=project_timing_finding(finding, binding),
                    clock_evidence=clock_evidence,
                )
            )

        result = LiveConditionResult(
            stream_result=stream_result,
            measurements=tuple(measurements),
            refusals=tuple(refusals),
        )
        self._results.append(result)
        return result

    def consume_all(self, envelopes: Iterable[StreamEnvelope]) -> LiveConditionSummary:
        for envelope in envelopes:
            self.consume(envelope)
        return self.summary()

    def summary(self) -> LiveConditionSummary:
        return LiveConditionSummary(
            results=tuple(self._results),
            stream_summary=self._stream.summary(),
            bindings=self._bindings,
        )

    def _qualify_clock_basis(
        self,
        finding: TimingFinding,
    ) -> tuple[LiveClockEvidence | None, LiveConditionRefusal | None]:
        start = self._event_transport.get(finding.start_event_id or "")
        end = self._event_transport.get(finding.end_event_id or "")
        if start is None or end is None:
            return None, LiveConditionRefusal(
                rule_id=finding.rule_id,
                correlation_id=finding.correlation_id,
                start_event_id=finding.start_event_id,
                end_event_id=finding.end_event_id,
                start_source_id=finding.start_source_id,
                end_source_id=finding.end_source_id,
                start_clock_quality=start[1] if start else None,
                end_clock_quality=end[1] if end else None,
                reason_code="EVIDENCE.RELATIONSHIP_CLOCK_EVIDENCE_MISSING",
                retained_uncertainty=(
                    "The timing engine completed a relationship, but live transport-clock "
                    "evidence for both source events was not retained."
                ),
            )

        start_source, start_clock = start
        end_source, end_clock = end
        if start_source != end_source and (
            start_clock != "synchronized" or end_clock != "synchronized"
        ):
            return None, LiveConditionRefusal(
                rule_id=finding.rule_id,
                correlation_id=finding.correlation_id,
                start_event_id=finding.start_event_id,
                end_event_id=finding.end_event_id,
                start_source_id=start_source,
                end_source_id=end_source,
                start_clock_quality=start_clock,
                end_clock_quality=end_clock,
                reason_code="EVIDENCE.RELATIONSHIP_CROSS_SOURCE_CLOCK_UNQUALIFIED",
                retained_uncertainty=(
                    "A cross-source interval requires both transport clocks to be declared "
                    "synchronized; the timing finding is retained but not promoted to a live "
                    "condition signal."
                ),
            )

        if start_source == end_source:
            return LiveClockEvidence(
                start_clock_quality=start_clock,
                end_clock_quality=end_clock,
                basis="same_source_relative_interval",
                retained_uncertainty=(
                    "The interval uses timestamps from one source clock. Synchronization to "
                    "wall time is not required for this relative interval and is not claimed."
                ),
            ), None

        return LiveClockEvidence(
            start_clock_quality=start_clock,
            end_clock_quality=end_clock,
            basis="synchronized_cross_source_interval",
            retained_uncertainty=(
                "Both source transports declared synchronized clocks. External clock "
                "correctness is not independently proven by LineAlert."
            ),
        ), None


def consume_live_condition_stream(
    core: LineAlertCore,
    envelopes: Iterable[StreamEnvelope],
    bindings: tuple[TimingConditionBinding, ...],
) -> LiveConditionSummary:
    """Consume one bounded stream and return condition measurements as they were admitted."""

    return LiveConditionConsumer(core, bindings).consume_all(envelopes)


def live_condition_summary_to_dict(summary: LiveConditionSummary) -> dict[str, Any]:
    """Return transport and condition evidence without upgrading it into failure prediction."""

    projection = ConditionSignalProjection(
        bindings=summary.bindings,
        observations=tuple(
            measurement.observation for measurement in summary.measurements
        ),
    )
    condition_payload = condition_signal_projection_to_dict(projection)
    clock_by_observation = {
        measurement.observation.observation_id: measurement.clock_evidence
        for measurement in summary.measurements
    }
    for observation in condition_payload["observations"]:
        clock = clock_by_observation[observation["observation_id"]]
        observation["clock_evidence"] = {
            "start_clock_quality": clock.start_clock_quality,
            "end_clock_quality": clock.end_clock_quality,
            "basis": clock.basis,
            "retained_uncertainty": clock.retained_uncertainty,
        }

    return {
        "schema_version": "linealert.live-condition-stream.v1",
        "claim_boundary": (
            "Live measurements are exact intervals between admitted correlated machine "
            "events, subject to retained transport and clock evidence. They do not establish "
            "physical root cause, component health, remaining useful life, or future failure."
        ),
        "stream": stream_summary_to_dict(summary.stream_summary),
        "condition_signals": condition_payload,
        "refusals": [
            {
                "rule_id": refusal.rule_id,
                "correlation_id": refusal.correlation_id,
                "start_event_id": refusal.start_event_id,
                "end_event_id": refusal.end_event_id,
                "start_source_id": refusal.start_source_id,
                "end_source_id": refusal.end_source_id,
                "start_clock_quality": refusal.start_clock_quality,
                "end_clock_quality": refusal.end_clock_quality,
                "reason_code": refusal.reason_code,
                "retained_uncertainty": refusal.retained_uncertainty,
            }
            for refusal in summary.refusals
        ],
    }
