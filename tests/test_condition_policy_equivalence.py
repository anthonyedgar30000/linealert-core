from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path

from linealert_core.condition_policy_equivalence import (
    HistoricalPolicyEquivalenceState,
    historical_policy_equivalence_to_dict,
    verify_historical_policy_equivalence,
)
from linealert_core.historian import ConditionHistoryRecord
from linealert_core.historian_service import (
    condition_evidence_authority_payload,
    load_localization_topology_authority,
)

ROOT = Path(__file__).resolve().parents[1]


def _record(
    observation_id: str,
    *,
    relationship_id: str,
    evidence_authority: dict[str, object] | None,
) -> ConditionHistoryRecord:
    return ConditionHistoryRecord(
        observed_at=datetime(2026, 9, 14, 11, 42, tzinfo=UTC),
        observation_id=observation_id,
        episode_id="incident-42",
        asset_id="LABELER-DEMO-01",
        relationship_id=relationship_id,
        signal="condition_signal",
        value=500.0,
        unit="ms",
        min_value=50.0,
        max_value=350.0,
        temporal_rule_status="late",
        quality="good",
        reason_code="EVIDENCE.RELATIONSHIP_DELAY_MEASURED",
        correlation_id="cycle-42",
        topology_from="A",
        topology_to="B",
        source_mode="replay",
        cycle_id="cycle-42",
        operating_context={"configuration_version": "demo-config-v1"},
        evidence_authority=evidence_authority,
        clock_evidence={"basis": "same_source_relative_interval"},
    )


def _authority_and_binding():
    authority = load_localization_topology_authority(ROOT / "examples" / "labeler_demo_config.json")
    binding = authority.bind_persistence_policy("relationship:label-presentation-delay")
    return authority, binding


def test_exact_selected_config_and_target_policy_authority_is_verified() -> None:
    authority, binding = _authority_and_binding()
    target_authority = condition_evidence_authority_payload(
        authority,
        asset_id="LABELER-DEMO-01",
        relationship_id="relationship:label-presentation-delay",
    )
    dependency_authority = condition_evidence_authority_payload(
        authority,
        asset_id="LABELER-DEMO-01",
        relationship_id="relationship:initial-contact-delay",
    )
    assert target_authority is not None
    assert dependency_authority is not None
    assert dependency_authority["persistence_policy"] is None

    result = verify_historical_policy_equivalence(
        (
            _record(
                "target-1",
                relationship_id="relationship:label-presentation-delay",
                evidence_authority=target_authority,
            ),
            _record(
                "dependency-1",
                relationship_id="relationship:initial-contact-delay",
                evidence_authority=dependency_authority,
            ),
        ),
        target_relationship_id="relationship:label-presentation-delay",
        binding=binding,
    )

    assert result.state is HistoricalPolicyEquivalenceState.VERIFIED
    assert result.selected_record_count == 2
    assert result.target_record_count == 1
    assert result.retained_authority_count == 2
    assert result.missing_authority_count == 0
    assert result.incomplete_authority_count == 0
    assert result.conflict_count == 0
    payload = historical_policy_equivalence_to_dict(result)
    assert payload["historical_policy_equivalence"] == "VERIFIED"
    assert payload["evidence_basis"] == "HISTORIAN_WRITE_TIME_POLICY_AUTHORITY"


def test_legacy_missing_authority_is_unverified() -> None:
    _, binding = _authority_and_binding()

    result = verify_historical_policy_equivalence(
        (
            _record(
                "legacy-target",
                relationship_id="relationship:label-presentation-delay",
                evidence_authority=None,
            ),
        ),
        target_relationship_id="relationship:label-presentation-delay",
        binding=binding,
    )

    assert result.state is HistoricalPolicyEquivalenceState.UNVERIFIED
    assert result.reason_code == "POLICY.HISTORICAL_AUTHORITY_INCOMPLETE"
    assert result.missing_authority_count == 1
    assert result.first_missing_observation_id == "legacy-target"


def test_target_policy_absence_is_unverified_not_conflict() -> None:
    authority, binding = _authority_and_binding()
    config_only = condition_evidence_authority_payload(
        authority,
        asset_id="LABELER-DEMO-01",
        relationship_id="relationship:initial-contact-delay",
    )
    assert config_only is not None
    target_without_policy = copy.deepcopy(config_only)

    result = verify_historical_policy_equivalence(
        (
            _record(
                "target-no-policy",
                relationship_id="relationship:label-presentation-delay",
                evidence_authority=target_without_policy,
            ),
        ),
        target_relationship_id="relationship:label-presentation-delay",
        binding=binding,
    )

    assert result.state is HistoricalPolicyEquivalenceState.UNVERIFIED
    assert result.incomplete_authority_count == 1
    assert result.conflict_count == 0


def test_target_policy_revision_mismatch_is_conflict() -> None:
    authority, binding = _authority_and_binding()
    retained = condition_evidence_authority_payload(
        authority,
        asset_id="LABELER-DEMO-01",
        relationship_id="relationship:label-presentation-delay",
    )
    assert retained is not None
    conflicting = copy.deepcopy(retained)
    retained_binding = conflicting["persistence_policy"]
    assert isinstance(retained_binding, dict)
    retained_policy = retained_binding["policy"]
    assert isinstance(retained_policy, dict)
    retained_policy["policy_revision"] = "different-revision"

    result = verify_historical_policy_equivalence(
        (
            _record(
                "target-conflict",
                relationship_id="relationship:label-presentation-delay",
                evidence_authority=conflicting,
            ),
        ),
        target_relationship_id="relationship:label-presentation-delay",
        binding=binding,
    )

    assert result.state is HistoricalPolicyEquivalenceState.CONFLICT
    assert result.reason_code == "POLICY.HISTORICAL_AUTHORITY_CONFLICT"
    assert result.conflict_count == 1
    assert result.first_conflict_observation_id == "target-conflict"


def test_dependency_config_sha_mismatch_is_conflict() -> None:
    authority, binding = _authority_and_binding()
    target_authority = condition_evidence_authority_payload(
        authority,
        asset_id="LABELER-DEMO-01",
        relationship_id="relationship:label-presentation-delay",
    )
    dependency_authority = condition_evidence_authority_payload(
        authority,
        asset_id="LABELER-DEMO-01",
        relationship_id="relationship:initial-contact-delay",
    )
    assert target_authority is not None
    assert dependency_authority is not None
    conflicting_dependency = copy.deepcopy(dependency_authority)
    configuration = conflicting_dependency["configuration"]
    assert isinstance(configuration, dict)
    configuration["source_sha256"] = "b" * 64

    result = verify_historical_policy_equivalence(
        (
            _record(
                "target",
                relationship_id="relationship:label-presentation-delay",
                evidence_authority=target_authority,
            ),
            _record(
                "dependency-conflict",
                relationship_id="relationship:initial-contact-delay",
                evidence_authority=conflicting_dependency,
            ),
        ),
        target_relationship_id="relationship:label-presentation-delay",
        binding=binding,
    )

    assert result.state is HistoricalPolicyEquivalenceState.CONFLICT
    assert result.conflict_count == 1
    assert result.first_conflict_observation_id == "dependency-conflict"


def test_unsupported_authority_schema_is_unverified() -> None:
    authority, binding = _authority_and_binding()
    retained = condition_evidence_authority_payload(
        authority,
        asset_id="LABELER-DEMO-01",
        relationship_id="relationship:label-presentation-delay",
    )
    assert retained is not None
    incomplete = copy.deepcopy(retained)
    incomplete["schema_version"] = "unknown"

    result = verify_historical_policy_equivalence(
        (
            _record(
                "target-unknown-schema",
                relationship_id="relationship:label-presentation-delay",
                evidence_authority=incomplete,
            ),
        ),
        target_relationship_id="relationship:label-presentation-delay",
        binding=binding,
    )

    assert result.state is HistoricalPolicyEquivalenceState.UNVERIFIED
    assert result.incomplete_authority_count == 1
