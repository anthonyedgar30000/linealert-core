"""Optional TimescaleDB persistence for shared LineAlert operational history.

The historian is an adapter boundary. Writes happen only after deterministic
admission/derivation has succeeded; database durability is not part of the
core transaction or rollback guarantee.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from .functional_temporal import (
    EpistemicState,
    EvidenceValidity,
    TemporalCoverage,
    TransitionDisposition,
)
from .live_condition import LiveConditionMeasurement


class HistorianError(RuntimeError):
    """Raised when the optional historian cannot be configured or queried."""


class HistorianQueryError(HistorianError):
    """Raised when a read-only historian query is malformed or unsafe to execute."""


class FunctionalTemporalRecordKind(StrEnum):
    """Historian record class for functional-temporal evidence."""

    PHASE = "PHASE"
    TRANSITION = "TRANSITION"
    GUARD = "GUARD"
    INVARIANT = "INVARIANT"


@dataclass(frozen=True, slots=True)
class HistorianOperatingContext:
    """Exact machine context bound to one persisted evidence record."""

    asset_id: str
    component_id: str
    profile_id: str
    operating_mode: str
    configuration_version: str
    firmware_version: str
    calibration_id: str
    sampling_profile_id: str
    recipe_id: str | None = None
    product_id: str | None = None
    context_tags: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "asset_id",
            "component_id",
            "profile_id",
            "operating_mode",
            "configuration_version",
            "firmware_version",
            "calibration_id",
            "sampling_profile_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise HistorianError(f"{field_name} must be a non-empty string")
        for field_name in ("recipe_id", "product_id"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise HistorianError(f"{field_name} must be non-empty when supplied")

        normalized: dict[str, str] = {}
        for key, value in self.context_tags.items():
            if not isinstance(key, str) or not key.strip():
                raise HistorianError("context tag keys must be non-empty strings")
            if not isinstance(value, str) or not value.strip():
                raise HistorianError("context tag values must be non-empty strings")
            normalized[key.strip()] = value.strip()
        object.__setattr__(
            self,
            "context_tags",
            MappingProxyType(dict(sorted(normalized.items()))),
        )


@dataclass(frozen=True, slots=True)
class ConditionHistoryRecord:
    """Typed persisted condition relationship evidence."""

    observed_at: datetime
    observation_id: str
    episode_id: str
    asset_id: str
    relationship_id: str
    signal: str
    value: float
    unit: str
    min_value: float
    max_value: float
    temporal_rule_status: str
    quality: str
    reason_code: str
    correlation_id: str
    topology_from: str
    topology_to: str
    source_mode: str
    cycle_id: str | None = None
    phase_id: str | None = None
    operating_context: Mapping[str, Any] = field(default_factory=dict)
    evidence_authority: Mapping[str, Any] | None = None
    clock_evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise HistorianError("observed_at must be timezone-aware")
        for field_name in (
            "observation_id",
            "episode_id",
            "asset_id",
            "relationship_id",
            "signal",
            "unit",
            "temporal_rule_status",
            "quality",
            "reason_code",
            "correlation_id",
            "topology_from",
            "topology_to",
            "source_mode",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise HistorianError(f"{field_name} must be a non-empty string")
        for field_name in ("cycle_id", "phase_id"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise HistorianError(f"{field_name} must be non-empty when supplied")
        if self.min_value > self.max_value:
            raise HistorianError("min_value cannot exceed max_value")
        object.__setattr__(
            self,
            "operating_context",
            MappingProxyType(dict(self.operating_context)),
        )
        if self.evidence_authority is not None:
            object.__setattr__(
                self,
                "evidence_authority",
                MappingProxyType(dict(self.evidence_authority)),
            )
        object.__setattr__(
            self,
            "clock_evidence",
            MappingProxyType(dict(self.clock_evidence)),
        )


@dataclass(frozen=True, slots=True)
class FunctionalTemporalHistoryRecord:
    """Append-only historian record for evaluated phase/transition evidence."""

    observed_at: datetime
    record_id: str
    episode_id: str
    cycle_id: str
    record_kind: FunctionalTemporalRecordKind
    state: EpistemicState
    validity: EvidenceValidity
    coverage: TemporalCoverage
    source_id: str
    operating_context: HistorianOperatingContext
    phase_id: str | None = None
    transition_id: str | None = None
    from_phase_id: str | None = None
    to_phase_id: str | None = None
    trigger_event_id: str | None = None
    requirement_id: str | None = None
    transition_disposition: TransitionDisposition | None = None
    evidence_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    clock_evidence: Mapping[str, Any] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise HistorianError("observed_at must be timezone-aware")
        for field_name in ("record_id", "episode_id", "cycle_id", "source_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise HistorianError(f"{field_name} must be a non-empty string")
        for field_name in (
            "phase_id",
            "transition_id",
            "from_phase_id",
            "to_phase_id",
            "trigger_event_id",
            "requirement_id",
        ):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise HistorianError(f"{field_name} must be non-empty when supplied")
        if any(not item.strip() for item in self.evidence_ids):
            raise HistorianError("evidence_ids must not contain empty values")
        if any(not item.strip() for item in self.reasons):
            raise HistorianError("reasons must not contain empty values")
        object.__setattr__(self, "clock_evidence", MappingProxyType(dict(self.clock_evidence)))
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))
        self._validate_kind_fields()

    def _validate_kind_fields(self) -> None:
        if self.record_kind is FunctionalTemporalRecordKind.PHASE and self.phase_id is None:
            raise HistorianError("phase records require phase_id")
        if self.record_kind is FunctionalTemporalRecordKind.TRANSITION:
            required = (
                self.transition_id,
                self.from_phase_id,
                self.to_phase_id,
                self.trigger_event_id,
            )
            if any(value is None for value in required):
                raise HistorianError(
                    "transition records require transition_id, from_phase_id, "
                    "to_phase_id, and trigger_event_id"
                )
            if self.transition_disposition is None:
                raise HistorianError("transition records require transition_disposition")
        if (
            self.record_kind
            in {
                FunctionalTemporalRecordKind.GUARD,
                FunctionalTemporalRecordKind.INVARIANT,
            }
            and self.requirement_id is None
        ):
            raise HistorianError("guard and invariant records require requirement_id")


_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS machine_observations (
    observed_at TIMESTAMPTZ NOT NULL,
    observation_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    source_id TEXT,
    source_kind TEXT,
    connected BOOLEAN NOT NULL,
    reason_code TEXT,
    payload JSONB NOT NULL,
    PRIMARY KEY (observed_at, observation_id)
);
SELECT create_hypertable(
    'machine_observations', 'observed_at', if_not_exists => TRUE, migrate_data => TRUE
);

CREATE TABLE IF NOT EXISTS condition_measurements (
    observed_at TIMESTAMPTZ NOT NULL,
    observation_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    relationship_id TEXT NOT NULL,
    signal_name TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    min_value DOUBLE PRECISION NOT NULL,
    max_value DOUBLE PRECISION NOT NULL,
    temporal_rule_status TEXT NOT NULL,
    quality TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    topology_from TEXT NOT NULL,
    topology_to TEXT NOT NULL,
    start_event_id TEXT,
    end_event_id TEXT,
    start_source_id TEXT,
    end_source_id TEXT,
    semantic TEXT NOT NULL,
    scope TEXT NOT NULL,
    source_mode TEXT NOT NULL,
    clock_evidence JSONB NOT NULL,
    PRIMARY KEY (observed_at, observation_id)
);
SELECT create_hypertable(
    'condition_measurements', 'observed_at', if_not_exists => TRUE, migrate_data => TRUE
);
CREATE INDEX IF NOT EXISTS condition_asset_relationship_time_idx
    ON condition_measurements (asset_id, relationship_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS condition_episode_time_idx
    ON condition_measurements (episode_id, observed_at DESC);
ALTER TABLE condition_measurements
    ADD COLUMN IF NOT EXISTS cycle_id TEXT,
    ADD COLUMN IF NOT EXISTS phase_id TEXT,
    ADD COLUMN IF NOT EXISTS operating_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS evidence_authority JSONB;

CREATE TABLE IF NOT EXISTS functional_temporal_evidence (
    observed_at TIMESTAMPTZ NOT NULL,
    record_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    record_kind TEXT NOT NULL,
    phase_id TEXT,
    transition_id TEXT,
    from_phase_id TEXT,
    to_phase_id TEXT,
    trigger_event_id TEXT,
    requirement_id TEXT,
    transition_disposition TEXT,
    epistemic_state TEXT NOT NULL,
    evidence_validity TEXT NOT NULL,
    temporal_coverage TEXT NOT NULL,
    source_id TEXT NOT NULL,
    component_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    operating_mode TEXT NOT NULL,
    configuration_version TEXT NOT NULL,
    firmware_version TEXT NOT NULL,
    calibration_id TEXT NOT NULL,
    sampling_profile_id TEXT NOT NULL,
    recipe_id TEXT,
    product_id TEXT,
    context_tags JSONB NOT NULL,
    evidence_ids JSONB NOT NULL,
    reasons JSONB NOT NULL,
    clock_evidence JSONB NOT NULL,
    details JSONB NOT NULL,
    PRIMARY KEY (observed_at, record_id)
);
SELECT create_hypertable(
    'functional_temporal_evidence', 'observed_at',
    if_not_exists => TRUE, migrate_data => TRUE
);
CREATE INDEX IF NOT EXISTS functional_temporal_asset_time_idx
    ON functional_temporal_evidence (asset_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS functional_temporal_episode_time_idx
    ON functional_temporal_evidence (episode_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS functional_temporal_cycle_time_idx
    ON functional_temporal_evidence (cycle_id, observed_at ASC);
CREATE INDEX IF NOT EXISTS functional_temporal_phase_time_idx
    ON functional_temporal_evidence (phase_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS operational_outcomes (
    recorded_at TIMESTAMPTZ NOT NULL,
    outcome_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    relationship_id TEXT NOT NULL,
    outcome_type TEXT NOT NULL,
    status TEXT NOT NULL,
    actor_role TEXT,
    note TEXT,
    related_observation_id TEXT,
    verification_value DOUBLE PRECISION,
    verification_unit TEXT,
    verification_status TEXT,
    details JSONB NOT NULL,
    PRIMARY KEY (recorded_at, outcome_id)
);
SELECT create_hypertable(
    'operational_outcomes', 'recorded_at', if_not_exists => TRUE, migrate_data => TRUE
);
CREATE INDEX IF NOT EXISTS outcomes_episode_time_idx
    ON operational_outcomes (episode_id, recorded_at DESC);
"""


class TimescaleHistorian:
    """Thread-serialized TimescaleDB adapter shared by health and operator APIs."""

    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise HistorianError("historian DSN must be a non-empty string")
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - exercised in local integration only
            raise HistorianError(
                "Install the historian extra: python -m pip install -e '.[historian]'"
            ) from exc
        try:
            self._connection = psycopg.connect(dsn, autocommit=True)
        except Exception as exc:  # pragma: no cover - database integration path
            raise HistorianError(
                f"unable to connect to configured historian: {type(exc).__name__}"
            ) from exc
        self._lock = threading.RLock()
        self.ensure_schema()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def ensure_schema(self) -> None:
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(_SCHEMA_SQL)

    def record_machine_observation(self, payload: dict[str, Any]) -> None:
        observed_at = payload.get("bridge_timestamp") or datetime.now(UTC).isoformat()
        source_id = payload.get("source_id", "unknown")
        sequence = payload.get("observation_sequence", observed_at)
        observation_id = str(payload.get("observation_id") or f"{source_id}:{sequence}")
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO machine_observations (
                    observed_at, observation_id, asset_id, source_id, source_kind,
                    connected, reason_code, payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (observed_at, observation_id) DO NOTHING
                """,
                (
                    observed_at,
                    observation_id,
                    str(payload.get("asset_id", "unknown")),
                    payload.get("source_id"),
                    payload.get("source_kind"),
                    bool(payload.get("connected", False)),
                    payload.get("reason_code"),
                    json.dumps(payload, sort_keys=True),
                ),
            )

    def record_condition_measurement(
        self,
        measurement: LiveConditionMeasurement,
        *,
        episode_id: str,
        source_mode: str,
        cycle_id: str | None = None,
        phase_id: str | None = None,
        operating_context: Mapping[str, Any] | None = None,
        evidence_authority: Mapping[str, Any] | None = None,
    ) -> None:
        observation = measurement.observation
        clock = measurement.clock_evidence
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO condition_measurements (
                    observed_at, observation_id, episode_id, asset_id, relationship_id,
                    signal_name, value, unit, min_value, max_value, temporal_rule_status,
                    quality, reason_code, rule_id, correlation_id, topology_from, topology_to,
                    start_event_id, end_event_id, start_source_id, end_source_id, semantic, scope,
                    source_mode, cycle_id, phase_id, operating_context, evidence_authority,
                    clock_evidence
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb
                )
                ON CONFLICT (observed_at, observation_id) DO NOTHING
                """,
                (
                    observation.source_timestamp,
                    observation.observation_id,
                    episode_id,
                    observation.asset_id,
                    observation.relationship_id,
                    observation.signal_name,
                    observation.value,
                    observation.unit,
                    observation.min_value,
                    observation.max_value,
                    observation.temporal_rule_status,
                    observation.quality,
                    observation.reason_code,
                    observation.rule_id,
                    observation.correlation_id,
                    observation.topology_from,
                    observation.topology_to,
                    observation.start_event_id,
                    observation.end_event_id,
                    observation.start_source_id,
                    observation.end_source_id,
                    observation.semantic,
                    observation.scope,
                    source_mode,
                    cycle_id,
                    phase_id,
                    json.dumps(dict(operating_context or {}), sort_keys=True),
                    (
                        json.dumps(dict(evidence_authority), sort_keys=True)
                        if evidence_authority is not None
                        else None
                    ),
                    json.dumps(
                        {
                            "start_clock_quality": clock.start_clock_quality,
                            "end_clock_quality": clock.end_clock_quality,
                            "basis": clock.basis,
                            "retained_uncertainty": clock.retained_uncertainty,
                        },
                        sort_keys=True,
                    ),
                ),
            )

    def record_functional_temporal_evidence(
        self,
        record: FunctionalTemporalHistoryRecord,
    ) -> dict[str, Any]:
        """Persist one already-evaluated functional-temporal evidence record."""

        context = record.operating_context
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO functional_temporal_evidence (
                    observed_at, record_id, episode_id, asset_id, cycle_id, record_kind,
                    phase_id, transition_id, from_phase_id, to_phase_id, trigger_event_id,
                    requirement_id, transition_disposition, epistemic_state,
                    evidence_validity, temporal_coverage, source_id, component_id, profile_id,
                    operating_mode, configuration_version, firmware_version, calibration_id,
                    sampling_profile_id, recipe_id, product_id, context_tags, evidence_ids,
                    reasons, clock_evidence, details
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb
                )
                ON CONFLICT (observed_at, record_id) DO NOTHING
                """,
                (
                    record.observed_at,
                    record.record_id,
                    record.episode_id,
                    context.asset_id,
                    record.cycle_id,
                    record.record_kind.value,
                    record.phase_id,
                    record.transition_id,
                    record.from_phase_id,
                    record.to_phase_id,
                    record.trigger_event_id,
                    record.requirement_id,
                    (
                        record.transition_disposition.value
                        if record.transition_disposition is not None
                        else None
                    ),
                    record.state.value,
                    record.validity.value,
                    record.coverage.value,
                    record.source_id,
                    context.component_id,
                    context.profile_id,
                    context.operating_mode,
                    context.configuration_version,
                    context.firmware_version,
                    context.calibration_id,
                    context.sampling_profile_id,
                    context.recipe_id,
                    context.product_id,
                    json.dumps(dict(context.context_tags), sort_keys=True),
                    json.dumps(list(record.evidence_ids), sort_keys=True),
                    json.dumps(list(record.reasons), sort_keys=True),
                    json.dumps(dict(record.clock_evidence), sort_keys=True),
                    json.dumps(dict(record.details), sort_keys=True),
                ),
            )
        return {
            "record_id": record.record_id,
            "observed_at": record.observed_at.isoformat(),
            "episode_id": record.episode_id,
            "asset_id": context.asset_id,
            "cycle_id": record.cycle_id,
            "record_kind": record.record_kind.value,
            "state": record.state.value,
        }

    def record_functional_temporal_evidence_batch(
        self,
        records: tuple[FunctionalTemporalHistoryRecord, ...],
    ) -> tuple[dict[str, Any], ...]:
        """Persist one deterministic record batch atomically.

        The connection runs in autocommit mode for ordinary historian writes. An explicit
        transaction is opened here so an orchestration unit cannot leave a partial
        functional-temporal record set behind.
        """

        if not records:
            return ()
        with self._lock, self._connection.transaction():
            return tuple(self.record_functional_temporal_evidence(record) for record in records)

    def record_outcome(self, payload: dict[str, Any]) -> dict[str, Any]:
        required = ("episode_id", "asset_id", "relationship_id", "outcome_type", "status")
        missing = [name for name in required if not str(payload.get(name, "")).strip()]
        if missing:
            raise HistorianError(f"outcome is missing required fields: {', '.join(missing)}")
        recorded_at = str(payload.get("recorded_at") or datetime.now(UTC).isoformat())
        outcome_id = str(payload.get("outcome_id") or uuid.uuid4())
        details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO operational_outcomes (
                    recorded_at, outcome_id, episode_id, asset_id, relationship_id,
                    outcome_type, status, actor_role, note, related_observation_id,
                    verification_value, verification_unit, verification_status, details
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (recorded_at, outcome_id) DO NOTHING
                """,
                (
                    recorded_at,
                    outcome_id,
                    str(payload["episode_id"]),
                    str(payload["asset_id"]),
                    str(payload["relationship_id"]),
                    str(payload["outcome_type"]),
                    str(payload["status"]),
                    payload.get("actor_role"),
                    payload.get("note"),
                    payload.get("related_observation_id"),
                    payload.get("verification_value"),
                    payload.get("verification_unit"),
                    payload.get("verification_status"),
                    json.dumps(details, sort_keys=True),
                ),
            )
        return {
            "outcome_id": outcome_id,
            "recorded_at": recorded_at,
            "episode_id": str(payload["episode_id"]),
            "asset_id": str(payload["asset_id"]),
            "relationship_id": str(payload["relationship_id"]),
            "outcome_type": str(payload["outcome_type"]),
            "status": str(payload["status"]),
        }

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
        """Return typed condition history plus explicit truncation state."""

        if limit < 1 or limit > 5000:
            raise HistorianQueryError("condition history limit must be between 1 and 5000")
        _validate_optional_history_time(from_time, "from_time")
        _validate_optional_history_time(to_time, "to_time")
        if from_time is not None and to_time is not None and from_time > to_time:
            raise HistorianQueryError("from_time must be less than or equal to to_time")

        where: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("asset_id", asset_id),
            ("relationship_id", relationship_id),
            ("episode_id", episode_id),
            ("cycle_id", cycle_id),
            ("phase_id", phase_id),
        ):
            if value:
                where.append(f"{column} = %s")
                params.append(value)
        if from_time is not None:
            where.append("observed_at >= %s")
            params.append(from_time)
        if to_time is not None:
            where.append("observed_at <= %s")
            params.append(to_time)
        predicate = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(limit + 1)
        query = f"""
            SELECT observed_at, observation_id, episode_id, asset_id, relationship_id,
                   signal_name, value, unit, min_value, max_value, temporal_rule_status,
                   quality, reason_code, correlation_id, topology_from, topology_to,
                   source_mode, cycle_id, phase_id, operating_context, evidence_authority,
                   clock_evidence
            FROM condition_measurements
            {predicate}
            ORDER BY observed_at DESC, observation_id DESC
            LIMIT %s
        """
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

        truncated = len(rows) > limit
        selected_rows = rows[:limit]
        records = tuple(_condition_history_record_from_row(row) for row in reversed(selected_rows))
        return records, truncated

    def condition_history(
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
    ) -> dict[str, Any]:
        records, truncated = self.select_condition_history_records(
            limit=limit,
            asset_id=asset_id,
            relationship_id=relationship_id,
            episode_id=episode_id,
            cycle_id=cycle_id,
            phase_id=phase_id,
            from_time=from_time,
            to_time=to_time,
        )
        return {
            "schema_version": "linealert.historian.condition-history.v1",
            "persistence": "timescaledb",
            "count": len(records),
            "truncated": truncated,
            "truncation_semantic": ("older_matching_records_omitted" if truncated else None),
            "from_time": from_time.isoformat() if from_time is not None else None,
            "to_time": to_time.isoformat() if to_time is not None else None,
            "measurements": [_condition_history_record_to_payload(record) for record in records],
        }

    def select_functional_temporal_records(
        self,
        *,
        limit: int = 240,
        asset_id: str | None = None,
        episode_id: str | None = None,
        cycle_id: str | None = None,
        phase_id: str | None = None,
        record_kind: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> tuple[tuple[FunctionalTemporalHistoryRecord, ...], bool]:
        """Return typed functional-temporal evidence plus explicit truncation state."""

        if limit < 1 or limit > 5000:
            raise HistorianQueryError(
                "functional-temporal history limit must be between 1 and 5000"
            )
        _validate_optional_history_time(from_time, "from_time")
        _validate_optional_history_time(to_time, "to_time")
        if from_time is not None and to_time is not None and from_time > to_time:
            raise HistorianQueryError("from_time must be less than or equal to to_time")

        where: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("asset_id", asset_id),
            ("episode_id", episode_id),
            ("cycle_id", cycle_id),
            ("phase_id", phase_id),
            ("record_kind", record_kind),
        ):
            if value:
                where.append(f"{column} = %s")
                params.append(value)
        if from_time is not None:
            where.append("observed_at >= %s")
            params.append(from_time)
        if to_time is not None:
            where.append("observed_at <= %s")
            params.append(to_time)
        predicate = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(limit + 1)
        query = f"""
            SELECT observed_at, record_id, episode_id, asset_id, cycle_id, record_kind,
                   phase_id, transition_id, from_phase_id, to_phase_id, trigger_event_id,
                   requirement_id, transition_disposition, epistemic_state,
                   evidence_validity, temporal_coverage, source_id, component_id, profile_id,
                   operating_mode, configuration_version, firmware_version, calibration_id,
                   sampling_profile_id, recipe_id, product_id, context_tags, evidence_ids,
                   reasons, clock_evidence, details
            FROM functional_temporal_evidence
            {predicate}
            ORDER BY observed_at DESC, record_id DESC
            LIMIT %s
        """
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

        truncated = len(rows) > limit
        selected_rows = rows[:limit]
        records = tuple(
            _functional_temporal_record_from_row(row) for row in reversed(selected_rows)
        )
        return records, truncated

    def functional_temporal_history(
        self,
        *,
        limit: int = 240,
        asset_id: str | None = None,
        episode_id: str | None = None,
        cycle_id: str | None = None,
        phase_id: str | None = None,
        record_kind: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Return bounded functional-temporal evidence in chronological order."""

        records, truncated = self.select_functional_temporal_records(
            limit=limit,
            asset_id=asset_id,
            episode_id=episode_id,
            cycle_id=cycle_id,
            phase_id=phase_id,
            record_kind=record_kind,
            from_time=from_time,
            to_time=to_time,
        )
        return {
            "schema_version": "linealert.historian.functional-temporal-history.v1",
            "persistence": "timescaledb",
            "count": len(records),
            "truncated": truncated,
            "truncation_semantic": ("older_matching_records_omitted" if truncated else None),
            "from_time": from_time.isoformat() if from_time is not None else None,
            "to_time": to_time.isoformat() if to_time is not None else None,
            "records": [_functional_temporal_record_to_payload(record) for record in records],
        }

    def observation_history(
        self,
        *,
        limit: int = 240,
        asset_id: str | None = None,
    ) -> dict[str, Any]:
        bounded_limit = max(1, min(limit, 5000))
        params: tuple[Any, ...]
        if asset_id:
            query = """
                SELECT payload FROM machine_observations
                WHERE asset_id = %s ORDER BY observed_at DESC LIMIT %s
            """
            params = (asset_id, bounded_limit)
        else:
            query = "SELECT payload FROM machine_observations ORDER BY observed_at DESC LIMIT %s"
            params = (bounded_limit,)
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return {
            "schema_version": "linealert.historian.observation-history.v1",
            "persistence": "timescaledb",
            "count": len(rows),
            "observations": [row[0] for row in reversed(rows)],
        }

    def episode(self, episode_id: str, *, limit: int = 1000) -> dict[str, Any]:
        conditions = self.condition_history(episode_id=episode_id, limit=limit)
        functional_temporal = self.functional_temporal_history(
            episode_id=episode_id,
            limit=limit,
        )
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT recorded_at, outcome_id, asset_id, relationship_id, outcome_type,
                       status, actor_role, note, related_observation_id, verification_value,
                       verification_unit, verification_status, details
                FROM operational_outcomes
                WHERE episode_id = %s ORDER BY recorded_at ASC LIMIT %s
                """,
                (episode_id, max(1, min(limit, 5000))),
            )
            rows = cursor.fetchall()
        outcomes = [
            {
                "recorded_at": row[0].isoformat(),
                "outcome_id": row[1],
                "asset_id": row[2],
                "relationship_id": row[3],
                "outcome_type": row[4],
                "status": row[5],
                "actor_role": row[6],
                "note": row[7],
                "related_observation_id": row[8],
                "verification_value": row[9],
                "verification_unit": row[10],
                "verification_status": row[11],
                "details": row[12],
            }
            for row in rows
        ]
        return {
            "schema_version": "linealert.historian.episode.v1",
            "episode_id": episode_id,
            "condition_measurements": conditions["measurements"],
            "functional_temporal_evidence": functional_temporal["records"],
            "outcomes": outcomes,
            "claim_boundary": (
                "A shared timeline preserves association and sequence. It does not by itself "
                "prove physical root cause or predictive validity."
            ),
        }


def _validate_optional_history_time(value: datetime | None, field_name: str) -> None:
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() is None:
        raise HistorianQueryError(f"{field_name} must be timezone-aware")


def _condition_history_record_from_row(
    row: tuple[Any, ...],
) -> ConditionHistoryRecord:
    return ConditionHistoryRecord(
        observed_at=row[0],
        observation_id=row[1],
        episode_id=row[2],
        asset_id=row[3],
        relationship_id=row[4],
        signal=row[5],
        value=row[6],
        unit=row[7],
        min_value=row[8],
        max_value=row[9],
        temporal_rule_status=row[10],
        quality=row[11],
        reason_code=row[12],
        correlation_id=row[13],
        topology_from=row[14],
        topology_to=row[15],
        source_mode=row[16],
        cycle_id=row[17],
        phase_id=row[18],
        operating_context=row[19] or {},
        evidence_authority=row[20],
        clock_evidence=row[21] or {},
    )


def _condition_history_record_to_payload(
    record: ConditionHistoryRecord,
) -> dict[str, Any]:
    return {
        "observed_at": record.observed_at.isoformat(),
        "observation_id": record.observation_id,
        "episode_id": record.episode_id,
        "asset_id": record.asset_id,
        "relationship_id": record.relationship_id,
        "signal": record.signal,
        "value": record.value,
        "unit": record.unit,
        "min_value": record.min_value,
        "max_value": record.max_value,
        "temporal_rule_status": record.temporal_rule_status,
        "quality": record.quality,
        "reason_code": record.reason_code,
        "correlation_id": record.correlation_id,
        "topology_from": record.topology_from,
        "topology_to": record.topology_to,
        "source_mode": record.source_mode,
        "cycle_id": record.cycle_id,
        "phase_id": record.phase_id,
        "operating_context": dict(record.operating_context),
        "evidence_authority": (
            dict(record.evidence_authority) if record.evidence_authority is not None else None
        ),
        "clock_evidence": dict(record.clock_evidence),
    }


def _functional_temporal_record_from_row(
    row: tuple[Any, ...],
) -> FunctionalTemporalHistoryRecord:
    transition_disposition = TransitionDisposition(row[12]) if row[12] is not None else None
    return FunctionalTemporalHistoryRecord(
        observed_at=row[0],
        record_id=row[1],
        episode_id=row[2],
        cycle_id=row[4],
        record_kind=FunctionalTemporalRecordKind(row[5]),
        state=EpistemicState(row[13]),
        validity=EvidenceValidity(row[14]),
        coverage=TemporalCoverage(row[15]),
        source_id=row[16],
        operating_context=HistorianOperatingContext(
            asset_id=row[3],
            component_id=row[17],
            profile_id=row[18],
            operating_mode=row[19],
            configuration_version=row[20],
            firmware_version=row[21],
            calibration_id=row[22],
            sampling_profile_id=row[23],
            recipe_id=row[24],
            product_id=row[25],
            context_tags=row[26],
        ),
        phase_id=row[6],
        transition_id=row[7],
        from_phase_id=row[8],
        to_phase_id=row[9],
        trigger_event_id=row[10],
        requirement_id=row[11],
        transition_disposition=transition_disposition,
        evidence_ids=tuple(row[27]),
        reasons=tuple(row[28]),
        clock_evidence=row[29],
        details=row[30],
    )


def _functional_temporal_record_to_payload(
    record: FunctionalTemporalHistoryRecord,
) -> dict[str, Any]:
    context = record.operating_context
    return {
        "observed_at": record.observed_at.isoformat(),
        "record_id": record.record_id,
        "episode_id": record.episode_id,
        "asset_id": context.asset_id,
        "cycle_id": record.cycle_id,
        "record_kind": record.record_kind.value,
        "phase_id": record.phase_id,
        "transition_id": record.transition_id,
        "from_phase_id": record.from_phase_id,
        "to_phase_id": record.to_phase_id,
        "trigger_event_id": record.trigger_event_id,
        "requirement_id": record.requirement_id,
        "transition_disposition": (
            record.transition_disposition.value
            if record.transition_disposition is not None
            else None
        ),
        "epistemic_state": record.state.value,
        "evidence_validity": record.validity.value,
        "temporal_coverage": record.coverage.value,
        "source_id": record.source_id,
        "operating_context": {
            "component_id": context.component_id,
            "profile_id": context.profile_id,
            "operating_mode": context.operating_mode,
            "configuration_version": context.configuration_version,
            "firmware_version": context.firmware_version,
            "calibration_id": context.calibration_id,
            "sampling_profile_id": context.sampling_profile_id,
            "recipe_id": context.recipe_id,
            "product_id": context.product_id,
            "context_tags": dict(context.context_tags),
        },
        "evidence_ids": list(record.evidence_ids),
        "reasons": list(record.reasons),
        "clock_evidence": dict(record.clock_evidence),
        "details": dict(record.details),
    }
