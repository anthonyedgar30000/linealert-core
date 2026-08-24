"""Project measured timing findings into bounded condition-monitoring signals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .events import EventQuality
from .replay import ReplaySummary
from .timing import TimingFinding


class ConditionProjectionError(ValueError):
    """Raised when a condition-signal projection contract is invalid."""


@dataclass(frozen=True, slots=True)
class TimingConditionBinding:
    """Explicit mapping from one timing rule to one named condition signal."""

    signal_name: str
    rule_id: str
    semantic: str
    scope: str
    unit: str = "ms"

    def __post_init__(self) -> None:
        for field_name in ("signal_name", "rule_id", "semantic", "scope", "unit"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ConditionProjectionError(f"{field_name} must be a non-empty string")
        if self.unit not in {"ms", "s"}:
            raise ConditionProjectionError("condition signal unit must be 'ms' or 's'")

    @property
    def relationship_id(self) -> str:
        """Return a stable identifier for the measured event relationship."""

        return f"relationship:{self.rule_id}"


@dataclass(frozen=True, slots=True)
class ConditionSignalObservation:
    """One measured event-pair delay projected as condition-monitoring evidence."""

    signal_name: str
    value: float
    unit: str
    min_value: float
    max_value: float
    asset_id: str
    rule_id: str
    correlation_id: str
    source_timestamp: str
    start_timestamp: str
    end_timestamp: str
    topology_from: str
    topology_to: str
    temporal_rule_status: str
    semantic: str
    scope: str
    relationship_id: str
    observation_id: str
    quality: str
    reason_code: str
    start_event_id: str | None
    end_event_id: str | None
    start_source_id: str | None
    end_source_id: str | None


@dataclass(frozen=True, slots=True)
class ConditionSignalProjection:
    """All bounded condition-signal observations projected from one replay."""

    bindings: tuple[TimingConditionBinding, ...]
    observations: tuple[ConditionSignalObservation, ...]


def _convert_seconds(value: float, unit: str) -> float:
    if unit == "s":
        return value
    if unit == "ms":
        return value * 1000.0
    raise ConditionProjectionError(f"unsupported condition signal unit {unit!r}")


def _combined_quality(finding: TimingFinding) -> tuple[str, str]:
    qualities = (finding.start_quality, finding.end_quality)
    if EventQuality.BAD in qualities:
        return "bad", "EVIDENCE.RELATIONSHIP_INPUT_BAD"
    if EventQuality.SUSPECT in qualities:
        return "suspect", "EVIDENCE.RELATIONSHIP_INPUT_SUSPECT"
    if EventQuality.UNKNOWN in qualities:
        return "unknown", "EVIDENCE.RELATIONSHIP_INPUT_UNKNOWN"
    return "good", "EVIDENCE.RELATIONSHIP_DELAY_MEASURED"


def project_timing_finding(
    finding: TimingFinding,
    binding: TimingConditionBinding,
) -> ConditionSignalObservation:
    """Project one exact timing finding without upgrading it into a diagnosis."""

    if finding.rule_id != binding.rule_id:
        raise ConditionProjectionError(
            f"binding for rule {binding.rule_id!r} cannot project finding "
            f"for rule {finding.rule_id!r}"
        )

    end_timestamp = finding.end_timestamp.isoformat()
    observation_id = (
        f"{finding.asset_id}:{finding.correlation_id}:"
        f"{binding.signal_name}:{end_timestamp}"
    )
    quality, reason_code = _combined_quality(finding)
    return ConditionSignalObservation(
        signal_name=binding.signal_name,
        value=_convert_seconds(finding.delay_seconds, binding.unit),
        unit=binding.unit,
        min_value=_convert_seconds(finding.min_delay_seconds, binding.unit),
        max_value=_convert_seconds(finding.max_delay_seconds, binding.unit),
        asset_id=finding.asset_id,
        rule_id=finding.rule_id,
        correlation_id=finding.correlation_id,
        source_timestamp=end_timestamp,
        start_timestamp=finding.start_timestamp.isoformat(),
        end_timestamp=end_timestamp,
        topology_from=finding.topology_from,
        topology_to=finding.topology_to,
        temporal_rule_status=finding.status.value,
        semantic=binding.semantic,
        scope=binding.scope,
        relationship_id=binding.relationship_id,
        observation_id=observation_id,
        quality=quality,
        reason_code=reason_code,
        start_event_id=finding.start_event_id,
        end_event_id=finding.end_event_id,
        start_source_id=finding.start_source_id,
        end_source_id=finding.end_source_id,
    )


def project_replay_condition_signals(
    summary: ReplaySummary,
    bindings: tuple[TimingConditionBinding, ...],
) -> ConditionSignalProjection:
    """Project configured timing findings from replayed or captured event evidence."""

    if not bindings:
        raise ConditionProjectionError("at least one condition signal binding is required")
    by_rule = {binding.rule_id: binding for binding in bindings}
    if len(by_rule) != len(bindings):
        raise ConditionProjectionError("condition signal rule IDs must be unique")

    observations: list[ConditionSignalObservation] = []
    for pipeline_result in summary.results:
        for finding in pipeline_result.timing_findings:
            binding = by_rule.get(finding.rule_id)
            if binding is not None:
                observations.append(project_timing_finding(finding, binding))

    return ConditionSignalProjection(
        bindings=bindings,
        observations=tuple(observations),
    )


def load_condition_signal_bindings(
    path: str | Path,
) -> tuple[TimingConditionBinding, ...]:
    """Load explicit timing-rule to condition-signal mappings from JSON."""

    source_path = Path(path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConditionProjectionError(
            f"{source_path}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(raw, dict):
        raise ConditionProjectionError(f"{source_path}: binding document must be an object")
    if raw.get("schema_version") != "linealert.condition-signal-bindings.v1":
        raise ConditionProjectionError(f"{source_path}: unsupported binding schema")

    bindings_raw = raw.get("bindings")
    if not isinstance(bindings_raw, list) or not bindings_raw:
        raise ConditionProjectionError(f"{source_path}: bindings must be a non-empty list")

    bindings: list[TimingConditionBinding] = []
    for index, item in enumerate(bindings_raw, start=1):
        location = f"{source_path}: binding {index}"
        if not isinstance(item, dict):
            raise ConditionProjectionError(f"{location}: binding must be an object")
        bindings.append(
            TimingConditionBinding(
                signal_name=_required_text(item, "signal_name", location),
                rule_id=_required_text(item, "rule_id", location),
                semantic=_required_text(item, "semantic", location),
                scope=_required_text(item, "scope", location),
                unit=_optional_text(item, "unit") or "ms",
            )
        )

    signal_names = [binding.signal_name for binding in bindings]
    rule_ids = [binding.rule_id for binding in bindings]
    if len(signal_names) != len(set(signal_names)):
        raise ConditionProjectionError("condition signal names must be unique")
    if len(rule_ids) != len(set(rule_ids)):
        raise ConditionProjectionError("condition signal rule IDs must be unique")
    return tuple(bindings)


def condition_signal_projection_to_dict(
    projection: ConditionSignalProjection,
) -> dict[str, Any]:
    """Return a JSON-compatible evidence section for a replay report."""

    return {
        "schema_version": "linealert.condition-signal-projection.v1",
        "claim_boundary": (
            "Measured correlated-event delay only. This does not establish physical root cause, "
            "component health, remaining useful life, or future failure."
        ),
        "count": len(projection.observations),
        "bindings": [
            {
                "signal_name": binding.signal_name,
                "rule_id": binding.rule_id,
                "semantic": binding.semantic,
                "scope": binding.scope,
                "unit": binding.unit,
                "relationship_id": binding.relationship_id,
            }
            for binding in projection.bindings
        ],
        "observations": [
            {
                "signal": observation.signal_name,
                "value": observation.value,
                "unit": observation.unit,
                "min_value": observation.min_value,
                "max_value": observation.max_value,
                "asset_id": observation.asset_id,
                "rule_id": observation.rule_id,
                "correlation_id": observation.correlation_id,
                "source_timestamp": observation.source_timestamp,
                "start_timestamp": observation.start_timestamp,
                "end_timestamp": observation.end_timestamp,
                "start_event_id": observation.start_event_id,
                "end_event_id": observation.end_event_id,
                "start_source_id": observation.start_source_id,
                "end_source_id": observation.end_source_id,
                "topology_from": observation.topology_from,
                "topology_to": observation.topology_to,
                "temporal_rule_status": observation.temporal_rule_status,
                "semantic": observation.semantic,
                "scope": observation.scope,
                "relationship_id": observation.relationship_id,
                "observation_id": observation.observation_id,
                "quality": observation.quality,
                "reason_code": observation.reason_code,
                "provenance": "correlated_machine_event_source_timestamps",
            }
            for observation in projection.observations
        ],
    }


def _required_text(raw: dict[str, Any], field: str, location: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ConditionProjectionError(f"{location}: {field} must be a non-empty string")
    return value.strip()


def _optional_text(raw: dict[str, Any], field: str) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConditionProjectionError(f"{field} must be a string when supplied")
    return value.strip() or None
