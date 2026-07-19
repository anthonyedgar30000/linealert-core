"""JSON loading and reporting for diagnostic projections."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .diagnostic_projection import (
    DiagnosticCheck,
    DiagnosticGuide,
    DiagnosticProjection,
    DiagnosticProjectionEngine,
    DiagnosticProjectionError,
    OperatorReport,
    SymptomDefinition,
)
from .machine import MachineProfile
from .pipeline import PipelineResult
from .timing import TimingFinding
from .topology import DependencyEdge, TopologyGraph


def load_diagnostic_engine(
    path: str | Path,
    *,
    machine_profile: MachineProfile | None,
    topology: TopologyGraph,
) -> DiagnosticProjectionEngine:
    """Load and validate a governed diagnostic guide."""

    if machine_profile is None:
        raise DiagnosticProjectionError(
            "diagnostic projection requires an approved machine profile"
        )
    guide_path = Path(path)
    raw = _read_json_object(guide_path, "diagnostic guide")
    guide = _parse_guide(raw, guide_path)
    return DiagnosticProjectionEngine(
        guide=guide,
        machine_profile=machine_profile,
        topology=topology,
    )


def load_operator_report(path: str | Path) -> OperatorReport:
    """Load one operator-reported issue timeline from JSON."""

    report_path = Path(path)
    raw = _read_json_object(report_path, "operator report")
    start_raw = raw.get("reported_start")
    if start_raw is None:
        reported_start = None
    else:
        start_text = _required_text(raw, "reported_start", str(report_path))
        try:
            reported_start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DiagnosticProjectionError(
                f"{report_path}: reported_start must be ISO 8601"
            ) from exc

    return OperatorReport(
        symptom_id=_required_text(raw, "symptom_id", str(report_path)),
        reported_start=reported_start,
        description=_required_text(raw, "description", str(report_path)),
        operating_mode=_optional_text(raw, "operating_mode", str(report_path)),
        observations=_string_tuple(raw.get("observations", []), "observations", report_path),
        recent_changes=_string_tuple(
            raw.get("recent_changes", []),
            "recent_changes",
            report_path,
        ),
    )


def collect_timing_findings(
    results: Iterable[PipelineResult],
) -> tuple[TimingFinding, ...]:
    """Flatten timing findings from an ordered replay."""

    return tuple(finding for result in results for finding in result.timing_findings)


def projection_to_dict(projection: DiagnosticProjection) -> dict[str, Any]:
    """Return a machine-readable diagnostic projection."""

    first = projection.first_observed_deviation
    region = projection.investigation_region
    return {
        "guide": {
            "guide_id": projection.guide_id,
            "version": projection.guide_version,
        },
        "symptom": {
            "symptom_id": projection.symptom_id,
            "title": projection.symptom_title,
            "examples": list(projection.symptom_examples),
        },
        "operator_report": {
            "reported_start": (
                projection.operator_report.reported_start.isoformat()
                if projection.operator_report.reported_start is not None
                else None
            ),
            "description": projection.operator_report.description,
            "operating_mode": projection.operator_report.operating_mode,
            "observations": list(projection.operator_report.observations),
            "recent_changes": list(projection.operator_report.recent_changes),
        },
        "first_observed_deviation": (
            _finding_to_dict(first) if first is not None else None
        ),
        "investigation_region": (
            {
                "upstream": region.upstream,
                "downstream": region.downstream,
                "upstream_dependencies": list(region.upstream_dependencies),
                "downstream_dependencies": list(region.downstream_dependencies),
            }
            if region is not None
            else None
        ),
        "abnormal_relationships": [
            _finding_to_dict(finding) for finding in projection.abnormal_relationships
        ],
        "healthy_relationships": [
            _finding_to_dict(finding) for finding in projection.healthy_relationships
        ],
        "ranked_checks": [
            {
                "check_id": assessment.check_id,
                "prompt": assessment.prompt,
                "disposition": assessment.disposition.value,
                "component_ids": list(assessment.component_ids),
                "evidence": list(assessment.evidence),
                "safe_next_action": assessment.safe_next_action,
            }
            for assessment in projection.check_assessments
        ],
        "escalation_triggers": list(projection.escalation_triggers),
        "retained_uncertainty": projection.retained_uncertainty,
    }


def _parse_guide(raw: Mapping[str, object], path: Path) -> DiagnosticGuide:
    symptoms_raw = raw.get("symptoms")
    if not isinstance(symptoms_raw, list) or not symptoms_raw:
        raise DiagnosticProjectionError(f"{path}: symptoms must be a non-empty list")

    symptoms = tuple(
        _parse_symptom(item, index, path)
        for index, item in enumerate(symptoms_raw, start=1)
    )
    return DiagnosticGuide(
        guide_id=_required_text(raw, "guide_id", str(path)),
        version=_required_text(raw, "version", str(path)),
        symptoms=symptoms,
    )


def _parse_symptom(
    raw: object,
    index: int,
    path: Path,
) -> SymptomDefinition:
    location = f"{path}: symptom {index}"
    if not isinstance(raw, Mapping):
        raise DiagnosticProjectionError(f"{location} must be an object")

    checks_raw = raw.get("checks")
    if not isinstance(checks_raw, list) or not checks_raw:
        raise DiagnosticProjectionError(f"{location}: checks must be a non-empty list")
    checks = tuple(
        _parse_check(item, check_index, location)
        for check_index, item in enumerate(checks_raw, start=1)
    )
    return SymptomDefinition(
        symptom_id=_required_text(raw, "symptom_id", location),
        title=_required_text(raw, "title", location),
        examples=_string_tuple(raw.get("examples", []), "examples", path),
        checks=checks,
        escalation_triggers=_string_tuple(
            raw.get("escalation_triggers", []),
            "escalation_triggers",
            path,
        ),
    )


def _parse_check(
    raw: object,
    index: int,
    symptom_location: str,
) -> DiagnosticCheck:
    location = f"{symptom_location}, check {index}"
    if not isinstance(raw, Mapping):
        raise DiagnosticProjectionError(f"{location} must be an object")

    edges_raw = raw.get("related_edges", [])
    if not isinstance(edges_raw, list):
        raise DiagnosticProjectionError(f"{location}: related_edges must be a list")
    edges = tuple(
        DependencyEdge(
            upstream=_required_text(item, "from", f"{location}, edge {edge_index}"),
            downstream=_required_text(item, "to", f"{location}, edge {edge_index}"),
        )
        for edge_index, item in enumerate(edges_raw, start=1)
    )

    component_ids = _string_tuple(
        raw.get("component_ids", []),
        "component_ids",
        Path(location),
    )
    return DiagnosticCheck(
        check_id=_required_text(raw, "check_id", location),
        prompt=_required_text(raw, "prompt", location),
        component_ids=component_ids,
        related_edges=edges,
        safe_next_action=_required_text(raw, "safe_next_action", location),
    )


def _read_json_object(path: Path, description: str) -> Mapping[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DiagnosticProjectionError(
            f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise DiagnosticProjectionError(f"{path}: {description} must be an object")
    return raw


def _required_text(raw: object, field: str, location: str) -> str:
    if not isinstance(raw, Mapping):
        raise DiagnosticProjectionError(f"{location}: must be an object")
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DiagnosticProjectionError(
            f"{location}: {field} must be a non-empty string"
        )
    return value.strip()


def _optional_text(
    raw: Mapping[str, object],
    field: str,
    location: str,
) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise DiagnosticProjectionError(
            f"{location}: {field} must be a non-empty string when supplied"
        )
    return value.strip()


def _string_tuple(
    raw: object,
    field: str,
    path: Path,
) -> tuple[str, ...]:
    if not isinstance(raw, list) or any(not isinstance(value, str) for value in raw):
        raise DiagnosticProjectionError(f"{path}: {field} must be a list of strings")
    return tuple(value.strip() for value in raw)


def _finding_to_dict(finding: TimingFinding) -> dict[str, Any]:
    return {
        "rule_id": finding.rule_id,
        "asset_id": finding.asset_id,
        "correlation_id": finding.correlation_id,
        "start_timestamp": finding.start_timestamp.isoformat(),
        "end_timestamp": finding.end_timestamp.isoformat(),
        "delay_seconds": finding.delay_seconds,
        "approved_min_seconds": finding.min_delay_seconds,
        "approved_max_seconds": finding.max_delay_seconds,
        "status": finding.status.value,
        "from": finding.topology_from,
        "to": finding.topology_to,
    }
