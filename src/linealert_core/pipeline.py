"""Small deterministic LineAlert vertical slice."""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostic_projection import (
    DiagnosticGuide,
    DiagnosticProjection,
    DiagnosticProjectionEngine,
    DiagnosticProjectionError,
    OperatorReport,
)
from .diagnostics import DiagnosticEngine, DiagnosticRecommendation
from .events import MachineEvent
from .machine import MachineProfile
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
    """Typed event routing, applicability checks, and bounded recommendations."""

    def __init__(
        self,
        *,
        rules: list[TemporalRule],
        topology: TopologyGraph,
        machine_profile: MachineProfile | None = None,
        diagnostic_guide: DiagnosticGuide | None = None,
    ) -> None:
        if diagnostic_guide is not None and machine_profile is None:
            raise DiagnosticProjectionError(
                "diagnostic guide requires an approved machine profile"
            )

        self.machine_profile = machine_profile
        self.topology = topology
        self.diagnostic_guide = diagnostic_guide
        self.mosaic = FusionMosaic()
        self.timing_monitor = TimingMonitor(rules)
        self.diagnostics = DiagnosticEngine(topology)
        self.diagnostic_projection_engine = (
            DiagnosticProjectionEngine(
                guide=diagnostic_guide,
                machine_profile=machine_profile,
                topology=topology,
            )
            if diagnostic_guide is not None and machine_profile is not None
            else None
        )

        self.mosaic.register(
            Subscription(
                name="timing-monitor",
                event_types=self.timing_monitor.event_types,
                handler=self.timing_monitor.handle,
            )
        )

    def ingest(self, event: MachineEvent) -> PipelineResult:
        if self.machine_profile is not None:
            self.machine_profile.validate_event(event)

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

    def project_diagnostic(
        self,
        *,
        operator_report: OperatorReport,
        timing_findings: tuple[TimingFinding, ...],
    ) -> DiagnosticProjection:
        """Build a symptom-first diagnostic view from supplied findings."""

        if self.diagnostic_projection_engine is None:
            raise DiagnosticProjectionError(
                "the loaded configuration does not define a diagnostic guide"
            )
        return self.diagnostic_projection_engine.project(
            operator_report=operator_report,
            timing_findings=timing_findings,
        )
