"""Small deterministic LineAlert vertical slice."""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import DiagnosticEngine, DiagnosticRecommendation
from .events import MachineEvent
from .mosaic import EventReceipt, FusionMosaic, Subscription
from .timing import TemporalRule, TimingFinding, TimingMonitor
from .topology import TopologyGraph


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """All deterministic outputs caused by publishing one event."""

    receipt: EventReceipt
    timing_findings: tuple[TimingFinding, ...]
    recommendations: tuple[DiagnosticRecommendation, ...]


class LineAlertCore:
    """Typed event routing, timing evaluation, and bounded recommendations."""

    def __init__(
        self,
        *,
        rules: list[TemporalRule],
        topology: TopologyGraph,
    ) -> None:
        self.mosaic = FusionMosaic()
        self.timing_monitor = TimingMonitor(rules)
        self.diagnostics = DiagnosticEngine(topology)

        self.mosaic.register(
            Subscription(
                name="timing-monitor",
                event_types=self.timing_monitor.event_types,
                handler=self.timing_monitor.handle,
            )
        )

    def ingest(self, event: MachineEvent) -> PipelineResult:
        receipt = self.mosaic.publish(event)
        findings = tuple(
            output.value
            for output in receipt.outputs
            if isinstance(output.value, TimingFinding)
        )
        recommendations = tuple(
            recommendation
            for finding in findings
            if (recommendation := self.diagnostics.recommend(finding)) is not None
        )
        return PipelineResult(
            receipt=receipt,
            timing_findings=findings,
            recommendations=recommendations,
        )
