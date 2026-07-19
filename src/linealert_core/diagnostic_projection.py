"""Symptom-first diagnostic projection grounded in governed guide knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .machine import MachineProfile
from .timing import TimingFinding, TimingStatus
from .topology import DependencyEdge, TopologyContext, TopologyGraph


class DiagnosticProjectionError(ValueError):
    """Raised when diagnostic knowledge or a request is invalid."""


class CheckDisposition(StrEnum):
    """How supplied timing evidence affects one guide-authored check."""

    EVIDENCE_ALIGNED = "evidence_aligned"
    GUIDE_ONLY = "guide_only"
    DEPRIORITIZED_BY_HEALTHY_EVIDENCE = "deprioritized_by_healthy_evidence"


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    """One expert-authored inspection path for a symptom."""

    check_id: str
    prompt: str
    component_ids: tuple[str, ...]
    related_edges: tuple[DependencyEdge, ...]
    safe_next_action: str

    def __post_init__(self) -> None:
        for field_name in ("check_id", "prompt", "safe_next_action"):
            value = getattr(self, field_name)
            if not value.strip():
                raise DiagnosticProjectionError(f"{field_name} must not be empty")
        if not self.component_ids:
            raise DiagnosticProjectionError(
                "diagnostic check requires at least one component"
            )
        if any(not component_id.strip() for component_id in self.component_ids):
            raise DiagnosticProjectionError(
                "diagnostic component IDs must not be empty"
            )
        if len(self.component_ids) != len(set(self.component_ids)):
            raise DiagnosticProjectionError(
                "diagnostic component IDs must be unique"
            )
        if len(self.related_edges) != len(set(self.related_edges)):
            raise DiagnosticProjectionError(
                "diagnostic related edges must be unique"
            )


@dataclass(frozen=True, slots=True)
class SymptomDefinition:
    """Governed troubleshooting knowledge for one operator-visible symptom."""

    symptom_id: str
    title: str
    examples: tuple[str, ...]
    checks: tuple[DiagnosticCheck, ...]
    escalation_triggers: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.symptom_id.strip() or not self.title.strip():
            raise DiagnosticProjectionError(
                "symptom_id and title must not be empty"
            )
        if not self.checks:
            raise DiagnosticProjectionError(
                "symptom requires at least one diagnostic check"
            )
        check_ids = [check.check_id for check in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise DiagnosticProjectionError(
                "diagnostic check IDs must be unique per symptom"
            )
        if any(not example.strip() for example in self.examples):
            raise DiagnosticProjectionError("symptom examples must not be empty")
        if any(not trigger.strip() for trigger in self.escalation_triggers):
            raise DiagnosticProjectionError(
                "escalation triggers must not be empty"
            )


@dataclass(frozen=True, slots=True)
class DiagnosticGuide:
    """Versioned expert knowledge used to build diagnostic projections."""

    guide_id: str
    version: str
    symptoms: tuple[SymptomDefinition, ...]

    def __post_init__(self) -> None:
        if not self.guide_id.strip() or not self.version.strip():
            raise DiagnosticProjectionError(
                "guide_id and version must not be empty"
            )
        if not self.symptoms:
            raise DiagnosticProjectionError(
                "diagnostic guide requires at least one symptom"
            )
        symptom_ids = [symptom.symptom_id for symptom in self.symptoms]
        if len(symptom_ids) != len(set(symptom_ids)):
            raise DiagnosticProjectionError(
                "diagnostic symptom IDs must be unique"
            )

    def symptom(self, symptom_id: str) -> SymptomDefinition:
        """Return one declared symptom or fail explicitly."""

        for symptom in self.symptoms:
            if symptom.symptom_id == symptom_id:
                return symptom
        raise DiagnosticProjectionError(
            f"symptom {symptom_id!r} is not declared by guide "
            f"{self.guide_id!r}"
        )

    def validate_against(
        self,
        *,
        machine_profile: MachineProfile,
        topology: TopologyGraph,
    ) -> None:
        """Ensure guide references apply to the loaded machine definition."""

        for symptom in self.symptoms:
            for check in symptom.checks:
                for component_id in check.component_ids:
                    if component_id not in machine_profile.component_ids:
                        raise DiagnosticProjectionError(
                            f"check {check.check_id!r} references unknown "
                            f"component {component_id!r}"
                        )
                for edge in check.related_edges:
                    if not topology.has_edge(edge.upstream, edge.downstream):
                        raise DiagnosticProjectionError(
                            f"check {check.check_id!r} references unknown "
                            f"topology edge {edge.upstream} -> {edge.downstream}"
                        )


@dataclass(frozen=True, slots=True)
class OperatorReport:
    """Human-reported issue timeline and operating context."""

    symptom_id: str
    reported_start: datetime | None
    description: str
    operating_mode: str | None = None
    observations: tuple[str, ...] = ()
    recent_changes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.symptom_id.strip() or not self.description.strip():
            raise DiagnosticProjectionError(
                "symptom_id and description must not be empty"
            )
        if self.reported_start is not None:
            if (
                self.reported_start.tzinfo is None
                or self.reported_start.utcoffset() is None
            ):
                raise DiagnosticProjectionError(
                    "reported_start must be timezone-aware"
                )
        if self.operating_mode is not None and not self.operating_mode.strip():
            raise DiagnosticProjectionError("operating_mode must not be empty")
        if any(not observation.strip() for observation in self.observations):
            raise DiagnosticProjectionError(
                "operator observations must not be empty"
            )
        if any(not change.strip() for change in self.recent_changes):
            raise DiagnosticProjectionError("recent changes must not be empty")


@dataclass(frozen=True, slots=True)
class DiagnosticCheckAssessment:
    """One guide check ranked against the supplied timing evidence."""

    check_id: str
    prompt: str
    disposition: CheckDisposition
    component_ids: tuple[str, ...]
    evidence: tuple[str, ...]
    safe_next_action: str


@dataclass(frozen=True, slots=True)
class DiagnosticProjection:
    """Reverse-facing, symptom-first view of one investigation."""

    guide_id: str
    guide_version: str
    symptom_id: str
    symptom_title: str
    symptom_examples: tuple[str, ...]
    operator_report: OperatorReport
    first_observed_deviation: TimingFinding | None
    investigation_region: TopologyContext | None
    abnormal_relationships: tuple[TimingFinding, ...]
    healthy_relationships: tuple[TimingFinding, ...]
    check_assessments: tuple[DiagnosticCheckAssessment, ...]
    escalation_triggers: tuple[str, ...]
    retained_uncertainty: str


class DiagnosticProjectionEngine:
    """Project governed symptom knowledge onto supplied operational evidence."""

    def __init__(
        self,
        *,
        guide: DiagnosticGuide,
        machine_profile: MachineProfile,
        topology: TopologyGraph,
    ) -> None:
        guide.validate_against(
            machine_profile=machine_profile,
            topology=topology,
        )
        self.guide = guide
        self.machine_profile = machine_profile
        self.topology = topology

    def project(
        self,
        *,
        operator_report: OperatorReport,
        timing_findings: tuple[TimingFinding, ...],
    ) -> DiagnosticProjection:
        """Build one deterministic diagnostic view without inferring causality."""

        symptom = self.guide.symptom(operator_report.symptom_id)
        self._validate_report(operator_report)

        abnormal = tuple(
            sorted(
                (
                    finding
                    for finding in timing_findings
                    if finding.status is not TimingStatus.WITHIN
                ),
                key=lambda finding: (
                    finding.start_timestamp,
                    finding.end_timestamp,
                    finding.rule_id,
                ),
            )
        )
        healthy = tuple(
            sorted(
                (
                    finding
                    for finding in timing_findings
                    if finding.status is TimingStatus.WITHIN
                ),
                key=lambda finding: (
                    finding.start_timestamp,
                    finding.end_timestamp,
                    finding.rule_id,
                ),
            )
        )
        first = abnormal[0] if abnormal else None
        region = (
            self.topology.context_for_edge(
                first.topology_from,
                first.topology_to,
            )
            if first is not None
            else None
        )

        assessments = tuple(
            sorted(
                (
                    self._assess_check(check, timing_findings)
                    for check in symptom.checks
                ),
                key=lambda assessment: (
                    _DISPOSITION_ORDER[assessment.disposition],
                    _check_order(symptom, assessment.check_id),
                ),
            )
        )

        return DiagnosticProjection(
            guide_id=self.guide.guide_id,
            guide_version=self.guide.version,
            symptom_id=symptom.symptom_id,
            symptom_title=symptom.title,
            symptom_examples=symptom.examples,
            operator_report=operator_report,
            first_observed_deviation=first,
            investigation_region=region,
            abnormal_relationships=abnormal,
            healthy_relationships=healthy,
            check_assessments=assessments,
            escalation_triggers=symptom.escalation_triggers,
            retained_uncertainty=(
                "This projection ranks expert-authored checks against the supplied "
                "operator report and timing findings. It does not establish a root "
                "cause, infer when degradation began, or approve a new normal."
            ),
        )

    def _validate_report(self, report: OperatorReport) -> None:
        if (
            report.operating_mode is not None
            and self.machine_profile.operating_modes
            and report.operating_mode not in self.machine_profile.operating_modes
        ):
            allowed = ", ".join(sorted(self.machine_profile.operating_modes))
            raise DiagnosticProjectionError(
                f"operating mode {report.operating_mode!r} is not approved; "
                f"expected one of: {allowed}"
            )

    def _assess_check(
        self,
        check: DiagnosticCheck,
        findings: tuple[TimingFinding, ...],
    ) -> DiagnosticCheckAssessment:
        matching = tuple(
            finding
            for finding in findings
            if any(
                finding.topology_from == edge.upstream
                and finding.topology_to == edge.downstream
                for edge in check.related_edges
            )
        )
        abnormal = tuple(
            finding
            for finding in matching
            if finding.status is not TimingStatus.WITHIN
        )

        if abnormal:
            disposition = CheckDisposition.EVIDENCE_ALIGNED
            evidence = tuple(
                (
                    f"{finding.topology_from} -> {finding.topology_to} observed "
                    f"{finding.delay_seconds:.3f}s against "
                    f"{finding.min_delay_seconds:.3f}-"
                    f"{finding.max_delay_seconds:.3f}s "
                    f"({finding.status.value})."
                )
                for finding in abnormal
            )
        elif matching:
            disposition = CheckDisposition.DEPRIORITIZED_BY_HEALTHY_EVIDENCE
            evidence = tuple(
                (
                    f"{finding.topology_from} -> {finding.topology_to} remained "
                    f"within its supplied timing envelope."
                )
                for finding in matching
            )
        else:
            disposition = CheckDisposition.GUIDE_ONLY
            evidence = (
                "The guide identifies this check, but the supplied timing evidence "
                "does not directly assess its related relationships.",
            )

        return DiagnosticCheckAssessment(
            check_id=check.check_id,
            prompt=check.prompt,
            disposition=disposition,
            component_ids=check.component_ids,
            evidence=evidence,
            safe_next_action=check.safe_next_action,
        )


_DISPOSITION_ORDER = {
    CheckDisposition.EVIDENCE_ALIGNED: 0,
    CheckDisposition.GUIDE_ONLY: 1,
    CheckDisposition.DEPRIORITIZED_BY_HEALTHY_EVIDENCE: 2,
}


def _check_order(symptom: SymptomDefinition, check_id: str) -> int:
    return next(
        index
        for index, check in enumerate(symptom.checks)
        if check.check_id == check_id
    )
