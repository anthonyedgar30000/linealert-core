from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from linealert_core.reasoning_context import ReasoningContextRequest, assemble_reasoning_context
from linealert_core.reasoning_historian import (
    HistorianConditionQuery,
    HistorianRetrievalAuthority,
    ReadOnlyTimescaleConditionHistorySource,
    ReasoningHistorianError,
    retrieve_historian_condition_candidates,
)


def _authority(*, source_sha256: str = "a" * 64) -> HistorianRetrievalAuthority:
    return HistorianRetrievalAuthority(
        asset_id="LABELER-DEMO-01",
        profile_id="generic-pressure-sensitive-labeler-demo-v1",
        source_name="labeler_demo_config.json",
        source_sha256=source_sha256,
    )


def _retained_authority(*, source_sha256: str = "a" * 64) -> dict[str, object]:
    return {
        "schema_version": "linealert.condition-evidence-authority.v1",
        "authority_scope": "HISTORIAN_WRITE_TIME_POLICY_AUTHORITY",
        "configuration": {
            "asset_id": "LABELER-DEMO-01",
            "profile_id": "generic-pressure-sensitive-labeler-demo-v1",
            "source_name": "labeler_demo_config.json",
            "source_sha256": source_sha256,
        },
        "persistence_policy": None,
    }


def _record(
    observation_id: str = "obs-1",
    *,
    config_version: str = "cfg-2",
    quality: str = "good",
    authority: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "observed_at": "2026-09-28T18:00:00+00:00",
        "observation_id": observation_id,
        "episode_id": "episode-42",
        "asset_id": "LABELER-DEMO-01",
        "relationship_id": "relationship:label-presentation-delay",
        "signal": "label_presentation_delay_ms",
        "value": 510.0,
        "unit": "ms",
        "min_value": 100.0,
        "max_value": 450.0,
        "temporal_rule_status": "outside",
        "quality": quality,
        "reason_code": "CONDITION.OUTSIDE_ENVELOPE",
        "correlation_id": "corr-1",
        "topology_from": "LABEL_SENSOR",
        "topology_to": "APPLICATOR",
        "source_mode": "deterministic_event_replay",
        "cycle_id": "cycle-7",
        "phase_id": "apply",
        "operating_context": {
            "configuration_version": config_version,
            "firmware_version": "demo-fw-v1",
        },
        "evidence_authority": authority if authority is not None else _retained_authority(),
        "clock_evidence": {
            "schema_version": "linealert.clock-evidence.v1",
            "status": "BOUNDED",
            "uncertainty_ms": 4.0,
        },
    }


class _FakeSource:
    source_id = "timescaledb:test"
    read_only_verified = True

    def __init__(
        self,
        records: tuple[dict[str, object], ...],
        *,
        truncated: bool = False,
        read_only_verified: bool = True,
    ) -> None:
        self.records = records
        self.truncated = truncated
        self.read_only_verified = read_only_verified
        self.calls: list[HistorianConditionQuery] = []

    def select_condition_history(
        self,
        query: HistorianConditionQuery,
    ) -> tuple[tuple[dict[str, object], ...], bool]:
        self.calls.append(query)
        return self.records, self.truncated


def _query(**overrides: Any) -> HistorianConditionQuery:
    values: dict[str, Any] = {
        "asset_id": "LABELER-DEMO-01",
        "relationship_id": "relationship:label-presentation-delay",
        "episode_id": "episode-42",
        "limit": 20,
    }
    values.update(overrides)
    return HistorianConditionQuery(**values)


def _db_row(
    observation_id: str,
    observed_at: datetime,
    *,
    authority: dict[str, object] | None = None,
) -> tuple[object, ...]:
    return (
        observed_at,
        observation_id,
        "episode-42",
        "LABELER-DEMO-01",
        "relationship:label-presentation-delay",
        "label_presentation_delay_ms",
        510.0,
        "ms",
        100.0,
        450.0,
        "outside",
        "good",
        "CONDITION.OUTSIDE_ENVELOPE",
        "corr-1",
        "LABEL_SENSOR",
        "APPLICATOR",
        "deterministic_event_replay",
        "cycle-7",
        "apply",
        {
            "configuration_version": "cfg-2",
            "firmware_version": "demo-fw-v1",
        },
        authority if authority is not None else _retained_authority(),
        {
            "schema_version": "linealert.clock-evidence.v1",
            "status": "BOUNDED",
            "uncertainty_ms": 4.0,
        },
    )


class _FakeCursor:
    def __init__(
        self,
        statements: list[tuple[str, tuple[object, ...] | None]],
        rows: list[tuple[object, ...]],
        *,
        read_only_value: str = "on",
    ) -> None:
        self.statements = statements
        self.rows = rows
        self.read_only_value = read_only_value
        self.current = ""

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
        self.current = sql.strip()
        self.statements.append((self.current, params))

    def fetchone(self) -> tuple[str]:
        assert self.current == "SHOW default_transaction_read_only"
        return (self.read_only_value,)

    def fetchall(self) -> list[tuple[object, ...]]:
        assert self.current.startswith("SELECT")
        return self.rows


class _FakeConnection:
    def __init__(
        self,
        rows: list[tuple[object, ...]],
        *,
        read_only_value: str = "on",
    ) -> None:
        self.rows = rows
        self.read_only_value = read_only_value
        self.statements: list[tuple[str, tuple[object, ...] | None]] = []
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(
            self.statements,
            self.rows,
            read_only_value=self.read_only_value,
        )

    def close(self) -> None:
        self.closed = True


def test_query_rejects_naive_time_and_invalid_window() -> None:
    with pytest.raises(ReasoningHistorianError, match="timezone-aware"):
        _query(from_time=datetime(2026, 9, 28, 12, 0, 0))

    start = datetime(2026, 9, 28, 13, 0, tzinfo=UTC)
    with pytest.raises(ReasoningHistorianError, match="less than or equal"):
        _query(from_time=start, to_time=start - timedelta(seconds=1))


def test_authority_normalizes_sha256_case() -> None:
    authority = _authority(source_sha256="A" * 64)
    assert authority.source_sha256 == "a" * 64


def test_read_only_source_verifies_session_and_uses_only_show_and_select() -> None:
    connection = _FakeConnection(
        [
            _db_row("obs-1", datetime(2026, 9, 28, 18, 0, tzinfo=UTC)),
        ]
    )
    connect_calls: list[tuple[str, dict[str, object]]] = []

    def connect(dsn: str, **kwargs: object) -> _FakeConnection:
        connect_calls.append((dsn, kwargs))
        return connection

    source = ReadOnlyTimescaleConditionHistorySource(
        "postgresql://example/reasoning",
        source_id="timescaledb:test",
        connect_factory=connect,
    )
    records, truncated = source.select_condition_history(_query(limit=2))

    assert source.read_only_verified is True
    assert truncated is False
    assert len(records) == 1
    assert records[0]["observation_id"] == "obs-1"
    assert records[0]["clock_evidence"]["uncertainty_ms"] == 4.0
    assert connect_calls == [
        (
            "postgresql://example/reasoning",
            {
                "autocommit": True,
                "options": "-c default_transaction_read_only=on",
            },
        )
    ]
    statements = [sql for sql, _ in connection.statements]
    assert statements[0] == "SHOW default_transaction_read_only"
    assert statements[1].startswith("SELECT")
    assert not any(
        token in statement.upper()
        for statement in statements
        for token in ("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER ", "DROP ")
    )
    source.close()
    assert connection.closed is True


def test_read_only_source_refuses_unverified_database_session() -> None:
    connection = _FakeConnection([], read_only_value="off")

    with pytest.raises(ReasoningHistorianError, match="did not verify"):
        ReadOnlyTimescaleConditionHistorySource(
            "postgresql://example/reasoning",
            connect_factory=lambda *args, **kwargs: connection,
        )

    assert connection.closed is True


def test_database_source_reports_truncation_without_hiding_query_bound() -> None:
    newer = _db_row("obs-new", datetime(2026, 9, 28, 18, 2, tzinfo=UTC))
    older = _db_row("obs-old", datetime(2026, 9, 28, 18, 1, tzinfo=UTC))
    connection = _FakeConnection([newer, older])

    source = ReadOnlyTimescaleConditionHistorySource(
        "postgresql://example/reasoning",
        connect_factory=lambda *args, **kwargs: connection,
    )
    records, truncated = source.select_condition_history(_query(limit=1))

    assert truncated is True
    assert len(records) == 1
    select_statement, params = connection.statements[-1]
    assert "asset_id = %s" in select_statement
    assert "relationship_id = %s" in select_statement
    assert params is not None
    assert params[-1] == 2


def test_retrieval_refuses_unverified_read_only_source_without_querying() -> None:
    source = _FakeSource((_record(),), read_only_verified=False)

    result = retrieve_historian_condition_candidates(source, _query(), _authority())

    assert result.candidates == ()
    assert result.refusals[0].reason_code == "HISTORIAN.READ_ONLY_SESSION_UNVERIFIED"
    assert source.calls == []


def test_retrieval_refuses_truncated_history_entirely() -> None:
    source = _FakeSource((_record(),), truncated=True)

    result = retrieve_historian_condition_candidates(source, _query(), _authority())

    assert result.candidates == ()
    assert result.truncated is True
    assert result.refusals[0].reason_code == "HISTORIAN.RETRIEVAL_TRUNCATED"


def test_retrieval_refuses_missing_or_mismatched_authority() -> None:
    missing = _record()
    missing["evidence_authority"] = None
    mismatch = _record("obs-2")
    mismatch["evidence_authority"] = _retained_authority(source_sha256="b" * 64)
    source = _FakeSource((missing, mismatch))

    result = retrieve_historian_condition_candidates(source, _query(), _authority())

    assert result.candidates == ()
    assert [item.reason_code for item in result.refusals] == [
        "HISTORIAN.RETAINED_AUTHORITY_MISSING",
        "HISTORIAN.RETAINED_CONFIGURATION_MISMATCH",
    ]


def test_retrieval_refuses_bad_quality_without_promoting_record() -> None:
    source = _FakeSource((_record(quality="uncertain"),))

    result = retrieve_historian_condition_candidates(source, _query(), _authority())

    assert result.candidates == ()
    assert result.refusals[0].reason_code == "HISTORIAN.QUALITY_NOT_GOOD"


def test_exact_record_becomes_provenance_bound_historical_candidate() -> None:
    source = _FakeSource((_record(),))

    result = retrieve_historian_condition_candidates(source, _query(), _authority())

    assert result.refusals == ()
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.evidence_id == "historian.condition:obs-1"
    assert candidate.asset_id == "LABELER-DEMO-01"
    assert candidate.source_id == "timescaledb:test"
    assert candidate.binding_verified is True
    assert candidate.semantic_admitted is True
    assert candidate.authority_class == "HISTORIAN_WRITE_TIME_POLICY_AUTHORITY"
    assert candidate.configuration_version == "cfg-2"
    assert candidate.content["clock_evidence"]["uncertainty_ms"] == 4.0
    assert candidate.provenance == (
        "timescaledb:test:obs-1",
        f"config:labeler_demo_config.json:sha256:{'a' * 64}",
    )
    assert result.to_dict()["authorized_action"] is False


def test_candidate_hands_off_to_context_bundle_without_overriding_config_gate() -> None:
    source = _FakeSource((_record(config_version="cfg-1"),))
    retrieval = retrieve_historian_condition_candidates(source, _query(), _authority())
    assert len(retrieval.candidates) == 1

    bundle = assemble_reasoning_context(
        ReasoningContextRequest(
            asset_id="LABELER-DEMO-01",
            purpose="bounded historian context",
            current_configuration_version="cfg-2",
        ),
        retrieval.candidates,
    )

    assert bundle["counts"]["evidence_count"] == 0
    assert bundle["counts"]["context_only_count"] == 1
    assert (
        bundle["context_only"][0]["reason_code"]
        == "RETRIEVAL.HISTORICAL_CONFIGURATION_CONTEXT_ONLY"
    )
    assert bundle["authorized_action"] is False
    assert bundle["diagnosis_established"] is False


def test_matching_config_historical_record_can_enter_evidence_lane() -> None:
    source = _FakeSource((_record(config_version="cfg-2"),))
    retrieval = retrieve_historian_condition_candidates(source, _query(), _authority())

    bundle = assemble_reasoning_context(
        ReasoningContextRequest(
            asset_id="LABELER-DEMO-01",
            purpose="bounded historian context",
            current_configuration_version="cfg-2",
        ),
        retrieval.candidates,
    )

    assert bundle["counts"]["evidence_count"] == 1
    assert bundle["counts"]["context_only_count"] == 0
    assert bundle["evidence"][0]["candidate"]["content"]["clock_evidence"] == {
        "schema_version": "linealert.clock-evidence.v1",
        "status": "BOUNDED",
        "uncertainty_ms": 4.0,
    }
