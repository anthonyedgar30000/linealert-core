from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from linealert_core.condition_history_selection import (
    ConditionHistorianSelector,
    ConditionHistorySelectionError,
    ConditionHistorySelectionSpec,
    ConditionLocalizationHandoffDisposition,
    selected_condition_localization_to_dict,
)
from linealert_core.condition_localization import (
    LocalizationDisposition,
    PersistenceRule,
    RelationshipWindowState,
)
from linealert_core.historian import ConditionHistoryRecord
from linealert_core.topology import DependencyEdge, TopologyGraph

BASE = datetime(2026, 9, 14, 11, 37, tzinfo=UTC)


def topology() -> TopologyGraph:
    return TopologyGraph(
        [
            DependencyEdge("SpacingConfirmed", "AlignmentConfirmed"),
            DependencyEdge("AlignmentConfirmed", "LabelFeedCommand"),
            DependencyEdge("WebTensionStable", "LabelFeedCommand"),
            DependencyEdge("LabelFeedCommand", "LabelAtPeelPoint"),
            DependencyEdge("LabelAtPeelPoint", "InitialContact"),
        ]
    )


def record(
    *,
    relationship_id: str,
    offset_seconds: int,
    value: float,
    topology_from: str,
    topology_to: str,
    min_value: float = 50.0,
    max_value: float = 350.0,
    operating_context: dict[str, object] | None = None,
    asset_id: str = "LABELER-DEMO-01",
) -> ConditionHistoryRecord:
    outside = value < min_value or value > max_value
    return ConditionHistoryRecord(
        observed_at=BASE + timedelta(seconds=offset_seconds),
        observation_id=f"{relationship_id}:{offset_seconds}",
        episode_id="incident-42",
        asset_id=asset_id,
        relationship_id=relationship_id,
        signal=f"{relationship_id}:signal",
        value=value,
        unit="ms",
        min_value=min_value,
        max_value=max_value,
        temporal_rule_status="late" if outside else "within",
        quality="good",
        reason_code="EVIDENCE.RELATIONSHIP_DELAY_MEASURED",
        correlation_id=f"cycle-{offset_seconds}",
        topology_from=topology_from,
        topology_to=topology_to,
        source_mode="replay",
        cycle_id=f"cycle-{offset_seconds}",
        phase_id="LABEL_PRESENTED",
        operating_context=operating_context
        or {
            "configuration_version": "plc-config-4.2.1",
            "firmware_version": "servo-fw-3.7",
            "recipe_id": "500ml-round",
        },
        clock_evidence={"basis": "same_source_relative_interval"},
    )


class FakeRepository:
    def __init__(
        self,
        responses: list[tuple[tuple[ConditionHistoryRecord, ...], bool]],
    ) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def select_condition_history_records(
        self,
        *,
        limit: int = 240,
        asset_id: str | None = None,
        relationship_id: str | None = None,
        episode_id: str | None = None,
        cycle_id: str | None = None,
        phase_id: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> tuple[tuple[ConditionHistoryRecord, ...], bool]:
        self.calls.append(
            {
                "limit": limit,
                "asset_id": asset_id,
                "relationship_id": relationship_id,
                "episode_id": episode_id,
                "cycle_id": cycle_id,
                "phase_id": phase_id,
                "from_time": from_time,
                "to_time": to_time,
            }
        )
        return self.responses.pop(0)


def spec(**overrides: object) -> ConditionHistorySelectionSpec:
    values: dict[str, object] = {
        "label": "Incident persistence window",
        "asset_id": "LABELER-DEMO-01",
        "episode_id": "incident-42",
        "limit": 1000,
    }
    values.update(overrides)
    return ConditionHistorySelectionSpec(**values)  # type: ignore[arg-type]


def target_records() -> tuple[ConditionHistoryRecord, ...]:
    return tuple(
        record(
            relationship_id="relationship:label-presentation-delay",
            offset_seconds=index * 60,
            value=value,
            topology_from="LabelFeedCommand",
            topology_to="LabelAtPeelPoint",
        )
        for index, value in enumerate([200.0, 500.0, 510.0, 520.0])
    )


def test_selection_spec_requires_explicit_bounded_scope() -> None:
    with pytest.raises(ConditionHistorySelectionError, match="requires"):
        ConditionHistorySelectionSpec(
            label="Too broad",
            asset_id="LABELER-DEMO-01",
        )

    bounded = ConditionHistorySelectionSpec(
        label="Time bounded",
        asset_id="LABELER-DEMO-01",
        from_time=BASE,
        to_time=BASE + timedelta(minutes=5),
    )
    assert bounded.episode_id is None


def test_selection_spec_rejects_naive_inverted_time_and_bad_limit() -> None:
    with pytest.raises(ConditionHistorySelectionError, match="timezone-aware"):
        spec(from_time=datetime(2026, 9, 14, 11, 37))
    with pytest.raises(ConditionHistorySelectionError, match="less than or equal"):
        ConditionHistorySelectionSpec(
            label="bad time",
            asset_id="LABELER-DEMO-01",
            from_time=BASE + timedelta(minutes=1),
            to_time=BASE,
        )
    with pytest.raises(ConditionHistorySelectionError, match="between 1 and 5000"):
        spec(limit=5001)


def test_selector_forwards_exact_condition_filters() -> None:
    repository = FakeRepository([(target_records(), False)])
    selector = ConditionHistorianSelector(repository)
    selection_spec = spec(
        cycle_id="cycle-180",
        phase_id="LABEL_PRESENTED",
        from_time=BASE,
        to_time=BASE + timedelta(minutes=3),
        limit=250,
    )

    selection = selector.select(selection_spec)

    assert selection.records == target_records()
    assert selection.complete is True
    assert repository.calls == [
        {
            "limit": 250,
            "asset_id": "LABELER-DEMO-01",
            "relationship_id": None,
            "episode_id": "incident-42",
            "cycle_id": "cycle-180",
            "phase_id": "LABEL_PRESENTED",
            "from_time": BASE,
            "to_time": BASE + timedelta(minutes=3),
        }
    ]


def test_localization_refuses_relationship_filtered_selection_without_querying() -> None:
    repository = FakeRepository([])
    selector = ConditionHistorianSelector(repository)

    result = selector.localize(
        spec(relationship_id="relationship:label-presentation-delay"),
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
        topology=topology(),
    )

    assert result.disposition is (
        ConditionLocalizationHandoffDisposition.REFUSED_RELATIONSHIP_FILTERED
    )
    assert result.localization is None
    assert result.reason_code == "SELECTION.RELATIONSHIP_FILTER_HIDES_DEPENDENCIES"
    assert repository.calls == []


def test_localization_refuses_truncated_or_empty_history() -> None:
    target = target_records()
    truncated_selector = ConditionHistorianSelector(FakeRepository([(target, True)]))
    truncated = truncated_selector.localize(
        spec(),
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
        topology=topology(),
    )
    assert truncated.disposition is ConditionLocalizationHandoffDisposition.REFUSED_TRUNCATED
    assert truncated.localization is None

    empty_selector = ConditionHistorianSelector(FakeRepository([((), False)]))
    empty = empty_selector.localize(
        spec(),
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
        topology=topology(),
    )
    assert empty.disposition is ConditionLocalizationHandoffDisposition.REFUSED_EMPTY
    assert empty.localization is None


def test_localization_refuses_mixed_operating_context() -> None:
    target = list(target_records())
    target[-1] = record(
        relationship_id="relationship:label-presentation-delay",
        offset_seconds=180,
        value=520.0,
        topology_from="LabelFeedCommand",
        topology_to="LabelAtPeelPoint",
        operating_context={
            "configuration_version": "plc-config-4.2.2",
            "firmware_version": "servo-fw-3.7",
            "recipe_id": "500ml-round",
        },
    )
    selector = ConditionHistorianSelector(FakeRepository([(tuple(target), False)]))

    result = selector.localize(
        spec(),
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
        topology=topology(),
    )

    assert result.disposition is (ConditionLocalizationHandoffDisposition.REFUSED_CONTEXT_AMBIGUOUS)
    assert result.localization is None
    assert result.reason_code == "SELECTION.CONDITION_CONTEXT_AMBIGUOUS"


def test_complete_selection_feeds_localizer_with_dependency_evidence() -> None:
    target = target_records()
    upstream = tuple(
        record(
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
    downstream = tuple(
        record(
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
    selector = ConditionHistorianSelector(FakeRepository([(target + upstream + downstream, False)]))

    result = selector.localize(
        spec(),
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
        topology=topology(),
    )

    assert result.disposition is ConditionLocalizationHandoffDisposition.READY
    assert result.localization is not None
    assert result.localization.disposition is LocalizationDisposition.PERSISTENCE_ESTABLISHED
    assert result.localization.onset is not None
    assert result.localization.onset.persistence_established_at == (BASE + timedelta(seconds=180))
    upstream_states = {item.relationship_id: item.state for item in result.localization.upstream}
    downstream_states = {
        item.relationship_id: item.state for item in result.localization.downstream
    }
    assert upstream_states["relationship:alignment-feed"] is (
        RelationshipWindowState.WITHIN_ENVELOPE
    )
    assert downstream_states["relationship:initial-contact"] is (
        RelationshipWindowState.PERSISTENT_OUTSIDE
    )


def test_selector_refuses_repository_asset_mismatch() -> None:
    bad = record(
        relationship_id="relationship:label-presentation-delay",
        offset_seconds=0,
        value=200.0,
        topology_from="LabelFeedCommand",
        topology_to="LabelAtPeelPoint",
        asset_id="OTHER-ASSET",
    )
    selector = ConditionHistorianSelector(FakeRepository([((bad,), False)]))

    with pytest.raises(ConditionHistorySelectionError, match="different asset_id"):
        selector.select(spec())


def test_condition_history_selection_types_are_exported_from_public_api() -> None:
    import linealert_core

    assert linealert_core.ConditionHistorianSelector is ConditionHistorianSelector
    assert linealert_core.ConditionHistorySelectionSpec is ConditionHistorySelectionSpec
    assert (
        linealert_core.ConditionLocalizationHandoffDisposition
        is ConditionLocalizationHandoffDisposition
    )


def test_localization_refuses_when_target_relationship_is_not_present() -> None:
    only_upstream = tuple(
        record(
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
    selector = ConditionHistorianSelector(FakeRepository([(only_upstream, False)]))

    result = selector.localize(
        spec(),
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
        topology=topology(),
    )

    assert result.disposition is (
        ConditionLocalizationHandoffDisposition.REFUSED_TARGET_NOT_PRESENT
    )
    assert result.localization is None
    assert result.reason_code == "SELECTION.TARGET_RELATIONSHIP_NOT_PRESENT"


def test_selected_condition_localization_serializer_preserves_result() -> None:
    target = target_records()
    selector = ConditionHistorianSelector(FakeRepository([(target, False)]))

    result = selector.localize(
        spec(),
        target_relationship_id="relationship:label-presentation-delay",
        persistence_rule=PersistenceRule(required_outside=3, window_size=4),
        topology=topology(),
    )
    payload = selected_condition_localization_to_dict(result)

    assert payload["schema_version"] == "linealert.selected-condition-localization.v1"
    assert payload["disposition"] == "READY"
    selection = payload["selection"]
    assert isinstance(selection, dict)
    assert selection["asset_id"] == "LABELER-DEMO-01"
    assert selection["record_count"] == 4
    assert selection["truncated"] is False
    localization = payload["localization"]
    assert isinstance(localization, dict)
    assert localization["disposition"] == "PERSISTENCE_ESTABLISHED"
    onset = localization["onset"]
    assert isinstance(onset, dict)
    assert onset["outside_count"] == 3
    assert onset["window_count"] == 4
