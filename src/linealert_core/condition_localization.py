"""Deterministic persistent-onset and dependency-window localization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from .topology import TopologyContext, TopologyGraph


class ConditionLocalizationError(ValueError):
    """Raised when history cannot be compared deterministically."""


class SampleEnvelopeState(StrEnum):
    WITHIN = "WITHIN"
    OUTSIDE = "OUTSIDE"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"


class LocalizationDisposition(StrEnum):
    PERSISTENCE_ESTABLISHED = "PERSISTENCE_ESTABLISHED"
    PERSISTENCE_NOT_ESTABLISHED = "PERSISTENCE_NOT_ESTABLISHED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"


class DependencyDirection(StrEnum):
    UPSTREAM = "UPSTREAM"
    DOWNSTREAM = "DOWNSTREAM"


class RelationshipWindowState(StrEnum):
    WITHIN_ENVELOPE = "WITHIN_ENVELOPE"
    INTERMITTENT_OUTSIDE = "INTERMITTENT_OUTSIDE"
    PERSISTENT_OUTSIDE = "PERSISTENT_OUTSIDE"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"
    NO_EVIDENCE = "NO_EVIDENCE"


@dataclass(frozen=True, slots=True)
class PersistenceRule:
    """N-of-M persistence requirement over chronological relationship samples."""

    required_outside: int
    window_size: int

    def __post_init__(self) -> None:
        if self.required_outside < 1:
            raise ConditionLocalizationError("required_outside must be at least 1")
        if self.window_size < 1:
            raise ConditionLocalizationError("window_size must be at least 1")
        if self.required_outside > self.window_size:
            raise ConditionLocalizationError("required_outside cannot exceed window_size")


@dataclass(frozen=True, slots=True)
class ConditionHistorySample:
    """One admitted relationship measurement from condition history."""

    observed_at: datetime
    observation_id: str
    asset_id: str
    relationship_id: str
    signal: str
    value: float
    unit: str
    min_value: float
    max_value: float
    temporal_rule_status: str
    quality: str
    correlation_id: str
    topology_from: str
    topology_to: str
    episode_id: str | None = None
    cycle_id: str | None = None

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ConditionLocalizationError("observed_at must be timezone-aware")
        for field_name in (
            "observation_id",
            "asset_id",
            "relationship_id",
            "signal",
            "unit",
            "temporal_rule_status",
            "quality",
            "correlation_id",
            "topology_from",
            "topology_to",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ConditionLocalizationError(f"{field_name} must be a non-empty string")
        if self.min_value > self.max_value:
            raise ConditionLocalizationError("min_value cannot exceed max_value")


@dataclass(frozen=True, slots=True)
class PersistenceOnset:
    """Earliest window in which the declared N-of-M rule becomes satisfied."""

    relationship_id: str
    first_outside_at: datetime
    candidate_start_at: datetime
    persistence_established_at: datetime
    window_start_at: datetime
    window_end_at: datetime
    outside_count: int
    window_count: int
    observation_ids: tuple[str, ...]
    cycle_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DependencyRelationshipState:
    relationship_id: str
    direction: DependencyDirection
    topology_from: str
    topology_to: str
    state: RelationshipWindowState
    sample_count: int
    good_count: int
    outside_count: int
    first_outside_at: datetime | None
    persistence_established_at: datetime | None


@dataclass(frozen=True, slots=True)
class DependencyLocalizationResult:
    asset_id: str
    target_relationship_id: str
    persistence_rule: PersistenceRule
    disposition: LocalizationDisposition
    target_topology: TopologyContext
    first_outside_at: datetime | None
    onset: PersistenceOnset | None
    analysis_window_start: datetime | None
    analysis_window_end: datetime | None
    upstream: tuple[DependencyRelationshipState, ...]
    downstream: tuple[DependencyRelationshipState, ...]
    reasons: tuple[str, ...]
    claim_boundary: str = (
        "Persistent timing deviation and dependency-window states localize retained "
        "operational evidence only. They do not establish physical root cause, causation, "
        "safe production change, or authorized maintenance action."
    )


def condition_history_sample_from_dict(raw: dict[str, Any]) -> ConditionHistorySample:
    """Rebuild one historian condition measurement without reinterpreting it."""

    required = (
        "observed_at",
        "observation_id",
        "asset_id",
        "relationship_id",
        "signal",
        "value",
        "unit",
        "min_value",
        "max_value",
        "temporal_rule_status",
        "quality",
        "correlation_id",
        "topology_from",
        "topology_to",
    )
    missing = [name for name in required if raw.get(name) is None]
    if missing:
        raise ConditionLocalizationError(
            "condition history sample missing fields: " + ", ".join(missing)
        )
    try:
        observed_at = datetime.fromisoformat(str(raw["observed_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConditionLocalizationError("observed_at must be ISO 8601") from exc
    return ConditionHistorySample(
        observed_at=observed_at,
        observation_id=str(raw["observation_id"]),
        episode_id=_optional_text(raw.get("episode_id")),
        asset_id=str(raw["asset_id"]),
        relationship_id=str(raw["relationship_id"]),
        signal=str(raw["signal"]),
        value=float(raw["value"]),
        unit=str(raw["unit"]),
        min_value=float(raw["min_value"]),
        max_value=float(raw["max_value"]),
        temporal_rule_status=str(raw["temporal_rule_status"]),
        quality=str(raw["quality"]),
        correlation_id=str(raw["correlation_id"]),
        cycle_id=_optional_text(raw.get("cycle_id")),
        topology_from=str(raw["topology_from"]),
        topology_to=str(raw["topology_to"]),
    )


class PersistentDependencyLocalizer:
    """Find earliest sustained target deviation and summarize dependency evidence."""

    def __init__(self, topology: TopologyGraph) -> None:
        self.topology = topology

    def localize(
        self,
        samples: tuple[ConditionHistorySample, ...],
        *,
        target_relationship_id: str,
        persistence_rule: PersistenceRule,
    ) -> DependencyLocalizationResult:
        if not target_relationship_id.strip():
            raise ConditionLocalizationError("target_relationship_id must be a non-empty string")
        ordered = tuple(sorted(samples, key=lambda item: (item.observed_at, item.observation_id)))
        target = tuple(item for item in ordered if item.relationship_id == target_relationship_id)
        if not target:
            raise ConditionLocalizationError(
                f"no samples for target relationship {target_relationship_id!r}"
            )

        asset_ids = {item.asset_id for item in ordered}
        if len(asset_ids) != 1:
            raise ConditionLocalizationError("localization requires samples from exactly one asset")
        self._validate_relationship_identity(target)
        target_context = self.topology.context_for_edge(
            target[0].topology_from,
            target[0].topology_to,
        )

        states = tuple(_sample_state(item) for item in target)
        first_outside = next(
            (
                item.observed_at
                for item, state in zip(target, states, strict=True)
                if state is SampleEnvelopeState.OUTSIDE
            ),
            None,
        )
        if SampleEnvelopeState.CONFLICT in states:
            return self._result(
                target=target,
                target_context=target_context,
                persistence_rule=persistence_rule,
                disposition=LocalizationDisposition.EVIDENCE_CONFLICT,
                first_outside=first_outside,
                onset=None,
                related=ordered,
                reasons=(
                    "Target history contains a conflict between numeric envelope state "
                    "and retained temporal-rule status.",
                ),
            )

        onset = _find_persistence(target, persistence_rule)
        if onset is not None:
            disposition = LocalizationDisposition.PERSISTENCE_ESTABLISHED
            reasons = (
                f"Persistence established by {onset.outside_count} outside samples "
                f"within a {onset.window_count}-sample window.",
            )
        elif len(target) < persistence_rule.window_size:
            disposition = LocalizationDisposition.INSUFFICIENT_EVIDENCE
            reasons = (
                "Target history contains fewer samples than the declared persistence window.",
            )
        elif _unresolved_can_change_persistence(target, persistence_rule):
            disposition = LocalizationDisposition.INSUFFICIENT_EVIDENCE
            reasons = (
                "Unresolved target samples could change whether the declared persistence "
                "rule is satisfied.",
            )
        else:
            disposition = LocalizationDisposition.PERSISTENCE_NOT_ESTABLISHED
            reasons = ("No complete target window satisfies the declared persistence rule.",)

        return self._result(
            target=target,
            target_context=target_context,
            persistence_rule=persistence_rule,
            disposition=disposition,
            first_outside=first_outside,
            onset=onset,
            related=ordered,
            reasons=reasons,
        )

    def _result(
        self,
        *,
        target: tuple[ConditionHistorySample, ...],
        target_context: TopologyContext,
        persistence_rule: PersistenceRule,
        disposition: LocalizationDisposition,
        first_outside: datetime | None,
        onset: PersistenceOnset | None,
        related: tuple[ConditionHistorySample, ...],
        reasons: tuple[str, ...],
    ) -> DependencyLocalizationResult:
        window_start: datetime | None
        window_end: datetime | None
        if onset is not None:
            window_start = onset.window_start_at
            window_end = onset.window_end_at
        else:
            window_start = target[0].observed_at if target else None
            window_end = target[-1].observed_at if target else None

        upstream_nodes = set(target_context.upstream_dependencies)
        upstream_nodes.add(target_context.upstream)
        downstream_nodes = set(target_context.downstream_dependencies)
        downstream_nodes.add(target_context.downstream)

        all_grouped: dict[str, list[ConditionHistorySample]] = {}
        for sample in related:
            if sample.relationship_id == target[0].relationship_id:
                continue
            all_grouped.setdefault(sample.relationship_id, []).append(sample)

        upstream: list[DependencyRelationshipState] = []
        downstream: list[DependencyRelationshipState] = []
        for _relationship_id, all_items in all_grouped.items():
            all_group = tuple(
                sorted(
                    all_items,
                    key=lambda item: (item.observed_at, item.observation_id),
                )
            )
            self._validate_relationship_identity(all_group)
            first = all_group[0]
            direction: DependencyDirection | None = None
            if first.topology_to in upstream_nodes:
                direction = DependencyDirection.UPSTREAM
            elif first.topology_from in downstream_nodes:
                direction = DependencyDirection.DOWNSTREAM
            if direction is None:
                continue

            window_group = tuple(
                item
                for item in all_group
                if (window_start is None or item.observed_at >= window_start)
                and (window_end is None or item.observed_at <= window_end)
            )
            state = (
                _summarize_related(window_group, direction, persistence_rule)
                if window_group
                else _no_evidence_related(first, direction)
            )
            if direction is DependencyDirection.UPSTREAM:
                upstream.append(state)
            else:
                downstream.append(state)

        def sort_key(
            item: DependencyRelationshipState,
        ) -> tuple[str, str, str]:
            return (item.topology_from, item.topology_to, item.relationship_id)

        return DependencyLocalizationResult(
            asset_id=target[0].asset_id,
            target_relationship_id=target[0].relationship_id,
            persistence_rule=persistence_rule,
            disposition=disposition,
            target_topology=target_context,
            first_outside_at=first_outside,
            onset=onset,
            analysis_window_start=window_start,
            analysis_window_end=window_end,
            upstream=tuple(sorted(upstream, key=sort_key)),
            downstream=tuple(sorted(downstream, key=sort_key)),
            reasons=reasons,
        )

    @staticmethod
    def _validate_relationship_identity(
        samples: tuple[ConditionHistorySample, ...],
    ) -> None:
        identities = {
            (
                item.asset_id,
                item.relationship_id,
                item.signal,
                item.unit,
                item.min_value,
                item.max_value,
                item.topology_from,
                item.topology_to,
            )
            for item in samples
        }
        if len(identities) != 1:
            raise ConditionLocalizationError(
                "one relationship history contains incompatible identity or envelope metadata"
            )


def _sample_state(sample: ConditionHistorySample) -> SampleEnvelopeState:
    if sample.quality != "good":
        return SampleEnvelopeState.UNRESOLVED
    numeric_outside = sample.value < sample.min_value or sample.value > sample.max_value
    status = sample.temporal_rule_status.lower()
    if status == "within":
        return SampleEnvelopeState.CONFLICT if numeric_outside else SampleEnvelopeState.WITHIN
    if status in {"early", "late"}:
        return SampleEnvelopeState.OUTSIDE if numeric_outside else SampleEnvelopeState.CONFLICT
    return SampleEnvelopeState.UNRESOLVED


def _find_persistence(
    samples: tuple[ConditionHistorySample, ...],
    rule: PersistenceRule,
) -> PersistenceOnset | None:
    if len(samples) < rule.window_size:
        return None
    states = tuple(_sample_state(item) for item in samples)
    first_outside_at = next(
        (
            item.observed_at
            for item, state in zip(samples, states, strict=True)
            if state is SampleEnvelopeState.OUTSIDE
        ),
        None,
    )
    if first_outside_at is None:
        return None

    for end_index in range(rule.window_size - 1, len(samples)):
        start_index = end_index - rule.window_size + 1
        window = samples[start_index : end_index + 1]
        window_states = states[start_index : end_index + 1]
        outside = tuple(
            item
            for item, state in zip(window, window_states, strict=True)
            if state is SampleEnvelopeState.OUTSIDE
        )
        if len(outside) < rule.required_outside:
            continue
        return PersistenceOnset(
            relationship_id=window[0].relationship_id,
            first_outside_at=first_outside_at,
            candidate_start_at=outside[0].observed_at,
            persistence_established_at=window[-1].observed_at,
            window_start_at=window[0].observed_at,
            window_end_at=window[-1].observed_at,
            outside_count=len(outside),
            window_count=len(window),
            observation_ids=tuple(item.observation_id for item in window),
            cycle_ids=tuple(item.cycle_id or item.correlation_id for item in window),
        )
    return None


def _unresolved_can_change_persistence(
    samples: tuple[ConditionHistorySample, ...],
    rule: PersistenceRule,
) -> bool:
    if len(samples) < rule.window_size:
        return True
    states = tuple(_sample_state(item) for item in samples)
    for end_index in range(rule.window_size - 1, len(samples)):
        start_index = end_index - rule.window_size + 1
        window_states = states[start_index : end_index + 1]
        outside = sum(state is SampleEnvelopeState.OUTSIDE for state in window_states)
        unresolved = sum(state is SampleEnvelopeState.UNRESOLVED for state in window_states)
        if outside < rule.required_outside <= outside + unresolved:
            return True
    return False


def _summarize_related(
    samples: tuple[ConditionHistorySample, ...],
    direction: DependencyDirection,
    rule: PersistenceRule,
) -> DependencyRelationshipState:
    states = tuple(_sample_state(item) for item in samples)
    good_count = sum(
        state in {SampleEnvelopeState.WITHIN, SampleEnvelopeState.OUTSIDE} for state in states
    )
    outside_count = sum(state is SampleEnvelopeState.OUTSIDE for state in states)
    first_outside_at = next(
        (
            item.observed_at
            for item, state in zip(samples, states, strict=True)
            if state is SampleEnvelopeState.OUTSIDE
        ),
        None,
    )
    onset = _find_persistence(samples, rule)

    if SampleEnvelopeState.CONFLICT in states:
        state = RelationshipWindowState.CONFLICT
    elif onset is not None:
        state = RelationshipWindowState.PERSISTENT_OUTSIDE
    elif outside_count:
        state = RelationshipWindowState.INTERMITTENT_OUTSIDE
    elif SampleEnvelopeState.UNRESOLVED in states:
        state = RelationshipWindowState.UNRESOLVED
    elif good_count:
        state = RelationshipWindowState.WITHIN_ENVELOPE
    else:
        state = RelationshipWindowState.NO_EVIDENCE

    first = samples[0]
    return DependencyRelationshipState(
        relationship_id=first.relationship_id,
        direction=direction,
        topology_from=first.topology_from,
        topology_to=first.topology_to,
        state=state,
        sample_count=len(samples),
        good_count=good_count,
        outside_count=outside_count,
        first_outside_at=first_outside_at,
        persistence_established_at=(
            onset.persistence_established_at if onset is not None else None
        ),
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConditionLocalizationError(
            "optional condition-history identity fields must be strings"
        )
    return value if value.strip() else None


def _no_evidence_related(
    sample: ConditionHistorySample,
    direction: DependencyDirection,
) -> DependencyRelationshipState:
    return DependencyRelationshipState(
        relationship_id=sample.relationship_id,
        direction=direction,
        topology_from=sample.topology_from,
        topology_to=sample.topology_to,
        state=RelationshipWindowState.NO_EVIDENCE,
        sample_count=0,
        good_count=0,
        outside_count=0,
        first_outside_at=None,
        persistence_established_at=None,
    )


def dependency_localization_to_dict(
    result: DependencyLocalizationResult,
) -> dict[str, object]:
    """Serialize the bounded localization result without diagnostic upgrade."""

    return {
        "schema_version": "linealert.condition-dependency-localization.v1",
        "asset_id": result.asset_id,
        "target_relationship_id": result.target_relationship_id,
        "disposition": result.disposition.value,
        "persistence_rule": {
            "required_outside": result.persistence_rule.required_outside,
            "window_size": result.persistence_rule.window_size,
        },
        "target_topology": {
            "upstream": result.target_topology.upstream,
            "downstream": result.target_topology.downstream,
            "upstream_dependencies": list(result.target_topology.upstream_dependencies),
            "downstream_dependencies": list(result.target_topology.downstream_dependencies),
        },
        "first_outside_at": (
            result.first_outside_at.isoformat() if result.first_outside_at is not None else None
        ),
        "onset": (
            {
                "relationship_id": result.onset.relationship_id,
                "first_outside_at": result.onset.first_outside_at.isoformat(),
                "candidate_start_at": result.onset.candidate_start_at.isoformat(),
                "persistence_established_at": (result.onset.persistence_established_at.isoformat()),
                "window_start_at": result.onset.window_start_at.isoformat(),
                "window_end_at": result.onset.window_end_at.isoformat(),
                "outside_count": result.onset.outside_count,
                "window_count": result.onset.window_count,
                "observation_ids": list(result.onset.observation_ids),
                "cycle_ids": list(result.onset.cycle_ids),
            }
            if result.onset is not None
            else None
        ),
        "analysis_window_start": (
            result.analysis_window_start.isoformat()
            if result.analysis_window_start is not None
            else None
        ),
        "analysis_window_end": (
            result.analysis_window_end.isoformat()
            if result.analysis_window_end is not None
            else None
        ),
        "upstream": [_dependency_state_to_dict(item) for item in result.upstream],
        "downstream": [_dependency_state_to_dict(item) for item in result.downstream],
        "reasons": list(result.reasons),
        "claim_boundary": result.claim_boundary,
    }


def _dependency_state_to_dict(
    item: DependencyRelationshipState,
) -> dict[str, object]:
    return {
        "relationship_id": item.relationship_id,
        "direction": item.direction.value,
        "topology_from": item.topology_from,
        "topology_to": item.topology_to,
        "state": item.state.value,
        "sample_count": item.sample_count,
        "good_count": item.good_count,
        "outside_count": item.outside_count,
        "first_outside_at": (
            item.first_outside_at.isoformat() if item.first_outside_at is not None else None
        ),
        "persistence_established_at": (
            item.persistence_established_at.isoformat()
            if item.persistence_established_at is not None
            else None
        ),
    }
