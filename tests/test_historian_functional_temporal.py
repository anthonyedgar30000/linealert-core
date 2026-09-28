from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest

from linealert_core.functional_temporal import (
    EpistemicState,
    EvidenceValidity,
    TemporalCoverage,
    TransitionDisposition,
)
from linealert_core.historian import (
    _SCHEMA_SQL,
    FunctionalTemporalHistoryRecord,
    FunctionalTemporalRecordKind,
    HistorianError,
    HistorianOperatingContext,
    TimescaleHistorian,
)
from linealert_core.historian_service import (
    functional_temporal_record_from_payload,
    measurement_from_payload,
)


def context() -> HistorianOperatingContext:
    return HistorianOperatingContext(
        asset_id="LABELER-DEMO-01",
        component_id="capture",
        profile_id="speedway-labeler-demo-v1",
        operating_mode="production",
        configuration_version="plc-config-4.2.1",
        firmware_version="servo-fw-3.7",
        calibration_id="CAL-104",
        sampling_profile_id="profile-20ms-v1",
        recipe_id="500ml-round",
        product_id="bottle-500ml",
        context_tags={"line": "demo", "shift": "day"},
    )


def guard_record() -> FunctionalTemporalHistoryRecord:
    return FunctionalTemporalHistoryRecord(
        observed_at=datetime(2026, 9, 14, 15, 42, tzinfo=UTC),
        record_id="FT:cycle-42:guard-capture-ready",
        episode_id="incident-2026-09-14",
        cycle_id="cycle-42",
        record_kind=FunctionalTemporalRecordKind.GUARD,
        state=EpistemicState.VERIFIED,
        validity=EvidenceValidity.CURRENT,
        coverage=TemporalCoverage.POINT_ONLY,
        source_id="linealert-functional-temporal-v1",
        operating_context=context(),
        phase_id="CAPTURED",
        requirement_id="GUARD_CAPTURE_READY",
        evidence_ids=("E:bottle-present", "E:stop-extended"),
        clock_evidence={"quality": "synchronized"},
    )


def payload() -> dict[str, object]:
    return {
        "observed_at": "2026-09-14T15:42:00Z",
        "record_id": "FT:cycle-42:transition-indexed-captured",
        "episode_id": "incident-2026-09-14",
        "cycle_id": "cycle-42",
        "record_kind": "TRANSITION",
        "epistemic_state": "VERIFIED",
        "evidence_validity": "CURRENT",
        "temporal_coverage": "POINT_ONLY",
        "source_id": "linealert-functional-temporal-v1",
        "transition_id": "INDEXED_TO_CAPTURED",
        "from_phase_id": "INDEXED",
        "to_phase_id": "CAPTURED",
        "trigger_event_id": "event-stop-extended-42",
        "transition_disposition": "ADMITTED",
        "evidence_ids": ["E:bottle-present", "E:stop-extended"],
        "reasons": [],
        "clock_evidence": {"quality": "synchronized"},
        "details": {"trigger_event_type": "CaptureEstablished"},
        "operating_context": {
            "asset_id": "LABELER-DEMO-01",
            "component_id": "capture",
            "profile_id": "speedway-labeler-demo-v1",
            "operating_mode": "production",
            "configuration_version": "plc-config-4.2.1",
            "firmware_version": "servo-fw-3.7",
            "calibration_id": "CAL-104",
            "sampling_profile_id": "profile-20ms-v1",
            "recipe_id": "500ml-round",
            "product_id": "bottle-500ml",
            "context_tags": {"line": "demo"},
        },
    }


def test_payload_parser_preserves_exact_operating_context() -> None:
    record = functional_temporal_record_from_payload(payload())

    assert record.record_kind is FunctionalTemporalRecordKind.TRANSITION
    assert record.transition_disposition is TransitionDisposition.ADMITTED
    assert record.operating_context.configuration_version == "plc-config-4.2.1"
    assert record.operating_context.firmware_version == "servo-fw-3.7"
    assert record.operating_context.recipe_id == "500ml-round"
    assert record.trigger_event_id == "event-stop-extended-42"
    assert record.evidence_ids == ("E:bottle-present", "E:stop-extended")


def test_payload_parser_rejects_missing_configuration_context() -> None:
    raw = payload()
    operating_context = raw["operating_context"]
    assert isinstance(operating_context, dict)
    del operating_context["configuration_version"]

    with pytest.raises(ValueError, match="configuration_version"):
        functional_temporal_record_from_payload(raw)


def test_transition_history_requires_exact_trigger_event_identity() -> None:
    with pytest.raises(HistorianError, match="trigger_event_id"):
        FunctionalTemporalHistoryRecord(
            observed_at=datetime(2026, 9, 14, 15, 42, tzinfo=UTC),
            record_id="FT:transition",
            episode_id="incident",
            cycle_id="cycle-42",
            record_kind=FunctionalTemporalRecordKind.TRANSITION,
            state=EpistemicState.VERIFIED,
            validity=EvidenceValidity.CURRENT,
            coverage=TemporalCoverage.POINT_ONLY,
            source_id="source",
            operating_context=context(),
            transition_id="INDEXED_TO_CAPTURED",
            from_phase_id="INDEXED",
            to_phase_id="CAPTURED",
            transition_disposition=TransitionDisposition.ADMITTED,
        )


def test_history_record_requires_timezone_aware_observed_at() -> None:
    record = guard_record()
    with pytest.raises(HistorianError, match="timezone-aware"):
        FunctionalTemporalHistoryRecord(
            observed_at=datetime(2026, 9, 14, 15, 42),
            record_id=record.record_id,
            episode_id=record.episode_id,
            cycle_id=record.cycle_id,
            record_kind=record.record_kind,
            state=record.state,
            validity=record.validity,
            coverage=record.coverage,
            source_id=record.source_id,
            operating_context=record.operating_context,
            phase_id=record.phase_id,
            requirement_id=record.requirement_id,
        )


def test_schema_adds_append_only_functional_temporal_history_and_condition_context() -> None:
    assert "CREATE TABLE IF NOT EXISTS functional_temporal_evidence" in _SCHEMA_SQL
    assert "ADD COLUMN IF NOT EXISTS cycle_id TEXT" in _SCHEMA_SQL
    assert "ADD COLUMN IF NOT EXISTS phase_id TEXT" in _SCHEMA_SQL
    assert "ADD COLUMN IF NOT EXISTS operating_context JSONB" in _SCHEMA_SQL
    assert "functional_temporal_cycle_time_idx" in _SCHEMA_SQL


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


def test_historian_write_binds_context_and_epistemic_fields() -> None:
    historian, connection = fake_historian()

    result = historian.record_functional_temporal_evidence(guard_record())

    query, params = connection.executions[-1]
    assert "INSERT INTO functional_temporal_evidence" in query
    assert params is not None
    assert query.count("%s") == len(params)
    assert "plc-config-4.2.1" in params
    assert "servo-fw-3.7" in params
    assert "GUARD" in params
    assert "VERIFIED" in params
    assert result["record_kind"] == "GUARD"
    assert result["cycle_id"] == "cycle-42"


def test_operating_context_is_immutable_and_normalized() -> None:
    tags = {" shift ": " day ", "line": "demo"}
    value = HistorianOperatingContext(
        asset_id="A",
        component_id="C",
        profile_id="P",
        operating_mode="production",
        configuration_version="cfg",
        firmware_version="fw",
        calibration_id="cal",
        sampling_profile_id="sample",
        context_tags=tags,
    )

    tags["line"] = "changed"
    assert dict(value.context_tags) == {"line": "demo", "shift": "day"}
    with pytest.raises(TypeError):
        value.context_tags["line"] = "other"  # type: ignore[index]


def test_payload_parser_rejects_non_string_context_tag_values() -> None:
    raw = payload()
    operating_context = raw["operating_context"]
    assert isinstance(operating_context, dict)
    operating_context["context_tags"] = {"speed": 120}

    with pytest.raises(ValueError, match="context tag values"):
        functional_temporal_record_from_payload(raw)


def test_payload_parser_rejects_non_string_identity_fields() -> None:
    raw = payload()
    raw["phase_id"] = 42

    with pytest.raises(ValueError, match="optional identity fields"):
        functional_temporal_record_from_payload(raw)


def test_condition_measurement_write_preserves_cycle_phase_and_context() -> None:
    historian, connection = fake_historian()
    raw = {
        "signal": "stop_extension_ms",
        "value": 97.0,
        "unit": "ms",
        "min_value": 82.0,
        "max_value": 111.0,
        "asset_id": "LABELER-DEMO-01",
        "rule_id": "stop-extension",
        "correlation_id": "cycle-42",
        "source_timestamp": "2026-09-14T15:42:00+00:00",
        "start_timestamp": "2026-09-14T15:41:59.903000+00:00",
        "end_timestamp": "2026-09-14T15:42:00+00:00",
        "topology_from": "StopExtendCommand",
        "topology_to": "StopExtended",
        "temporal_rule_status": "within",
        "semantic": "stop extension response",
        "scope": "capture",
        "relationship_id": "relationship:stop-extension",
        "observation_id": "obs-stop-extension-42",
        "quality": "good",
        "reason_code": "EVIDENCE.RELATIONSHIP_DELAY_MEASURED",
        "clock_evidence": {
            "start_clock_quality": "synchronized",
            "end_clock_quality": "synchronized",
            "basis": "same_source_relative_interval",
            "retained_uncertainty": "same source clock",
        },
    }

    historian.record_condition_measurement(
        measurement_from_payload(raw),
        episode_id="incident-2026-09-14",
        source_mode="replay",
        cycle_id="cycle-42",
        phase_id="CAPTURED",
        operating_context={
            "configuration_version": "plc-config-4.2.1",
            "firmware_version": "servo-fw-3.7",
        },
    )

    query, params = connection.executions[-1]
    assert "cycle_id, phase_id, operating_context" in query
    assert params is not None
    assert query.count("%s") == len(params)
    assert "cycle-42" in params
    assert "CAPTURED" in params
    assert (
        '{"configuration_version": "plc-config-4.2.1", "firmware_version": "servo-fw-3.7"}'
        in params
    )
