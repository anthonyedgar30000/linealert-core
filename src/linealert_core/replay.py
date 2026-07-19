"""Replay captured or simulated machine events through LineAlert Core."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .events import EventQuality, MachineEvent
from .pipeline import LineAlertCore, PipelineResult
from .timing import TemporalRule
from .topology import DependencyEdge, TopologyGraph


class ReplayInputError(ValueError):
    """Raised when replay input or configuration is malformed."""


@dataclass(frozen=True, slots=True)
class ReplaySummary:
    """Deterministic results from replaying an ordered event stream."""

    results: tuple[PipelineResult, ...]

    @property
    def total_events(self) -> int:
        return len(self.results)

    @property
    def duplicate_events(self) -> int:
        return sum(result.receipt.duplicate for result in self.results)

    @property
    def timing_finding_count(self) -> int:
        return sum(len(result.timing_findings) for result in self.results)

    @property
    def recommendation_count(self) -> int:
        return sum(len(result.recommendations) for result in self.results)


def load_events(path: str | Path, *, input_format: str = "auto") -> tuple[MachineEvent, ...]:
    """Load ordered machine events from JSON Lines or CSV."""

    source_path = Path(path)
    selected_format = _resolve_format(source_path, input_format)
    if selected_format == "jsonl":
        return _load_jsonl_events(source_path)
    if selected_format == "csv":
        return _load_csv_events(source_path)
    raise ReplayInputError(f"unsupported replay format: {selected_format}")


def build_core_from_config(path: str | Path) -> LineAlertCore:
    """Build a deterministic core from a JSON replay configuration."""

    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReplayInputError(
            f"{config_path}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(raw, dict):
        raise ReplayInputError(f"{config_path}: configuration must be a JSON object")

    topology_raw = raw.get("topology")
    if not isinstance(topology_raw, dict):
        raise ReplayInputError(f"{config_path}: topology must be an object")
    dependencies_raw = topology_raw.get("dependencies")
    if not isinstance(dependencies_raw, list) or not dependencies_raw:
        raise ReplayInputError(f"{config_path}: topology.dependencies must be a non-empty list")

    edges = [
        DependencyEdge(
            upstream=_required_text(item, "from", f"topology dependency {index}"),
            downstream=_required_text(item, "to", f"topology dependency {index}"),
        )
        for index, item in enumerate(dependencies_raw, start=1)
    ]

    rules_raw = raw.get("temporal_rules")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise ReplayInputError(f"{config_path}: temporal_rules must be a non-empty list")

    rules = [
        TemporalRule(
            rule_id=_required_text(item, "rule_id", f"temporal rule {index}"),
            start_event=_required_text(item, "start_event", f"temporal rule {index}"),
            end_event=_required_text(item, "end_event", f"temporal rule {index}"),
            min_delay_seconds=_required_number(
                item,
                "min_delay_seconds",
                f"temporal rule {index}",
            ),
            max_delay_seconds=_required_number(
                item,
                "max_delay_seconds",
                f"temporal rule {index}",
            ),
            topology_from=_required_text(
                item,
                "topology_from",
                f"temporal rule {index}",
            ),
            topology_to=_required_text(
                item,
                "topology_to",
                f"temporal rule {index}",
            ),
        )
        for index, item in enumerate(rules_raw, start=1)
    ]

    topology = TopologyGraph(edges)
    for rule in rules:
        if not topology.has_edge(rule.topology_from, rule.topology_to):
            raise ReplayInputError(
                f"{config_path}: rule {rule.rule_id!r} references unknown topology edge "
                f"{rule.topology_from} -> {rule.topology_to}"
            )

    return LineAlertCore(rules=rules, topology=topology)


def replay_events(core: LineAlertCore, events: Iterable[MachineEvent]) -> ReplaySummary:
    """Ingest events in supplied order and retain every deterministic result."""

    return ReplaySummary(results=tuple(core.ingest(event) for event in events))


def summary_to_dict(summary: ReplaySummary) -> dict[str, Any]:
    """Return a JSON-compatible replay report."""

    return {
        "summary": {
            "total_events": summary.total_events,
            "duplicate_events": summary.duplicate_events,
            "timing_findings": summary.timing_finding_count,
            "recommendations": summary.recommendation_count,
        },
        "events": [_result_to_dict(result) for result in summary.results],
    }


def _load_jsonl_events(path: Path) -> tuple[MachineEvent, ...]:
    events: list[MachineEvent] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReplayInputError(
                    f"{path}:{line_number}: invalid JSON at column {exc.colno}"
                ) from exc
            events.append(_event_from_mapping(raw, location=f"{path}:{line_number}"))
    return tuple(events)


def _load_csv_events(path: Path) -> tuple[MachineEvent, ...]:
    events: list[MachineEvent] = []
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ReplayInputError(f"{path}: CSV header is required")
        for line_number, raw in enumerate(reader, start=2):
            events.append(_event_from_mapping(raw, location=f"{path}:{line_number}"))
    return tuple(events)


def _event_from_mapping(raw: object, *, location: str) -> MachineEvent:
    if not isinstance(raw, Mapping):
        raise ReplayInputError(f"{location}: event must be an object")

    timestamp_text = _required_text(raw, "timestamp", location)
    try:
        timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReplayInputError(f"{location}: timestamp must be ISO 8601") from exc

    value = _optional_number(raw, "value", location)
    unit = _optional_text(raw, "unit")
    quality_text = _optional_text(raw, "quality") or EventQuality.GOOD.value
    try:
        quality = EventQuality(quality_text)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in EventQuality)
        raise ReplayInputError(f"{location}: quality must be one of {allowed}") from exc

    attributes = _parse_attributes(raw.get("attributes"), location)

    try:
        return MachineEvent(
            event_id=_required_text(raw, "event_id", location),
            source_id=_required_text(raw, "source_id", location),
            asset_id=_required_text(raw, "asset_id", location),
            component_id=_required_text(raw, "component_id", location),
            event_type=_required_text(raw, "event_type", location),
            timestamp=timestamp,
            correlation_id=_required_text(raw, "correlation_id", location),
            value=value,
            unit=unit,
            quality=quality,
            attributes=attributes,
        )
    except ValueError as exc:
        raise ReplayInputError(f"{location}: {exc}") from exc


def _parse_attributes(raw: object, location: str) -> Mapping[str, Any]:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ReplayInputError(f"{location}: attributes must contain valid JSON") from exc
    if not isinstance(raw, Mapping):
        raise ReplayInputError(f"{location}: attributes must be an object")
    return dict(raw)


def _resolve_format(path: Path, input_format: str) -> str:
    normalized = input_format.lower()
    if normalized not in {"auto", "jsonl", "csv"}:
        raise ReplayInputError("input_format must be auto, jsonl, or csv")
    if normalized != "auto":
        return normalized
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        return "jsonl"
    if path.suffix.lower() == ".csv":
        return "csv"
    raise ReplayInputError(f"cannot infer format from {path}; pass jsonl or csv explicitly")


def _required_text(raw: object, field: str, location: str) -> str:
    if not isinstance(raw, Mapping):
        raise ReplayInputError(f"{location}: must be an object")
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ReplayInputError(f"{location}: {field} must be a non-empty string")
    return value.strip()


def _optional_text(raw: Mapping[str, object], field: str) -> str | None:
    value = raw.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ReplayInputError(f"{field} must be a string when supplied")
    return value.strip() or None


def _required_number(raw: object, field: str, location: str) -> float:
    if not isinstance(raw, Mapping):
        raise ReplayInputError(f"{location}: must be an object")
    value = raw.get(field)
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ReplayInputError(f"{location}: {field} must be numeric") from exc
    return number


def _optional_number(raw: Mapping[str, object], field: str, location: str) -> float | None:
    value = raw.get(field)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ReplayInputError(f"{location}: {field} must be numeric when supplied") from exc


def _result_to_dict(result: PipelineResult) -> dict[str, Any]:
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
