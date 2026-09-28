from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest

from linealert_core.historian import (
    ConditionHistoryRecord,
    HistorianError,
    TimescaleHistorian,
)


class _FakeCursor:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        self.connection.executions.append((query, params))

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self.connection.rows)


class _FakeConnection:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[object, ...] | None]] = []
        self.rows: list[tuple[object, ...]] = []

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)


def fake_historian() -> tuple[TimescaleHistorian, _FakeConnection]:
    historian = object.__new__(TimescaleHistorian)
    connection = _FakeConnection()
    historian._connection = connection
    historian._lock = threading.RLock()
    return historian, connection


def record(
    *,
    observation_id: str = "obs-42",
    observed_at: datetime = datetime(2026, 9, 14, 15, 42, tzinfo=UTC),
    relationship_id: str = "relationship:label-presentation-delay",
    cycle_id: str | None = "cycle-42",
    phase_id: str | None = "LABEL_PRESENTED",
    operating_context: dict[str, object] | None = None,
) -> ConditionHistoryRecord:
    return ConditionHistoryRecord(
        observed_at=observed_at,
        observation_id=observation_id,
        episode_id="incident-2026-09-14",
        asset_id="LABELER-DEMO-01",
        relationship_id=relationship_id,
        signal="label_presentation_delay_ms",
        value=550.0,
        unit="ms",
        min_value=50.0,
        max_value=350.0,
        temporal_rule_status="late",
        quality="good",
        reason_code="EVIDENCE.RELATIONSHIP_DELAY_MEASURED",
        correlation_id=cycle_id or "correlation-42",
        topology_from="LabelFeedCommand",
        topology_to="LabelAtPeelPoint",
        source_mode="replay",
        cycle_id=cycle_id,
        phase_id=phase_id,
        operating_context=operating_context
        or {
            "configuration_version": "plc-config-4.2.1",
            "firmware_version": "servo-fw-3.7",
            "recipe_id": "500ml-round",
        },
        clock_evidence={
            "basis": "same_source_relative_interval",
            "start_clock_quality": "synchronized",
            "end_clock_quality": "synchronized",
        },
    )


def row(value: ConditionHistoryRecord) -> tuple[object, ...]:
    return (
        value.observed_at,
        value.observation_id,
        value.episode_id,
        value.asset_id,
        value.relationship_id,
        value.signal,
        value.value,
        value.unit,
        value.min_value,
        value.max_value,
        value.temporal_rule_status,
        value.quality,
        value.reason_code,
        value.correlation_id,
        value.topology_from,
        value.topology_to,
        value.source_mode,
        value.cycle_id,
        value.phase_id,
        dict(value.operating_context),
        dict(value.clock_evidence),
    )


def test_condition_history_record_preserves_immutable_context_and_clock_evidence() -> None:
    operating_context = {"configuration_version": "cfg-1"}
    clock_evidence = {"basis": "same_source_relative_interval"}
    value = record(
        operating_context=operating_context,
    )
    value = ConditionHistoryRecord(
        **{
            field_name: getattr(value, field_name)
            for field_name in value.__dataclass_fields__
            if field_name not in {"operating_context", "clock_evidence"}
        },
        operating_context=operating_context,
        clock_evidence=clock_evidence,
    )

    operating_context["configuration_version"] = "changed"
    clock_evidence["basis"] = "changed"

    assert dict(value.operating_context) == {"configuration_version": "cfg-1"}
    assert dict(value.clock_evidence) == {"basis": "same_source_relative_interval"}
    with pytest.raises(TypeError):
        value.operating_context["configuration_version"] = "other"  # type: ignore[index]


def test_condition_history_record_requires_timezone_aware_observed_at() -> None:
    with pytest.raises(HistorianError, match="timezone-aware"):
        ConditionHistoryRecord(
            observed_at=datetime(2026, 9, 14, 15, 42),
            observation_id="obs",
            episode_id="episode",
            asset_id="asset",
            relationship_id="relationship",
            signal="signal",
            value=1.0,
            unit="ms",
            min_value=0.0,
            max_value=2.0,
            temporal_rule_status="within",
            quality="good",
            reason_code="reason",
            correlation_id="cycle",
            topology_from="A",
            topology_to="B",
            source_mode="replay",
        )


def test_select_condition_history_records_applies_exact_filters_and_time_bounds() -> None:
    historian, connection = fake_historian()
    value = record()
    connection.rows = [row(value)]
    start = value.observed_at - timedelta(minutes=1)
    end = value.observed_at + timedelta(minutes=1)

    records, truncated = historian.select_condition_history_records(
        limit=10,
        asset_id="LABELER-DEMO-01",
        relationship_id="relationship:label-presentation-delay",
        episode_id="incident-2026-09-14",
        cycle_id="cycle-42",
        phase_id="LABEL_PRESENTED",
        from_time=start,
        to_time=end,
    )

    assert records == (value,)
    assert truncated is False
    query, params = connection.executions[-1]
    assert "asset_id = %s" in query
    assert "relationship_id = %s" in query
    assert "episode_id = %s" in query
    assert "cycle_id = %s" in query
    assert "phase_id = %s" in query
    assert "observed_at >= %s" in query
    assert "observed_at <= %s" in query
    assert "ORDER BY observed_at DESC, observation_id DESC" in query
    assert params is not None
    assert params[-1] == 11
    assert start in params
    assert end in params


def test_select_condition_history_records_is_chronological_and_marks_truncation() -> None:
    historian, connection = fake_historian()
    latest = record(observation_id="obs-latest")
    middle = record(
        observation_id="obs-middle",
        observed_at=latest.observed_at - timedelta(seconds=1),
    )
    oldest = record(
        observation_id="obs-oldest",
        observed_at=latest.observed_at - timedelta(seconds=2),
    )
    connection.rows = [row(latest), row(middle), row(oldest)]

    records, truncated = historian.select_condition_history_records(limit=2)

    assert truncated is True
    assert [item.observation_id for item in records] == [
        middle.observation_id,
        latest.observation_id,
    ]
    query, params = connection.executions[-1]
    assert "LIMIT %s" in query
    assert params is not None
    assert params[-1] == 3


def test_condition_history_payload_exposes_bounds_and_truncation() -> None:
    historian, connection = fake_historian()
    latest = record(observation_id="obs-latest")
    older = record(
        observation_id="obs-older",
        observed_at=latest.observed_at - timedelta(seconds=1),
    )
    connection.rows = [row(latest), row(older)]
    start = latest.observed_at - timedelta(minutes=2)
    end = latest.observed_at + timedelta(minutes=2)

    payload = historian.condition_history(
        limit=1,
        asset_id="LABELER-DEMO-01",
        cycle_id="cycle-42",
        from_time=start,
        to_time=end,
    )

    assert payload["count"] == 1
    assert payload["truncated"] is True
    assert payload["truncation_semantic"] == "older_matching_records_omitted"
    assert payload["from_time"] == start.isoformat()
    assert payload["to_time"] == end.isoformat()
    measurement = payload["measurements"][0]
    assert measurement["observation_id"] == latest.observation_id
    assert measurement["cycle_id"] == "cycle-42"
    assert measurement["operating_context"]["configuration_version"] == ("plc-config-4.2.1")


def test_condition_history_selection_rejects_bad_bounds_and_limit() -> None:
    historian, _ = fake_historian()

    with pytest.raises(HistorianError, match="timezone-aware"):
        historian.select_condition_history_records(
            from_time=datetime(2026, 9, 14, 15, 42),
        )
    with pytest.raises(HistorianError, match="less than or equal"):
        historian.select_condition_history_records(
            from_time=datetime(2026, 9, 14, 16, 0, tzinfo=UTC),
            to_time=datetime(2026, 9, 14, 15, 0, tzinfo=UTC),
        )
    with pytest.raises(HistorianError, match="between 1 and 5000"):
        historian.select_condition_history_records(limit=5001)
