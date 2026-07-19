"""Bounded, topology-aware diagnostic recommendations."""

from __future__ import annotations

from dataclasses import dataclass

from .timing import TimingFinding, TimingStatus
from .topology import TopologyContext, TopologyGraph


@dataclass(frozen=True, slots=True)
class DiagnosticRecommendation:
    """A justified next check without pretending to establish root cause."""

    rule_id: str
    summary: str
    interpretation: str
    topology: TopologyContext
    recommended_checks: tuple[str, ...]
    retained_uncertainty: str


class DiagnosticEngine:
    """Translate timing drift into low-risk topology-aware checks."""

    def __init__(self, topology: TopologyGraph) -> None:
        self._topology = topology

    def recommend(
        self,
        finding: TimingFinding,
    ) -> DiagnosticRecommendation | None:
        if finding.status is TimingStatus.WITHIN:
            return None

        context = self._topology.context_for_edge(
            finding.topology_from,
            finding.topology_to,
        )
        direction = "longer" if finding.status is TimingStatus.LATE else "shorter"
        summary = (
            f"{finding.topology_from} -> {finding.topology_to} took "
            f"{finding.delay_seconds:.3f}s, {direction} than the approved "
            f"{finding.min_delay_seconds:.3f}-{finding.max_delay_seconds:.3f}s envelope."
        )

        return DiagnosticRecommendation(
            rule_id=finding.rule_id,
            summary=summary,
            interpretation=(
                "Timing drift is observed at this process relationship; "
                "the physical or logical cause remains unresolved."
            ),
            topology=context,
            recommended_checks=(
                f"Inspect {context.upstream} and its immediate operating state.",
                (
                    f"Inspect the handoff from {context.upstream} to "
                    f"{context.downstream} before changing settings."
                ),
                "Compare the same relationship in a matched healthy cycle.",
            ),
            retained_uncertainty=(
                "The timing relationship localizes the first observed deviation; "
                "it does not prove a root cause."
            ),
        )
