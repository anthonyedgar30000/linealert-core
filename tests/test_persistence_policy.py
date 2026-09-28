from __future__ import annotations

import json
from pathlib import Path

import pytest

from linealert_core.historian_service import load_localization_topology_authority
from linealert_core.persistence_policy import (
    PersistencePolicy,
    PersistencePolicyAuthorityClass,
    PersistencePolicyError,
    PersistencePolicyRegistry,
    bind_configured_persistence_policy,
    configured_persistence_policy_binding_to_dict,
    persistence_policy_registry_from_config,
)

ROOT = Path(__file__).resolve().parents[1]


def test_demo_config_binds_named_persistence_policy_to_declared_relationship() -> None:
    authority = load_localization_topology_authority(ROOT / "examples" / "labeler_demo_config.json")

    binding = authority.bind_persistence_policy("relationship:label-presentation-delay")

    assert binding.policy.policy_id == "label-presentation-persistence-v1"
    assert binding.policy.policy_revision == "1"
    assert binding.policy.required_outside == 3
    assert binding.policy.window_size == 4
    assert binding.policy.authority_class is (
        PersistencePolicyAuthorityClass.DECLARED_CONFIGURATION
    )
    assert binding.asset_id == "LABELER-DEMO-01"
    assert binding.profile_id == "generic-pressure-sensitive-labeler-demo-v1"
    assert binding.source_sha256 == authority.source_sha256
    assert binding.persistence_rule.required_outside == 3
    assert binding.persistence_rule.window_size == 4


def test_registry_refuses_duplicate_relationship_binding() -> None:
    first = PersistencePolicy(
        policy_id="policy-a",
        policy_revision="1",
        relationship_id="relationship:delay-a",
        required_outside=2,
        window_size=3,
    )
    second = PersistencePolicy(
        policy_id="policy-b",
        policy_revision="1",
        relationship_id="relationship:delay-a",
        required_outside=3,
        window_size=4,
    )

    with pytest.raises(PersistencePolicyError, match="only one"):
        PersistencePolicyRegistry((first, second))


def test_config_parser_refuses_unknown_relationship() -> None:
    raw = {
        "persistence_policies": [
            {
                "policy_id": "unknown-policy",
                "policy_revision": "1",
                "relationship_id": "relationship:not-declared",
                "required_outside": 2,
                "window_size": 3,
            }
        ]
    }

    with pytest.raises(PersistencePolicyError, match="not declared"):
        persistence_policy_registry_from_config(
            raw,
            declared_relationship_ids={"relationship:known"},
        )


def test_missing_policy_does_not_fall_back_to_default() -> None:
    registry = PersistencePolicyRegistry(())

    assert registry.resolve("relationship:missing") is None
    with pytest.raises(PersistencePolicyError, match="no configured"):
        registry.require("relationship:missing")


def test_configured_binding_retains_exact_policy_and_source_provenance() -> None:
    policy = PersistencePolicy(
        policy_id="configured-policy",
        policy_revision="7",
        relationship_id="relationship:delay-a",
        required_outside=3,
        window_size=5,
        metadata={"classification": "controlled_synthetic_demo"},
    )
    binding = bind_configured_persistence_policy(
        PersistencePolicyRegistry((policy,)),
        "relationship:delay-a",
        asset_id="ASSET-01",
        profile_id="profile-v2",
        source_name="machine-config.json",
        source_sha256="a" * 64,
    )

    payload = configured_persistence_policy_binding_to_dict(binding)

    assert payload["asset_id"] == "ASSET-01"
    assert payload["profile_id"] == "profile-v2"
    assert payload["source_sha256"] == "a" * 64
    policy_payload = payload["policy"]
    assert isinstance(policy_payload, dict)
    assert policy_payload["policy_id"] == "configured-policy"
    assert policy_payload["policy_revision"] == "7"
    assert policy_payload["authority_class"] == "DECLARED_CONFIGURATION"


def test_policy_revision_change_produces_distinct_config_provenance(tmp_path: Path) -> None:
    source = ROOT / "examples" / "labeler_demo_config.json"
    raw = json.loads(source.read_text(encoding="utf-8"))

    first_path = tmp_path / "config-v1.json"
    first_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    first = load_localization_topology_authority(first_path)

    raw["persistence_policies"][0]["policy_revision"] = "2"
    second_path = tmp_path / "config-v2.json"
    second_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    second = load_localization_topology_authority(second_path)

    first_binding = first.bind_persistence_policy("relationship:label-presentation-delay")
    second_binding = second.bind_persistence_policy("relationship:label-presentation-delay")

    assert first_binding.policy.policy_revision == "1"
    assert second_binding.policy.policy_revision == "2"
    assert first_binding.source_sha256 != second_binding.source_sha256


def test_policy_rejects_impossible_n_of_m() -> None:
    with pytest.raises(PersistencePolicyError):
        PersistencePolicy(
            policy_id="bad",
            policy_revision="1",
            relationship_id="relationship:delay",
            required_outside=5,
            window_size=4,
        )


def test_persistence_policy_types_are_exported_from_public_api() -> None:
    import linealert_core

    assert linealert_core.PersistencePolicy is PersistencePolicy
    assert linealert_core.PersistencePolicyRegistry is PersistencePolicyRegistry
    assert linealert_core.ConfiguredPersistencePolicyBinding is not None
