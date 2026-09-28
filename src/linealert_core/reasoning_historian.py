"""Read-only Timescale retrieval for governed Reasoning Node condition history."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol

from .reasoning_context import EvidenceCandidate, EvidenceRole, RetrievalMethod


class ReasoningHistorianError(RuntimeError):
    """Raised when governed historian retrieval cannot be established safely."""


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReasoningHistorianError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_text(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _text(name, value)


def _aware_time(name: str, value: datetime | None) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ReasoningHistorianError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class HistorianConditionQuery:
    """Exact bounded historian query owned by the Reasoning Node."""

    asset_id: str
    relationship_id: str | None = None
    episode_id: str | None = None
    cycle_id: str | None = None
    phase_id: str | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None
    limit: int = 240

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_id", _text("asset_id", self.asset_id))
        for name in ("relationship_id", "episode_id", "cycle_id", "phase_id"):
            object.__setattr__(self, name, _optional_text(name, getattr(self, name)))
        _aware_time("from_time", self.from_time)
        _aware_time("to_time", self.to_time)
        if (
            self.from_time is not None
            and self.to_time is not None
            and self.from_time > self.to_time
        ):
            raise ReasoningHistorianError("from_time must be less than or equal to to_time")
        if type(self.limit) is not int or self.limit < 1 or self.limit > 5000:
            raise ReasoningHistorianError("limit must be an integer between 1 and 5000")


@dataclass(frozen=True, slots=True)
class HistorianRetrievalAuthority:
    """Current config identity expected to match retained write-time authority."""

    asset_id: str
    profile_id: str
    source_name: str
    source_sha256: str

    def __post_init__(self) -> None:
        for name in ("asset_id", "profile_id", "source_name", "source_sha256"):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        if len(self.source_sha256) != 64 or any(
            char not in "0123456789abcdefABCDEF" for char in self.source_sha256
        ):
            raise ReasoningHistorianError("source_sha256 must be a 64-character hexadecimal digest")
        object.__setattr__(self, "source_sha256", self.source_sha256.lower())


class ConditionHistorySource(Protocol):
    """Minimal source contract consumed by deterministic retrieval."""

    source_id: str
    read_only_verified: bool

    def select_condition_history(
        self,
        query: HistorianConditionQuery,
    ) -> tuple[tuple[Mapping[str, Any], ...], bool]:
        """Return chronological records and whether older matches were truncated."""


@dataclass(frozen=True, slots=True)
class HistorianRetrievalRefusal:
    observation_id: str | None
    reason_code: str


@dataclass(frozen=True, slots=True)
class HistorianConditionRetrieval:
    """Deterministic retrieval handoff for the reasoning context assembler."""

    query: HistorianConditionQuery
    source_id: str
    candidates: tuple[EvidenceCandidate, ...]
    refusals: tuple[HistorianRetrievalRefusal, ...]
    truncated: bool
    read_only_verified: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "linealert.reasoning-historian-retrieval.v1",
            "source_id": self.source_id,
            "query": {
                "asset_id": self.query.asset_id,
                "relationship_id": self.query.relationship_id,
                "episode_id": self.query.episode_id,
                "cycle_id": self.query.cycle_id,
                "phase_id": self.query.phase_id,
                "from_time": self.query.from_time.isoformat() if self.query.from_time else None,
                "to_time": self.query.to_time.isoformat() if self.query.to_time else None,
                "limit": self.query.limit,
            },
            "candidate_count": len(self.candidates),
            "refusal_count": len(self.refusals),
            "truncated": self.truncated,
            "read_only_verified": self.read_only_verified,
            "refusals": [
                {
                    "observation_id": item.observation_id,
                    "reason_code": item.reason_code,
                }
                for item in self.refusals
            ],
            "claim_boundary": (
                "Historian retrieval preserves recorded evidence and provenance. "
                "It does not establish current physical state, diagnosis, root cause, "
                "or authorized action."
            ),
            "authorized_action": False,
        }


_CONDITION_COLUMNS = """
    observed_at, observation_id, episode_id, asset_id, relationship_id,
    signal_name, value, unit, min_value, max_value, temporal_rule_status,
    quality, reason_code, correlation_id, topology_from, topology_to,
    source_mode, cycle_id, phase_id, operating_context, evidence_authority,
    clock_evidence
"""


def _row_to_record(row: Sequence[Any]) -> Mapping[str, Any]:
    if len(row) != 22:
        raise ReasoningHistorianError("condition history row does not match expected schema")
    observed_at = row[0]
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
        raise ReasoningHistorianError("condition history observed_at must be timezone-aware")
    if observed_at.utcoffset() is None:
        raise ReasoningHistorianError("condition history observed_at must be timezone-aware")
    operating_context = row[19] if isinstance(row[19], Mapping) else {}
    authority = row[20] if isinstance(row[20], Mapping) else None
    clock_evidence = row[21] if isinstance(row[21], Mapping) else {}
    return MappingProxyType(
        {
            "observed_at": observed_at.isoformat(),
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
            "cycle_id": row[17],
            "phase_id": row[18],
            "operating_context": dict(operating_context),
            "evidence_authority": dict(authority) if authority is not None else None,
            "clock_evidence": dict(clock_evidence),
        }
    )


def _default_connect(dsn: str, **kwargs: Any) -> Any:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - local integration path
        raise ReasoningHistorianError(
            "Install the historian extra: python -m pip install -e '.[historian]'"
        ) from exc
    return psycopg.connect(dsn, **kwargs)


class ReadOnlyTimescaleConditionHistorySource:
    """Timescale condition-history source with a verified read-only database session."""

    def __init__(
        self,
        dsn: str,
        *,
        source_id: str = "timescaledb:condition_measurements",
        connect_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.source_id = _text("source_id", source_id)
        dsn = _text("dsn", dsn)
        connector = connect_factory or _default_connect
        try:
            self._connection = connector(
                dsn,
                autocommit=True,
                options="-c default_transaction_read_only=on",
            )
        except ReasoningHistorianError:
            raise
        except Exception as exc:  # pragma: no cover - database integration path
            raise ReasoningHistorianError(
                f"unable to connect to reasoning historian: {type(exc).__name__}"
            ) from exc
        self.read_only_verified = self._verify_read_only()
        if not self.read_only_verified:
            self._connection.close()
            raise ReasoningHistorianError(
                "historian session did not verify default_transaction_read_only=on"
            )

    def _verify_read_only(self) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute("SHOW default_transaction_read_only")
            row = cursor.fetchone()
        return bool(row) and str(row[0]).strip().lower() == "on"

    def close(self) -> None:
        self._connection.close()

    def select_condition_history(
        self,
        query: HistorianConditionQuery,
    ) -> tuple[tuple[Mapping[str, Any], ...], bool]:
        where = ["asset_id = %s"]
        params: list[Any] = [query.asset_id]
        for column, value in (
            ("relationship_id", query.relationship_id),
            ("episode_id", query.episode_id),
            ("cycle_id", query.cycle_id),
            ("phase_id", query.phase_id),
        ):
            if value is not None:
                where.append(f"{column} = %s")
                params.append(value)
        if query.from_time is not None:
            where.append("observed_at >= %s")
            params.append(query.from_time)
        if query.to_time is not None:
            where.append("observed_at <= %s")
            params.append(query.to_time)
        params.append(query.limit + 1)
        sql = f"""
            SELECT {_CONDITION_COLUMNS}
            FROM condition_measurements
            WHERE {" AND ".join(where)}
            ORDER BY observed_at DESC, observation_id DESC
            LIMIT %s
        """
        with self._connection.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
        truncated = len(rows) > query.limit
        selected = rows[: query.limit]
        records = tuple(_row_to_record(row) for row in reversed(selected))
        return records, truncated


def _record_id(record: Mapping[str, Any]) -> str | None:
    value = record.get("observation_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _authority_reason(
    record: Mapping[str, Any],
    expected: HistorianRetrievalAuthority,
) -> str | None:
    raw = record.get("evidence_authority")
    if not isinstance(raw, Mapping):
        return "HISTORIAN.RETAINED_AUTHORITY_MISSING"
    if raw.get("schema_version") != "linealert.condition-evidence-authority.v1":
        return "HISTORIAN.RETAINED_AUTHORITY_SCHEMA_MISMATCH"
    if raw.get("authority_scope") != "HISTORIAN_WRITE_TIME_POLICY_AUTHORITY":
        return "HISTORIAN.RETAINED_AUTHORITY_SCOPE_MISMATCH"
    config = raw.get("configuration")
    if not isinstance(config, Mapping):
        return "HISTORIAN.RETAINED_CONFIGURATION_MISSING"
    expected_values = {
        "asset_id": expected.asset_id,
        "profile_id": expected.profile_id,
        "source_name": expected.source_name,
        "source_sha256": expected.source_sha256,
    }
    for key, value in expected_values.items():
        if config.get(key) != value:
            return "HISTORIAN.RETAINED_CONFIGURATION_MISMATCH"
    return None


def _candidate_from_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
    authority: HistorianRetrievalAuthority,
) -> EvidenceCandidate:
    observation_id = _record_id(record)
    if observation_id is None:
        raise ReasoningHistorianError("admitted historian record requires observation_id")
    operating_context = record.get("operating_context")
    if not isinstance(operating_context, Mapping):
        operating_context = {}
    config_version = operating_context.get("configuration_version")
    if not isinstance(config_version, str) or not config_version.strip():
        config_version = None
    source_mode = record.get("source_mode")
    tags = {
        "relationship_id": _text("relationship_id", record.get("relationship_id")),
        "episode_id": _text("episode_id", record.get("episode_id")),
    }
    for key in ("cycle_id", "phase_id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            tags[key] = value.strip()
    if isinstance(source_mode, str) and source_mode.strip():
        tags["source_mode"] = source_mode.strip()
    return EvidenceCandidate(
        evidence_id=f"historian.condition:{observation_id}",
        asset_id=_text("asset_id", record.get("asset_id")),
        source_id=source_id,
        source_class="timescaledb_condition_measurement",
        evidence_role=EvidenceRole.HISTORICAL_OBSERVATION,
        retrieval_method=RetrievalMethod.DETERMINISTIC_SCOPE,
        content=dict(record),
        provenance=(
            f"{source_id}:{observation_id}",
            f"config:{authority.source_name}:sha256:{authority.source_sha256.lower()}",
        ),
        semantic_admitted=True,
        binding_verified=True,
        configuration_version=config_version,
        observed_at=_text("observed_at", record.get("observed_at")),
        authority_class="HISTORIAN_WRITE_TIME_POLICY_AUTHORITY",
        tags=tags,
    )


def retrieve_historian_condition_candidates(
    source: ConditionHistorySource,
    query: HistorianConditionQuery,
    authority: HistorianRetrievalAuthority,
) -> HistorianConditionRetrieval:
    """Retrieve condition evidence without granting historian data extra authority."""

    source_id = _text("source_id", source.source_id)
    if query.asset_id != authority.asset_id:
        raise ReasoningHistorianError("query asset_id does not match retrieval authority")
    if source.read_only_verified is not True:
        return HistorianConditionRetrieval(
            query=query,
            source_id=source_id,
            candidates=(),
            refusals=(
                HistorianRetrievalRefusal(
                    observation_id=None,
                    reason_code="HISTORIAN.READ_ONLY_SESSION_UNVERIFIED",
                ),
            ),
            truncated=False,
            read_only_verified=False,
        )

    records, truncated = source.select_condition_history(query)
    if truncated:
        return HistorianConditionRetrieval(
            query=query,
            source_id=source_id,
            candidates=(),
            refusals=(
                HistorianRetrievalRefusal(
                    observation_id=None,
                    reason_code="HISTORIAN.RETRIEVAL_TRUNCATED",
                ),
            ),
            truncated=True,
            read_only_verified=True,
        )

    candidates: list[EvidenceCandidate] = []
    refusals: list[HistorianRetrievalRefusal] = []
    for record in records:
        observation_id = _record_id(record)
        if record.get("asset_id") != query.asset_id:
            refusals.append(
                HistorianRetrievalRefusal(
                    observation_id=observation_id,
                    reason_code="HISTORIAN.ASSET_SCOPE_MISMATCH",
                )
            )
            continue
        if (
            query.relationship_id is not None
            and record.get("relationship_id") != query.relationship_id
        ):
            refusals.append(
                HistorianRetrievalRefusal(
                    observation_id=observation_id,
                    reason_code="HISTORIAN.RELATIONSHIP_SCOPE_MISMATCH",
                )
            )
            continue
        if record.get("quality") != "good":
            refusals.append(
                HistorianRetrievalRefusal(
                    observation_id=observation_id,
                    reason_code="HISTORIAN.QUALITY_NOT_GOOD",
                )
            )
            continue
        authority_reason = _authority_reason(record, authority)
        if authority_reason is not None:
            refusals.append(
                HistorianRetrievalRefusal(
                    observation_id=observation_id,
                    reason_code=authority_reason,
                )
            )
            continue
        try:
            candidates.append(
                _candidate_from_record(
                    record,
                    source_id=source_id,
                    authority=authority,
                )
            )
        except ReasoningHistorianError:
            refusals.append(
                HistorianRetrievalRefusal(
                    observation_id=observation_id,
                    reason_code="HISTORIAN.RECORD_IDENTITY_INCOMPLETE",
                )
            )

    return HistorianConditionRetrieval(
        query=query,
        source_id=source_id,
        candidates=tuple(candidates),
        refusals=tuple(refusals),
        truncated=False,
        read_only_verified=True,
    )
