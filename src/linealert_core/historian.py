"""Optional TimescaleDB persistence for shared LineAlert operational history.

The historian is an adapter boundary. Writes happen only after deterministic
admission/derivation has succeeded; database durability is not part of the
core transaction or rollback guarantee.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from .live_condition import LiveConditionMeasurement


class HistorianError(RuntimeError):
    """Raised when the optional historian cannot be configured or queried."""


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
                    source_mode, clock_evidence
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
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

    def condition_history(
        self,
        *,
        limit: int = 240,
        asset_id: str | None = None,
        relationship_id: str | None = None,
        episode_id: str | None = None,
    ) -> dict[str, Any]:
        bounded_limit = max(1, min(limit, 5000))
        where: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("asset_id", asset_id),
            ("relationship_id", relationship_id),
            ("episode_id", episode_id),
        ):
            if value:
                where.append(f"{column} = %s")
                params.append(value)
        predicate = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(bounded_limit)
        query = f"""
            SELECT observed_at, observation_id, episode_id, asset_id, relationship_id,
                   signal_name, value, unit, min_value, max_value, temporal_rule_status,
                   quality, reason_code, correlation_id, topology_from, topology_to,
                   source_mode, clock_evidence
            FROM condition_measurements
            {predicate}
            ORDER BY observed_at DESC
            LIMIT %s
        """
        with self._lock, self._connection.cursor() as cursor:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
        measurements = [
            {
                "observed_at": row[0].isoformat(),
                "observation_id": row[1],
                "episode_id": row[2],
                "asset_id": row[3],
                "relationship_id": row[4],
                "signal": row[5],
                "value": row[6],
                "unit": row[7],
                "min_value": row[8],
                "max_value": row[9],
                "temporal_rule_status": row[10],
                "quality": row[11],
                "reason_code": row[12],
                "correlation_id": row[13],
                "topology_from": row[14],
                "topology_to": row[15],
                "source_mode": row[16],
                "clock_evidence": row[17],
            }
            for row in reversed(rows)
        ]
        return {
            "schema_version": "linealert.historian.condition-history.v1",
            "persistence": "timescaledb",
            "count": len(measurements),
            "measurements": measurements,
        }

    def observation_history(
        self,
        *,
        limit: int = 240,
        asset_id: str | None = None,
    ) -> dict[str, Any]:
        bounded_limit = max(1, min(limit, 5000))
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
            "outcomes": outcomes,
            "claim_boundary": (
                "A shared timeline preserves association and sequence. It does not by itself "
                "prove physical root cause or predictive validity."
            ),
        }
