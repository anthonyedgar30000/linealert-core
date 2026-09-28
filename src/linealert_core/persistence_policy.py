"""Configured persistence-policy identity and exact relationship binding."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from .condition_localization import PersistenceRule


class PersistencePolicyError(ValueError):
    """Raised when persistence-policy configuration is invalid or unresolved."""


class PersistencePolicyAuthorityClass(StrEnum):
    """How a persistence criterion entered the investigation."""

    DECLARED_CONFIGURATION = "DECLARED_CONFIGURATION"
    AD_HOC_EXPERIMENT = "AD_HOC_EXPERIMENT"


@dataclass(frozen=True, slots=True)
class PersistencePolicy:
    """One named N-of-M criterion bound to one semantic relationship."""

    policy_id: str
    policy_revision: str
    relationship_id: str
    required_outside: int
    window_size: int
    authority_class: PersistencePolicyAuthorityClass = (
        PersistencePolicyAuthorityClass.DECLARED_CONFIGURATION
    )
    metadata: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "policy_revision", "relationship_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise PersistencePolicyError(f"{field_name} must be a non-empty string")
        if not self.relationship_id.startswith("relationship:"):
            raise PersistencePolicyError(
                "relationship_id must use the stable 'relationship:' semantic identity"
            )
        try:
            PersistenceRule(
                required_outside=self.required_outside,
                window_size=self.window_size,
            )
        except ValueError as exc:
            raise PersistencePolicyError(str(exc)) from exc

        detached: dict[str, str] = {}
        for key, value in dict(self.metadata).items():
            if not isinstance(key, str) or not key.strip():
                raise PersistencePolicyError(
                    "persistence policy metadata keys must be non-empty strings"
                )
            if not isinstance(value, str) or not value.strip():
                raise PersistencePolicyError(
                    "persistence policy metadata values must be non-empty strings"
                )
            detached[key] = value
        object.__setattr__(self, "metadata", MappingProxyType(detached))

    @property
    def persistence_rule(self) -> PersistenceRule:
        return PersistenceRule(
            required_outside=self.required_outside,
            window_size=self.window_size,
        )


@dataclass(frozen=True, slots=True)
class PersistencePolicyRegistry:
    """Exact configured persistence policies with one binding per relationship."""

    policies: tuple[PersistencePolicy, ...]

    def __post_init__(self) -> None:
        policy_ids = [policy.policy_id for policy in self.policies]
        if len(policy_ids) != len(set(policy_ids)):
            raise PersistencePolicyError("persistence policy IDs must be unique")
        relationships = [policy.relationship_id for policy in self.policies]
        if len(relationships) != len(set(relationships)):
            raise PersistencePolicyError(
                "only one configured persistence policy may bind each relationship"
            )

    def resolve(self, relationship_id: str) -> PersistencePolicy | None:
        if not isinstance(relationship_id, str) or not relationship_id.strip():
            raise PersistencePolicyError("relationship_id must be a non-empty string")
        return next(
            (policy for policy in self.policies if policy.relationship_id == relationship_id),
            None,
        )

    def require(self, relationship_id: str) -> PersistencePolicy:
        policy = self.resolve(relationship_id)
        if policy is None:
            raise PersistencePolicyError(
                f"no configured persistence policy for {relationship_id!r}"
            )
        return policy


def persistence_policy_registry_from_config(
    raw: Mapping[str, Any],
    *,
    declared_relationship_ids: Iterable[str],
    location: str = "machine configuration",
) -> PersistencePolicyRegistry:
    """Parse optional configured policies and verify every relationship binding."""

    declared = frozenset(declared_relationship_ids)
    policies_raw = raw.get("persistence_policies", [])
    if not isinstance(policies_raw, list):
        raise PersistencePolicyError(f"{location}: persistence_policies must be a list")

    policies: list[PersistencePolicy] = []
    for index, item in enumerate(policies_raw, start=1):
        item_location = f"{location}: persistence policy {index}"
        if not isinstance(item, Mapping):
            raise PersistencePolicyError(f"{item_location} must be an object")
        policy = PersistencePolicy(
            policy_id=_required_text(item, "policy_id", item_location),
            policy_revision=_required_text(
                item,
                "policy_revision",
                item_location,
            ),
            relationship_id=_required_text(
                item,
                "relationship_id",
                item_location,
            ),
            required_outside=_required_int(
                item,
                "required_outside",
                item_location,
            ),
            window_size=_required_int(item, "window_size", item_location),
            metadata=_metadata(item.get("metadata"), item_location),
        )
        if policy.relationship_id not in declared:
            raise PersistencePolicyError(
                f"{item_location}: relationship_id {policy.relationship_id!r} "
                "is not declared by a temporal rule in this configuration"
            )
        policies.append(policy)

    return PersistencePolicyRegistry(tuple(policies))


def persistence_policy_to_dict(
    policy: PersistencePolicy,
) -> dict[str, object]:
    return {
        "policy_id": policy.policy_id,
        "policy_revision": policy.policy_revision,
        "relationship_id": policy.relationship_id,
        "required_outside": policy.required_outside,
        "window_size": policy.window_size,
        "authority_class": policy.authority_class.value,
        "metadata": dict(policy.metadata),
    }


def _required_text(
    raw: Mapping[str, Any],
    field_name: str,
    location: str,
) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise PersistencePolicyError(f"{location}: {field_name} must be a non-empty string")
    return value.strip()


def _required_int(
    raw: Mapping[str, Any],
    field_name: str,
    location: str,
) -> int:
    value = raw.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise PersistencePolicyError(f"{location}: {field_name} must be an integer")
    return value


def _metadata(
    raw: object,
    location: str,
) -> Mapping[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise PersistencePolicyError(f"{location}: metadata must be an object")
    result: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise PersistencePolicyError(f"{location}: metadata keys must be non-empty strings")
        if not isinstance(value, str) or not value.strip():
            raise PersistencePolicyError(f"{location}: metadata values must be non-empty strings")
        result[key.strip()] = value.strip()
    return result


@dataclass(frozen=True, slots=True)
class ConfiguredPersistencePolicyBinding:
    """Resolved configured policy plus exact configuration provenance."""

    policy: PersistencePolicy
    asset_id: str
    profile_id: str
    source_name: str
    source_sha256: str

    def __post_init__(self) -> None:
        for field_name in (
            "asset_id",
            "profile_id",
            "source_name",
            "source_sha256",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise PersistencePolicyError(f"{field_name} must be a non-empty string")
        if len(self.source_sha256) != 64 or any(
            character not in "0123456789abcdefABCDEF" for character in self.source_sha256
        ):
            raise PersistencePolicyError(
                "source_sha256 must be a 64-character hexadecimal SHA-256 digest"
            )

    @property
    def persistence_rule(self) -> PersistenceRule:
        return self.policy.persistence_rule


def bind_configured_persistence_policy(
    registry: PersistencePolicyRegistry,
    relationship_id: str,
    *,
    asset_id: str,
    profile_id: str,
    source_name: str,
    source_sha256: str,
) -> ConfiguredPersistencePolicyBinding:
    """Resolve one exact configured policy and retain its source revision."""

    return ConfiguredPersistencePolicyBinding(
        policy=registry.require(relationship_id),
        asset_id=asset_id,
        profile_id=profile_id,
        source_name=source_name,
        source_sha256=source_sha256,
    )


def configured_persistence_policy_binding_to_dict(
    binding: ConfiguredPersistencePolicyBinding,
) -> dict[str, object]:
    return {
        "policy": persistence_policy_to_dict(binding.policy),
        "asset_id": binding.asset_id,
        "profile_id": binding.profile_id,
        "source_name": binding.source_name,
        "source_sha256": binding.source_sha256,
    }
