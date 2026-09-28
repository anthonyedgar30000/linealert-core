"""Deterministic live historian emulation for the local LineAlert demo.

This module intentionally models historian-shaped evidence without claiming
TimescaleDB, physical equipment state, or causal authority.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

from .functional_temporal import (
    EpistemicState,
    EvidenceValidity,
    TemporalCoverage,
)
from .historian import (
    ConditionHistoryRecord,
    FunctionalTemporalHistoryRecord,
    FunctionalTemporalRecordKind,
    HistorianOperatingContext,
)

ASSET_ID = "LABELER-DEMO-01"
PROFILE_ID = "generic-pressure-sensitive-labeler-demo-v1"
SOURCE_ID = "linealert-historian-emulator-v1"
SOURCE_MODE = "controlled_synthetic_live_emulation"
PERSISTENCE = "sqlite_local_emulated"
SCHEMA_VERSION = "linealert.emulated-historian.v1"
SCENARIO_LENGTH = 48


class HistorianEmulatorError(RuntimeError):
    """Raised when local emulated historian state cannot be retained or queried."""


@dataclass(frozen=True, slots=True)
class EmulatedCycle:
    sequence: int
    episode_id: str
    cycle_id: str
    scenario_phase: str
    label_presentation_delay_ms: float
    bottle_spacing_delay_ms: float
    line_speed_cpm: float
    reject_candidate: bool


def _repeat(values: tuple[float, ...], index: int) -> float:
    return values[index % len(values)]


def cycle_profile(sequence: int) -> EmulatedCycle:
    """Return one deterministic packaging-line cycle profile."""

    if sequence < 0:
        raise HistorianEmulatorError("sequence must be non-negative")
    position = sequence % SCENARIO_LENGTH
    episode = sequence // SCENARIO_LENGTH

    if position < 16:
        phase = "stable_reference"
        label_delay = _repeat((224.0, 231.0, 238.0, 227.0, 243.0, 235.0), position)
    elif position < 24:
        phase = "incipient_presentation_drift"
        label_delay = (280.0, 292.0, 307.0, 322.0, 338.0, 356.0, 374.0, 392.0)[
            position - 16
        ]
    elif position < 36:
        phase = "persistent_presentation_drift"
        label_delay = (
            418.0,
            436.0,
            461.0,
            487.0,
            514.0,
            542.0,
            505.0,
            472.0,
            448.0,
            421.0,
            397.0,
            455.0,
        )[position - 24]
    elif position < 40:
        phase = "bounded_diagnostic_observation"
        label_delay = (432.0, 401.0, 372.0, 344.0)[position - 36]
    else:
        phase = "post_intervention_observation"
        label_delay = (306.0, 291.0, 278.0, 266.0, 255.0, 248.0, 241.0, 236.0)[
            position - 40
        ]

    spacing_delay = _repeat((182.0, 194.0, 201.0, 188.0, 207.0, 197.0), sequence)
    line_speed = _repeat((71.8, 72.1, 72.0, 71.9, 72.2, 72.0), sequence)
    reject_candidate = label_delay > 350.0 and position % 3 == 1

    return EmulatedCycle(
        sequence=sequence,
        episode_id=f"emulated-labeler2-{episode:04d}",
        cycle_id=f"emu-cycle-{sequence:08d}",
        scenario_phase=phase,
        label_presentation_delay_ms=label_delay,
        bottle_spacing_delay_ms=spacing_delay,
        line_speed_cpm=line_speed,
        reject_candidate=reject_candidate,
    )


def _context(
    *,
    component_id: str,
    scenario_phase: str,
    config_sha256: str,
) -> HistorianOperatingContext:
    return HistorianOperatingContext(
        asset_id=ASSET_ID,
        component_id=component_id,
        profile_id=PROFILE_ID,
        operating_mode="500ml-round-bottle",
        configuration_version="demo-config-v1",
        firmware_version="emulator-fw-2026.09",
        calibration_id="synthetic-cal-2026-09",
        sampling_profile_id="emulated-cycle-2s",
        recipe_id="500ml-round-bottle",
        product_id="synthetic-500ml-bottle",
        context_tags={
            "source_classification": "controlled_synthetic_demo",
            "scenario_phase": scenario_phase,
            "config_sha256": config_sha256,
            "physical_state_authority": "false",
        },
    )


def _clock_evidence() -> dict[str, str]:
    return {
        "start_clock_quality": "synchronized_emulator_clock",
        "end_clock_quality": "synchronized_emulator_clock",
        "basis": "single_process_monotonic_emulator_projection",
        "retained_uncertainty": "synthetic clock model; no physical clock authority",
    }


def functional_temporal_records(
    cycle: EmulatedCycle,
    observed_at: datetime,
    *,
    config_sha256: str,
) -> tuple[FunctionalTemporalHistoryRecord, ...]:
    """Build bounded functional-temporal evidence for one emulated cycle."""

    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise HistorianEmulatorError("observed_at must be timezone-aware")

    label_within = 50.0 <= cycle.label_presentation_delay_ms <= 350.0
    spacing_within = 100.0 <= cycle.bottle_spacing_delay_ms <= 400.0

    label_state = EpistemicState.VERIFIED if label_within else EpistemicState.VIOLATED
    spacing_state = EpistemicState.VERIFIED if spacing_within else EpistemicState.VIOLATED
    label_reason = (
        "EVIDENCE.EMULATED_TIMING_WITHIN_ENVELOPE"
        if label_within
        else "CONDITION.OUTSIDE_EXPECTED_ENVELOPE"
    )
    spacing_reason = (
        "EVIDENCE.EMULATED_TIMING_WITHIN_ENVELOPE"
        if spacing_within
        else "CONDITION.OUTSIDE_EXPECTED_ENVELOPE"
    )

    return (
        FunctionalTemporalHistoryRecord(
            observed_at=observed_at,
            record_id=f"FT:{cycle.cycle_id}:label-presentation",
            episode_id=cycle.episode_id,
            cycle_id=cycle.cycle_id,
            record_kind=FunctionalTemporalRecordKind.GUARD,
            state=label_state,
            validity=EvidenceValidity.CURRENT,
            coverage=TemporalCoverage.POINT_ONLY,
            source_id=SOURCE_ID,
            operating_context=_context(
                component_id="label-present-sensor",
                scenario_phase=cycle.scenario_phase,
                config_sha256=config_sha256,
            ),
            phase_id="LABEL_APPLICATION",
            requirement_id="relationship:label-presentation-delay",
            evidence_ids=(
                f"{cycle.cycle_id}:label-feed-command",
                f"{cycle.cycle_id}:label-at-peel-point",
            ),
            reasons=(label_reason,),
            clock_evidence=_clock_evidence(),
            details={
                "signal": "label_presentation_delay_ms",
                "value": cycle.label_presentation_delay_ms,
                "unit": "ms",
                "min_value": 50.0,
                "max_value": 350.0,
                "scenario_phase": cycle.scenario_phase,
                "emulated": True,
            },
        ),
        FunctionalTemporalHistoryRecord(
            observed_at=observed_at + timedelta(milliseconds=1),
            record_id=f"FT:{cycle.cycle_id}:bottle-spacing",
            episode_id=cycle.episode_id,
            cycle_id=cycle.cycle_id,
            record_kind=FunctionalTemporalRecordKind.GUARD,
            state=spacing_state,
            validity=EvidenceValidity.CURRENT,
            coverage=TemporalCoverage.POINT_ONLY,
            source_id=SOURCE_ID,
            operating_context=_context(
                component_id="spacing-conveyor",
                scenario_phase=cycle.scenario_phase,
                config_sha256=config_sha256,
            ),
            phase_id="PRESENTATION",
            requirement_id="relationship:bottle-spacing-delay",
            evidence_ids=(
                f"{cycle.cycle_id}:bottle-detected",
                f"{cycle.cycle_id}:spacing-confirmed",
            ),
            reasons=(spacing_reason,),
            clock_evidence=_clock_evidence(),
            details={
                "signal": "bottle_spacing_delay_ms",
                "value": cycle.bottle_spacing_delay_ms,
                "unit": "ms",
                "min_value": 100.0,
                "max_value": 400.0,
                "scenario_phase": cycle.scenario_phase,
                "emulated": True,
            },
        ),
    )
def condition_records(
    cycle: EmulatedCycle,
    observed_at: datetime,
    *,
    config_sha256: str,
) -> tuple[ConditionHistoryRecord, ...]:
    """Build condition evidence for what changed and what held."""

    label_within = cycle.label_presentation_delay_ms <= 350.0
    spacing_within = cycle.bottle_spacing_delay_ms <= 400.0
    operating_context = {
        "profile_id": PROFILE_ID,
        "operating_mode": "500ml-round-bottle",
        "configuration_version": "demo-config-v1",
        "firmware_version": "emulator-fw-2026.09",
        "calibration_id": "synthetic-cal-2026-09",
        "sampling_profile_id": "emulated-cycle-2s",
        "recipe_id": "500ml-round-bottle",
        "scenario_phase": cycle.scenario_phase,
        "config_sha256": config_sha256,
        "source_classification": "controlled_synthetic_demo",
    }
    authority = {
        "schema_version": "linealert.emulated-evidence-authority.v1",
        "authority_scope": "CONTROLLED_SYNTHETIC_EMULATION_ONLY",
        "physical_state_authority": False,
        "production_authority": False,
        "config_sha256": config_sha256,
    }

    return (
        ConditionHistoryRecord(
            observed_at=observed_at,
            observation_id=f"COND:{cycle.cycle_id}:label-presentation",
            episode_id=cycle.episode_id,
            asset_id=ASSET_ID,
            relationship_id="relationship:label-presentation-delay",
            signal="label_presentation_delay_ms",
            value=cycle.label_presentation_delay_ms,
            unit="ms",
            min_value=50.0,
            max_value=350.0,
            temporal_rule_status="within" if label_within else "late",
            quality="good",
            reason_code=(
                "EVIDENCE.EMULATED_RELATIONSHIP_DELAY_MEASURED"
                if label_within
                else "CONDITION.OUTSIDE_EXPECTED_ENVELOPE"
            ),
            correlation_id=cycle.cycle_id,
            topology_from="LabelFeedCommand",
            topology_to="LabelAtPeelPoint",
            source_mode=SOURCE_MODE,
            cycle_id=cycle.cycle_id,
            phase_id="LABEL_APPLICATION",
            operating_context=operating_context,
            evidence_authority=authority,
            clock_evidence=_clock_evidence(),
        ),
        ConditionHistoryRecord(
            observed_at=observed_at + timedelta(milliseconds=1),
            observation_id=f"COND:{cycle.cycle_id}:bottle-spacing",
            episode_id=cycle.episode_id,
            asset_id=ASSET_ID,
            relationship_id="relationship:bottle-spacing-delay",
            signal="bottle_spacing_delay_ms",
            value=cycle.bottle_spacing_delay_ms,
            unit="ms",
            min_value=100.0,
            max_value=400.0,
            temporal_rule_status="within" if spacing_within else "late",
            quality="good",
            reason_code="EVIDENCE.EMULATED_RELATIONSHIP_DELAY_MEASURED",
            correlation_id=cycle.cycle_id,
            topology_from="BottleDetected",
            topology_to="SpacingConfirmed",
            source_mode=SOURCE_MODE,
            cycle_id=cycle.cycle_id,
            phase_id="PRESENTATION",
            operating_context=operating_context,
            evidence_authority=authority,
            clock_evidence=_clock_evidence(),
        ),
    )


def machine_observation(cycle: EmulatedCycle, observed_at: datetime) -> dict[str, Any]:
    return {
        "schema_version": "linealert.observation.snapshot.v1",
        "observation_id": f"OBS:{cycle.cycle_id}",
        "connected": True,
        "profile": PROFILE_ID,
        "source_id": SOURCE_ID,
        "source_kind": "historian_emulator",
        "source_scope": "controlled_synthetic_demo",
        "asset_id": ASSET_ID,
        "read_only": True,
        "proxy_warning": "Synthetic live historian evidence; not verified physical machine state.",
        "bridge_timestamp": observed_at.isoformat(),
        "observation_sequence": cycle.sequence,
        "reason_code": "EVIDENCE.EMULATED_HISTORIAN_SAMPLE",
        "operating_context": {
            "operating_mode": "500ml-round-bottle",
            "configuration_version": "demo-config-v1",
            "scenario_phase": cycle.scenario_phase,
        },
        "signals": {
            "line_speed_cpm": {
                "value": cycle.line_speed_cpm,
                "unit": "containers/min",
                "quality": "good",
            },
            "label_presentation_delay_ms": {
                "value": cycle.label_presentation_delay_ms,
                "unit": "ms",
                "quality": "good",
            },
            "bottle_spacing_delay_ms": {
                "value": cycle.bottle_spacing_delay_ms,
                "unit": "ms",
                "quality": "good",
            },
            "reject_candidate": {
                "value": cycle.reject_candidate,
                "unit": "boolean",
                "quality": "good",
            },
        },
    }


def _functional_payload(record: FunctionalTemporalHistoryRecord) -> dict[str, Any]:
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


def _condition_payload(record: ConditionHistoryRecord) -> dict[str, Any]:
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
            dict(record.evidence_authority)
            if record.evidence_authority is not None
            else None
        ),
        "clock_evidence": dict(record.clock_evidence),
    }
class EmulatedHistorianStore:
    """SQLite-backed bounded store for deterministic live emulation."""

    def __init__(
        self,
        database_path: Path,
        *,
        config_path: Path,
        retention_cycles: int = 1800,
    ) -> None:
        if retention_cycles < SCENARIO_LENGTH:
            raise HistorianEmulatorError(
                f"retention_cycles must be at least {SCENARIO_LENGTH}"
            )
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            config_bytes = Path(config_path).read_bytes()
        except OSError as exc:
            raise HistorianEmulatorError(
                f"cannot read emulation config: {config_path}"
            ) from exc
        self.config_sha256 = sha256(config_bytes).hexdigest()
        self.retention_cycles = retention_cycles
        self._lock = threading.RLock()
        try:
            self._connection = sqlite3.connect(
                self.database_path,
                check_same_thread=False,
                isolation_level=None,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA busy_timeout=5000")
            self._ensure_schema()
        except sqlite3.Error as exc:
            raise HistorianEmulatorError("cannot open emulated historian store") from exc

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _ensure_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS functional_temporal (
                sequence INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                record_id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                phase_id TEXT,
                record_kind TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ft_time_idx
                ON functional_temporal(observed_at DESC, record_id DESC);
            CREATE INDEX IF NOT EXISTS ft_episode_idx
                ON functional_temporal(episode_id, observed_at DESC);
            CREATE TABLE IF NOT EXISTS condition_measurements (
                sequence INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                observation_id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                relationship_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                phase_id TEXT,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS condition_time_idx
                ON condition_measurements(observed_at DESC, observation_id DESC);
            CREATE INDEX IF NOT EXISTS condition_episode_idx
                ON condition_measurements(episode_id, observed_at DESC);
            CREATE TABLE IF NOT EXISTS machine_observations (
                sequence INTEGER PRIMARY KEY,
                observed_at TEXT NOT NULL,
                observation_id TEXT NOT NULL UNIQUE,
                asset_id TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS observation_time_idx
                ON machine_observations(observed_at DESC);
            """
        )

    def _next_sequence(self) -> int:
        row = self._connection.execute(
            "SELECT value FROM metadata WHERE key = 'next_sequence'"
        ).fetchone()
        return int(row["value"]) if row is not None else 0

    def retained_cycle_count(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM machine_observations"
            ).fetchone()
            return int(row["count"])

    def latest_cycle(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT sequence, observed_at, payload
                FROM machine_observations
                ORDER BY sequence DESC LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            payload = json.loads(row["payload"])
            return {
                "sequence": int(row["sequence"]),
                "observed_at": str(row["observed_at"]),
                "cycle_id": payload.get("observation_id", "").removeprefix("OBS:"),
                "scenario_phase": payload.get("operating_context", {}).get(
                    "scenario_phase"
                ),
            }

    def seed_window(
        self,
        *,
        cycles: int,
        interval_seconds: float,
        now: datetime | None = None,
    ) -> None:
        if cycles < 0:
            raise HistorianEmulatorError("seed cycles must be non-negative")
        if interval_seconds <= 0:
            raise HistorianEmulatorError("interval_seconds must be positive")
        with self._lock:
            if self.retained_cycle_count() > 0:
                return
        anchor = now or datetime.now(UTC)
        for offset in range(cycles, 0, -1):
            self.append_next_cycle(
                observed_at=anchor - timedelta(seconds=offset * interval_seconds)
            )

    def append_next_cycle(
        self,
        *,
        observed_at: datetime | None = None,
    ) -> EmulatedCycle:
        timestamp = observed_at or datetime.now(UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise HistorianEmulatorError("observed_at must be timezone-aware")

        with self._lock:
            sequence = self._next_sequence()
            cycle = cycle_profile(sequence)
            ft_records = functional_temporal_records(
                cycle,
                timestamp,
                config_sha256=self.config_sha256,
            )
            condition_items = condition_records(
                cycle,
                timestamp,
                config_sha256=self.config_sha256,
            )
            observation = machine_observation(cycle, timestamp)

            try:
                self._connection.execute("BEGIN IMMEDIATE")
                for record in ft_records:
                    payload = _functional_payload(record)
                    self._connection.execute(
                        """
                        INSERT INTO functional_temporal (
                            sequence, observed_at, record_id, episode_id, asset_id,
                            cycle_id, phase_id, record_kind, payload
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            sequence,
                            payload["observed_at"],
                            payload["record_id"],
                            payload["episode_id"],
                            payload["asset_id"],
                            payload["cycle_id"],
                            payload["phase_id"],
                            payload["record_kind"],
                            json.dumps(payload, sort_keys=True, separators=(",", ":")),
                        ),
                    )
                for record in condition_items:
                    payload = _condition_payload(record)
                    self._connection.execute(
                        """
                        INSERT INTO condition_measurements (
                            sequence, observed_at, observation_id, episode_id, asset_id,
                            relationship_id, cycle_id, phase_id, payload
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            sequence,
                            payload["observed_at"],
                            payload["observation_id"],
                            payload["episode_id"],
                            payload["asset_id"],
                            payload["relationship_id"],
                            payload["cycle_id"],
                            payload["phase_id"],
                            json.dumps(payload, sort_keys=True, separators=(",", ":")),
                        ),
                    )
                self._connection.execute(
                    """
                    INSERT INTO machine_observations (
                        sequence, observed_at, observation_id, asset_id, payload
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        sequence,
                        timestamp.isoformat(),
                        observation["observation_id"],
                        ASSET_ID,
                        json.dumps(observation, sort_keys=True, separators=(",", ":")),
                    ),
                )
                self._connection.execute(
                    """
                    INSERT INTO metadata(key, value) VALUES('next_sequence', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (str(sequence + 1),),
                )
                cutoff = sequence - self.retention_cycles
                if cutoff >= 0:
                    for table in (
                        "functional_temporal",
                        "condition_measurements",
                        "machine_observations",
                    ):
                        self._connection.execute(
                            f"DELETE FROM {table} WHERE sequence <= ?",
                            (cutoff,),
                        )
                self._connection.execute("COMMIT")
            except sqlite3.Error as exc:
                self._connection.execute("ROLLBACK")
                raise HistorianEmulatorError(
                    "failed to atomically append emulated historian cycle"
                ) from exc
            return cycle
    @staticmethod
    def _bounded_limit(limit: int) -> int:
        if limit < 1 or limit > 5000:
            raise HistorianEmulatorError("history limit must be between 1 and 5000")
        return limit

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
        limit = self._bounded_limit(limit)
        where, params = _history_filters(
            asset_id=asset_id,
            episode_id=episode_id,
            cycle_id=cycle_id,
            phase_id=phase_id,
            from_time=from_time,
            to_time=to_time,
        )
        if record_kind:
            try:
                FunctionalTemporalRecordKind(record_kind)
            except ValueError as exc:
                raise HistorianEmulatorError("record_kind is invalid") from exc
            where.append("record_kind = ?")
            params.append(record_kind)
        predicate = " WHERE " + " AND ".join(where) if where else ""
        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT payload FROM functional_temporal
                {predicate}
                ORDER BY observed_at DESC, record_id DESC
                LIMIT ?
                """,
                (*params, limit + 1),
            ).fetchall()
        truncated = len(rows) > limit
        selected = list(reversed(rows[:limit]))
        return {
            "schema_version": "linealert.historian.functional-temporal-history.v1",
            "persistence": PERSISTENCE,
            "source_mode": SOURCE_MODE,
            "emulated": True,
            "count": len(selected),
            "truncated": truncated,
            "truncation_semantic": (
                "older_matching_records_omitted" if truncated else None
            ),
            "from_time": from_time.isoformat() if from_time else None,
            "to_time": to_time.isoformat() if to_time else None,
            "records": [json.loads(row["payload"]) for row in selected],
        }

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
        limit = self._bounded_limit(limit)
        where, params = _history_filters(
            asset_id=asset_id,
            episode_id=episode_id,
            cycle_id=cycle_id,
            phase_id=phase_id,
            from_time=from_time,
            to_time=to_time,
        )
        if relationship_id:
            where.append("relationship_id = ?")
            params.append(relationship_id)
        predicate = " WHERE " + " AND ".join(where) if where else ""
        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT payload FROM condition_measurements
                {predicate}
                ORDER BY observed_at DESC, observation_id DESC
                LIMIT ?
                """,
                (*params, limit + 1),
            ).fetchall()
        truncated = len(rows) > limit
        selected = list(reversed(rows[:limit]))
        return {
            "schema_version": "linealert.historian.condition-history.v1",
            "persistence": PERSISTENCE,
            "source_mode": SOURCE_MODE,
            "emulated": True,
            "count": len(selected),
            "truncated": truncated,
            "truncation_semantic": (
                "older_matching_records_omitted" if truncated else None
            ),
            "from_time": from_time.isoformat() if from_time else None,
            "to_time": to_time.isoformat() if to_time else None,
            "measurements": [json.loads(row["payload"]) for row in selected],
        }

    def observation_history(
        self,
        *,
        limit: int = 240,
        asset_id: str | None = None,
    ) -> dict[str, Any]:
        limit = self._bounded_limit(limit)
        where: list[str] = []
        params: list[Any] = []
        if asset_id:
            where.append("asset_id = ?")
            params.append(asset_id)
        predicate = " WHERE " + " AND ".join(where) if where else ""
        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT payload FROM machine_observations
                {predicate}
                ORDER BY observed_at DESC, observation_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return {
            "schema_version": "linealert.historian.observation-history.v1",
            "persistence": PERSISTENCE,
            "source_mode": SOURCE_MODE,
            "emulated": True,
            "count": len(rows),
            "observations": [json.loads(row["payload"]) for row in reversed(rows)],
        }

    def episode(self, episode_id: str, *, limit: int = 1000) -> dict[str, Any]:
        if not episode_id.strip():
            raise HistorianEmulatorError("episode_id must not be empty")
        return {
            "schema_version": "linealert.historian.episode.v1",
            "episode_id": episode_id,
            "persistence": PERSISTENCE,
            "source_mode": SOURCE_MODE,
            "emulated": True,
            "conditions": self.condition_history(
                episode_id=episode_id,
                limit=limit,
            ),
            "functional_temporal": self.functional_temporal_history(
                episode_id=episode_id,
                limit=limit,
            ),
            "outcomes": [],
            "authority_boundary": (
                "Synthetic historian episode; no physical state, diagnosis, "
                "or production authority is established."
            ),
        }


def _history_filters(
    *,
    asset_id: str | None,
    episode_id: str | None,
    cycle_id: str | None,
    phase_id: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> tuple[list[str], list[Any]]:
    if from_time is not None and (
        from_time.tzinfo is None or from_time.utcoffset() is None
    ):
        raise HistorianEmulatorError("from_time must be timezone-aware")
    if to_time is not None and (to_time.tzinfo is None or to_time.utcoffset() is None):
        raise HistorianEmulatorError("to_time must be timezone-aware")
    if from_time is not None and to_time is not None and from_time > to_time:
        raise HistorianEmulatorError("from_time must be less than or equal to to_time")

    where: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("asset_id", asset_id),
        ("episode_id", episode_id),
        ("cycle_id", cycle_id),
        ("phase_id", phase_id),
    ):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    if from_time is not None:
        where.append("observed_at >= ?")
        params.append(from_time.isoformat())
    if to_time is not None:
        where.append("observed_at <= ?")
        params.append(to_time.isoformat())
    return where, params
