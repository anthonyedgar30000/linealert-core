"""Verify retained historian write-time policy authority against an applied policy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .historian import ConditionHistoryRecord
from .persistence_policy import ConfiguredPersistencePolicyBinding


class HistoricalPolicyEquivalenceState(StrEnum):
    """Evidence state for historical write-time authority equivalence."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class HistoricalPolicyEquivalenceResult:
    """Bounded result of comparing selected history with one applied policy."""

    state: HistoricalPolicyEquivalenceState
    reason_code: str
    detail: str
    selected_record_count: int
    target_record_count: int
    retained_authority_count: int
    missing_authority_count: int
    incomplete_authority_count: int
    conflict_count: int
    first_missing_observation_id: str | None = None
    first_incomplete_observation_id: str | None = None
    first_conflict_observation_id: str | None = None


def verify_historical_policy_equivalence(
    records: tuple[ConditionHistoryRecord, ...],
    *,
    target_relationship_id: str,
    binding: ConfiguredPersistencePolicyBinding,
) -> HistoricalPolicyEquivalenceResult:
    """Compare retained write-time authority with the exact applied configured policy."""

    if not target_relationship_id.strip():
        raise ValueError("target_relationship_id must be a non-empty string")
    if binding.policy.relationship_id != target_relationship_id:
        raise ValueError(
            "configured persistence policy relationship does not match the target relationship"
        )

    target_record_count = 0
    retained_authority_count = 0
    missing: list[str] = []
    incomplete: list[str] = []
    conflicts: list[str] = []

    for record in records:
        if record.relationship_id == target_relationship_id:
            target_record_count += 1

        authority = record.evidence_authority
        if authority is None:
            missing.append(record.observation_id)
            continue
        retained_authority_count += 1

        authority_state = _authority_state(
            authority,
            record=record,
            target_relationship_id=target_relationship_id,
            binding=binding,
        )
        if authority_state == "INCOMPLETE":
            incomplete.append(record.observation_id)
        elif authority_state == "CONFLICT":
            conflicts.append(record.observation_id)

    if conflicts:
        return HistoricalPolicyEquivalenceResult(
            state=HistoricalPolicyEquivalenceState.CONFLICT,
            reason_code="POLICY.HISTORICAL_AUTHORITY_CONFLICT",
            detail=(
                "Retained historian write-time authority conflicts with the currently "
                "applied configuration or persistence-policy binding."
            ),
            selected_record_count=len(records),
            target_record_count=target_record_count,
            retained_authority_count=retained_authority_count,
            missing_authority_count=len(missing),
            incomplete_authority_count=len(incomplete),
            conflict_count=len(conflicts),
            first_missing_observation_id=_first(missing),
            first_incomplete_observation_id=_first(incomplete),
            first_conflict_observation_id=_first(conflicts),
        )

    if not records or target_record_count == 0:
        return HistoricalPolicyEquivalenceResult(
            state=HistoricalPolicyEquivalenceState.UNVERIFIED,
            reason_code="POLICY.HISTORICAL_AUTHORITY_TARGET_UNAVAILABLE",
            detail=(
                "Historical policy equivalence cannot be verified because the selected "
                "history does not contain target-relationship evidence."
            ),
            selected_record_count=len(records),
            target_record_count=target_record_count,
            retained_authority_count=retained_authority_count,
            missing_authority_count=len(missing),
            incomplete_authority_count=len(incomplete),
            conflict_count=0,
            first_missing_observation_id=_first(missing),
            first_incomplete_observation_id=_first(incomplete),
        )

    if missing or incomplete:
        return HistoricalPolicyEquivalenceResult(
            state=HistoricalPolicyEquivalenceState.UNVERIFIED,
            reason_code="POLICY.HISTORICAL_AUTHORITY_INCOMPLETE",
            detail=(
                "At least one selected condition record lacks complete historian write-time "
                "authority, so historical policy equivalence is not established."
            ),
            selected_record_count=len(records),
            target_record_count=target_record_count,
            retained_authority_count=retained_authority_count,
            missing_authority_count=len(missing),
            incomplete_authority_count=len(incomplete),
            conflict_count=0,
            first_missing_observation_id=_first(missing),
            first_incomplete_observation_id=_first(incomplete),
        )

    return HistoricalPolicyEquivalenceResult(
        state=HistoricalPolicyEquivalenceState.VERIFIED,
        reason_code="POLICY.HISTORICAL_AUTHORITY_EQUIVALENT",
        detail=(
            "Every selected condition record retains matching historian write-time "
            "configuration authority, and every target-relationship record retains the "
            "exact persistence-policy binding currently applied."
        ),
        selected_record_count=len(records),
        target_record_count=target_record_count,
        retained_authority_count=retained_authority_count,
        missing_authority_count=0,
        incomplete_authority_count=0,
        conflict_count=0,
    )


def historical_policy_equivalence_to_dict(
    result: HistoricalPolicyEquivalenceResult,
) -> dict[str, object]:
    """Serialize bounded equivalence evidence without reinterpreting it."""

    return {
        "historical_policy_equivalence": result.state.value,
        "reason_code": result.reason_code,
        "detail": result.detail,
        "evidence_basis": "HISTORIAN_WRITE_TIME_POLICY_AUTHORITY",
        "selected_record_count": result.selected_record_count,
        "target_record_count": result.target_record_count,
        "retained_authority_count": result.retained_authority_count,
        "missing_authority_count": result.missing_authority_count,
        "incomplete_authority_count": result.incomplete_authority_count,
        "conflict_count": result.conflict_count,
        "first_missing_observation_id": result.first_missing_observation_id,
        "first_incomplete_observation_id": result.first_incomplete_observation_id,
        "first_conflict_observation_id": result.first_conflict_observation_id,
    }


def _authority_state(
    authority: Mapping[str, Any],
    *,
    record: ConditionHistoryRecord,
    target_relationship_id: str,
    binding: ConfiguredPersistencePolicyBinding,
) -> str:
    if (
        authority.get("schema_version") != "linealert.condition-evidence-authority.v1"
        or authority.get("authority_scope") != "HISTORIAN_WRITE_TIME_POLICY_AUTHORITY"
    ):
        return "INCOMPLETE"

    configuration = authority.get("configuration")
    if not isinstance(configuration, Mapping):
        return "INCOMPLETE"
    config_values = {
        "asset_id": configuration.get("asset_id"),
        "profile_id": configuration.get("profile_id"),
        "source_sha256": configuration.get("source_sha256"),
    }
    if any(value is None for value in config_values.values()):
        return "INCOMPLETE"
    if config_values != {
        "asset_id": binding.asset_id,
        "profile_id": binding.profile_id,
        "source_sha256": binding.source_sha256,
    }:
        return "CONFLICT"

    if record.relationship_id != target_relationship_id:
        return "MATCH"

    retained_binding = authority.get("persistence_policy")
    if retained_binding is None:
        return "INCOMPLETE"
    if not isinstance(retained_binding, Mapping):
        return "INCOMPLETE"

    retained_policy = retained_binding.get("policy")
    if not isinstance(retained_policy, Mapping):
        return "INCOMPLETE"

    required_binding_values = {
        "asset_id": retained_binding.get("asset_id"),
        "profile_id": retained_binding.get("profile_id"),
        "source_sha256": retained_binding.get("source_sha256"),
    }
    if any(value is None for value in required_binding_values.values()):
        return "INCOMPLETE"
    if required_binding_values != {
        "asset_id": binding.asset_id,
        "profile_id": binding.profile_id,
        "source_sha256": binding.source_sha256,
    }:
        return "CONFLICT"

    expected_policy = {
        "policy_id": binding.policy.policy_id,
        "policy_revision": binding.policy.policy_revision,
        "relationship_id": binding.policy.relationship_id,
        "required_outside": binding.policy.required_outside,
        "window_size": binding.policy.window_size,
        "authority_class": binding.policy.authority_class.value,
    }
    retained_policy_values = {key: retained_policy.get(key) for key in expected_policy}
    if any(value is None for value in retained_policy_values.values()):
        return "INCOMPLETE"
    if retained_policy_values != expected_policy:
        return "CONFLICT"

    return "MATCH"


def _first(values: list[str]) -> str | None:
    return values[0] if values else None
