from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from linealert_core.condition_localization import (
    ConditionHistorySample,
    ConditionLocalizationError,
    DependencyDirection,
    LocalizationDisposition,
    PersistenceRule,
    PersistentDependencyLocalizer,
    RelationshipWindowState,
    condition_history_sample_from_dict,
    dependency_localization_to_dict,
)
from linealert_core.topology import DependencyEdge, TopologyGraph

BASE = datetime(2026, 9, 14, 11, 37, tzinfo=UTC)


def topology() -> TopologyGraph:
    return TopologyGraph(
        [
            DependencyEdge("BottleDetected", "SpacingConfirmed"),
            DependencyEdge("SpacingConfirmed", "AlignmentConfirmed"),
            DependencyEdge("WebTensionStable", "LabelFeedCommand"),
            DependencyEdge("AlignmentConfirmed", "LabelFeedCommand"),
            DependencyEdge("LabelFeedCommand", "LabelAtPeelPoint"),
            DependencyEdge("LabelAtPeelPoint", "InitialContact"),
        ]
    )


def sample(
    *,
    relationship_id: str,
    offset_seconds: int,
    value: float,
    topology_from: str,
    topology_to: str,
    min_value: float = 50.0,
    max_value: float = 350.0,
    status: str | None = None,
    quality: str = "good",
    unit: str = "ms",
    asset_id: str = "LABELER-DEMO-01",
) -> ConditionHistorySample:
    outside = value < min_value or value > max_value
    retained_status = status or ("late" if outside else "within")
    return ConditionHistorySample(
        observed_at=BASE + timedelta(seconds=offset_seconds),
        observation_id=f"{relationship_id}:{offset_seconds}",
        episode_id="episode-42",
        asset_id=asset_id,
        relationship_id=relationship_id,
        signal=f"{relationship_id}:signal",
        value=value,
        unit=unit,
        min_value=min_value,
        max_value=max_value,
        temporal_rule_status=retained_status,
        quality=quality,
        correlation_id=f"cycle-{offset_seconds}",
        cycle_id=f"cycle-{offset_seconds}",
        topology_from=topology_from,
        topology_to=topology_to,
    )


def target_samples(values: list[float]) -> tuple[ConditionHistorySample, ...]:
    return tuple(
        sample(
            relationship_id="relationship:label-presentation-delay",
            offset_seconds=index * 60,
            value=value,
            topology_from="LabelFeedCommand",
            topology_to="LabelAtPeelPoint",
        )
        for index, value in enumerate(values)
    )


def test_persistence_is_established_at_end_of_earliest_qualifying_window() -> None:
    samples = target_samples([200.0, 500.0, 510.0, 520.0, 210.0])
    result = PersistentDependencyLocalizer(topology()).localize(
        samples,
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
    )

    assert result.disposition is LocalizationDisposition.PERSISTENCE_ESTABLISHED
    assert result.first_outside_at == BASE + timedelta(seconds=60)
    assert result.onset is not None
    assert result.onset.candidate_start_at == BASE + timedelta(seconds=60)
    assert result.onset.persistence_established_at == BASE + timedelta(seconds=180)
    assert result.onset.window_start_at == BASE
    assert result.onset.window_end_at == BASE + timedelta(seconds=180)
    assert result.onset.outside_count == 3
    assert result.onset.window_count == 4
    assert result.onset.cycle_ids == (
        "cycle-0",
        "cycle-60",
        "cycle-120",
        "cycle-180",
    )
    assert "do not establish physical root cause" in result.claim_boundary


def test_first_outside_is_not_same_claim_as_persistence_established() -> None:
    samples = target_samples([500.0, 200.0, 210.0, 500.0, 510.0, 520.0])
    result = PersistentDependencyLocalizer(topology()).localize(
        samples,
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
    )

    assert result.onset is not None
    assert result.first_outside_at == BASE
    assert result.onset.candidate_start_at == BASE + timedelta(seconds=180)
    assert result.onset.persistence_established_at == BASE + timedelta(seconds=300)
    assert result.first_outside_at < result.onset.persistence_established_at


def test_isolated_outside_samples_do_not_establish_persistence() -> None:
    samples = target_samples([200.0, 500.0, 210.0, 220.0, 500.0, 230.0])
    result = PersistentDependencyLocalizer(topology()).localize(
        samples,
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
    )

    assert result.disposition is LocalizationDisposition.PERSISTENCE_NOT_ESTABLISHED
    assert result.onset is None
    assert result.first_outside_at == BASE + timedelta(seconds=60)


def test_unresolved_samples_that_could_change_result_are_insufficient() -> None:
    samples = list(target_samples([500.0, 500.0, 200.0, 200.0]))
    samples[2] = sample(
        relationship_id="relationship:label-presentation-delay",
        offset_seconds=120,
        value=500.0,
        topology_from="LabelFeedCommand",
        topology_to="LabelAtPeelPoint",
        quality="suspect",
    )
    result = PersistentDependencyLocalizer(topology()).localize(
        tuple(samples),
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
    )

    assert result.disposition is LocalizationDisposition.INSUFFICIENT_EVIDENCE
    assert result.onset is None
    assert "could change" in result.reasons[0]


def test_conflicting_numeric_and_retained_status_is_preserved_as_conflict() -> None:
    samples = list(target_samples([200.0, 500.0, 510.0, 520.0]))
    samples[1] = sample(
        relationship_id="relationship:label-presentation-delay",
        offset_seconds=60,
        value=500.0,
        topology_from="LabelFeedCommand",
        topology_to="LabelAtPeelPoint",
        status="within",
    )
    result = PersistentDependencyLocalizer(topology()).localize(
        tuple(samples),
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
    )

    assert result.disposition is LocalizationDisposition.EVIDENCE_CONFLICT
    assert result.onset is None
    assert "conflict" in result.reasons[0]


def test_dependency_window_classifies_upstream_and_downstream_evidence() -> None:
    target = target_samples([200.0, 500.0, 510.0, 520.0])
    upstream_within = tuple(
        sample(
            relationship_id="relationship:alignment-feed",
            offset_seconds=index * 60,
            value=100.0,
            min_value=0.0,
            max_value=200.0,
            topology_from="AlignmentConfirmed",
            topology_to="LabelFeedCommand",
        )
        for index in range(4)
    )
    shared_upstream_intermittent = tuple(
        sample(
            relationship_id="relationship:web-ready-feed",
            offset_seconds=index * 60,
            value=value,
            min_value=0.0,
            max_value=1000.0,
            topology_from="WebTensionStable",
            topology_to="LabelFeedCommand",
        )
        for index, value in enumerate([500.0, 1200.0, 500.0, 500.0])
    )
    downstream_persistent = tuple(
        sample(
            relationship_id="relationship:initial-contact",
            offset_seconds=index * 60,
            value=value,
            min_value=0.0,
            max_value=150.0,
            topology_from="LabelAtPeelPoint",
            topology_to="InitialContact",
        )
        for index, value in enumerate([100.0, 200.0, 210.0, 220.0])
    )
    old_upstream_only = (
        sample(
            relationship_id="relationship:spacing-alignment",
            offset_seconds=-60,
            value=100.0,
            min_value=50.0,
            max_value=500.0,
            topology_from="SpacingConfirmed",
            topology_to="AlignmentConfirmed",
        ),
    )

    result = PersistentDependencyLocalizer(topology()).localize(
        target
        + upstream_within
        + shared_upstream_intermittent
        + downstream_persistent
        + old_upstream_only,
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
    )

    upstream = {item.relationship_id: item for item in result.upstream}
    downstream = {item.relationship_id: item for item in result.downstream}

    assert upstream["relationship:alignment-feed"].direction is DependencyDirection.UPSTREAM
    assert upstream["relationship:alignment-feed"].state is (
        RelationshipWindowState.WITHIN_ENVELOPE
    )
    assert upstream["relationship:web-ready-feed"].state is (
        RelationshipWindowState.INTERMITTENT_OUTSIDE
    )
    assert upstream["relationship:spacing-alignment"].state is (RelationshipWindowState.NO_EVIDENCE)
    assert upstream["relationship:spacing-alignment"].sample_count == 0

    assert downstream["relationship:initial-contact"].direction is (DependencyDirection.DOWNSTREAM)
    assert downstream["relationship:initial-contact"].state is (
        RelationshipWindowState.PERSISTENT_OUTSIDE
    )
    assert downstream["relationship:initial-contact"].outside_count == 3
    assert downstream["relationship:initial-contact"].persistence_established_at == (
        BASE + timedelta(seconds=180)
    )


def test_unrelated_relationship_is_not_presented_as_dependency_evidence() -> None:
    target = target_samples([200.0, 500.0, 510.0, 520.0])
    unrelated = tuple(
        sample(
            relationship_id="relationship:other",
            offset_seconds=index * 60,
            value=500.0,
            topology_from="UnrelatedStart",
            topology_to="UnrelatedEnd",
        )
        for index in range(4)
    )

    result = PersistentDependencyLocalizer(topology()).localize(
        target + unrelated,
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
    )

    assert result.upstream == ()
    assert result.downstream == ()


def test_history_payload_parser_preserves_exact_identity_and_time() -> None:
    raw = {
        "observed_at": "2026-09-14T11:42:03Z",
        "observation_id": "obs-42",
        "episode_id": "episode-42",
        "asset_id": "LABELER-DEMO-01",
        "relationship_id": "relationship:label-presentation-delay",
        "signal": "label_presentation_delay_ms",
        "value": 550.0,
        "unit": "ms",
        "min_value": 50.0,
        "max_value": 350.0,
        "temporal_rule_status": "late",
        "quality": "good",
        "correlation_id": "cycle-42",
        "cycle_id": "cycle-42",
        "topology_from": "LabelFeedCommand",
        "topology_to": "LabelAtPeelPoint",
    }

    parsed = condition_history_sample_from_dict(raw)

    assert parsed.observed_at.isoformat() == "2026-09-14T11:42:03+00:00"
    assert parsed.relationship_id == raw["relationship_id"]
    assert parsed.cycle_id == "cycle-42"
    assert parsed.value == 550.0


def test_incompatible_target_envelope_metadata_is_refused() -> None:
    samples = list(target_samples([200.0, 500.0, 510.0, 520.0]))
    samples[-1] = sample(
        relationship_id="relationship:label-presentation-delay",
        offset_seconds=180,
        value=520.0,
        topology_from="LabelFeedCommand",
        topology_to="LabelAtPeelPoint",
        max_value=400.0,
    )

    with pytest.raises(ConditionLocalizationError, match="incompatible identity"):
        PersistentDependencyLocalizer(topology()).localize(
            tuple(samples),
            target_relationship_id="relationship:label-presentation-delay",
            persistence_rule=PersistenceRule(required_outside=3, window_size=4),
        )


def test_persistence_rule_rejects_impossible_n_of_m() -> None:
    with pytest.raises(ConditionLocalizationError, match="cannot exceed"):
        PersistenceRule(required_outside=5, window_size=4)


def test_localization_serializer_preserves_onset_and_dependency_states() -> None:
    target = target_samples([200.0, 500.0, 510.0, 520.0])
    upstream = tuple(
        sample(
            relationship_id="relationship:alignment-feed",
            offset_seconds=index * 60,
            value=100.0,
            min_value=0.0,
            max_value=200.0,
            topology_from="AlignmentConfirmed",
            topology_to="LabelFeedCommand",
        )
        for index in range(4)
    )
    result = PersistentDependencyLocalizer(topology()).localize(
        target + upstream,
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
    )

    payload = dependency_localization_to_dict(result)

    assert payload["schema_version"] == "linealert.condition-dependency-localization.v1"
    assert payload["disposition"] == "PERSISTENCE_ESTABLISHED"
    assert payload["first_outside_at"] == (BASE + timedelta(seconds=60)).isoformat()
    onset = payload["onset"]
    assert isinstance(onset, dict)
    assert onset["persistence_established_at"] == (BASE + timedelta(seconds=180)).isoformat()
    upstream_payload = payload["upstream"]
    assert isinstance(upstream_payload, list)
    assert upstream_payload[0]["state"] == "WITHIN_ENVELOPE"


def test_condition_localization_types_are_exported_from_public_api() -> None:
    import linealert_core

    assert linealert_core.PersistentDependencyLocalizer is PersistentDependencyLocalizer
    assert linealert_core.PersistenceRule is PersistenceRule
    assert linealert_core.LocalizationDisposition is LocalizationDisposition
    assert linealert_core.RelationshipWindowState is RelationshipWindowState
    assert linealert_core.condition_history_sample_from_dict is (condition_history_sample_from_dict)
    assert linealert_core.dependency_localization_to_dict is (dependency_localization_to_dict)
