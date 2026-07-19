"""Governed machine profile definitions and event applicability checks."""

from __future__ import annotations

from dataclasses import dataclass

from .events import MachineEvent


class MachineProfileError(ValueError):
    """Raised when a machine profile or event is not applicable."""


@dataclass(frozen=True, slots=True)
class ComponentDefinition:
    """One declared physical or logical component in a machine profile."""

    component_id: str
    name: str
    component_type: str

    def __post_init__(self) -> None:
        for field_name in ("component_id", "name", "component_type"):
            value = getattr(self, field_name)
            if not value.strip():
                raise MachineProfileError(f"{field_name} must not be empty")


@dataclass(frozen=True, slots=True)
class ComponentDependency:
    """One declared physical or functional dependency between components."""

    upstream_component: str
    downstream_component: str
    relationship: str

    def __post_init__(self) -> None:
        for field_name in (
            "upstream_component",
            "downstream_component",
            "relationship",
        ):
            value = getattr(self, field_name)
            if not value.strip():
                raise MachineProfileError(f"{field_name} must not be empty")
        if self.upstream_component == self.downstream_component:
            raise MachineProfileError("a component dependency cannot point to itself")


@dataclass(frozen=True, slots=True)
class EventBinding:
    """Declare which component is allowed to emit one event type."""

    event_type: str
    component_id: str

    def __post_init__(self) -> None:
        if not self.event_type.strip() or not self.component_id.strip():
            raise MachineProfileError("event bindings require event_type and component_id")


@dataclass(frozen=True, slots=True)
class MachineProfile:
    """Approved machine identity, components, dependencies, and event bindings."""

    profile_id: str
    asset_id: str
    components: tuple[ComponentDefinition, ...]
    component_dependencies: tuple[ComponentDependency, ...]
    event_bindings: tuple[EventBinding, ...]
    operating_modes: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.profile_id.strip() or not self.asset_id.strip():
            raise MachineProfileError("profile_id and asset_id must not be empty")
        if not self.components:
            raise MachineProfileError("machine profile requires at least one component")
        if not self.event_bindings:
            raise MachineProfileError("machine profile requires at least one event binding")

        component_ids = [component.component_id for component in self.components]
        if len(component_ids) != len(set(component_ids)):
            raise MachineProfileError("component IDs must be unique")

        binding_pairs = [
            (binding.event_type, binding.component_id) for binding in self.event_bindings
        ]
        if len(binding_pairs) != len(set(binding_pairs)):
            raise MachineProfileError("event bindings must be unique")

        known_components = set(component_ids)
        for dependency in self.component_dependencies:
            for component_id in (
                dependency.upstream_component,
                dependency.downstream_component,
            ):
                if component_id not in known_components:
                    raise MachineProfileError(
                        f"component dependency references unknown component {component_id!r}"
                    )
        for binding in self.event_bindings:
            if binding.component_id not in known_components:
                raise MachineProfileError(
                    f"event binding references unknown component {binding.component_id!r}"
                )

        if any(not mode.strip() for mode in self.operating_modes):
            raise MachineProfileError("operating modes must not be empty")

    @property
    def component_ids(self) -> frozenset[str]:
        return frozenset(component.component_id for component in self.components)

    @property
    def event_types(self) -> frozenset[str]:
        return frozenset(binding.event_type for binding in self.event_bindings)

    def validate_event(self, event: MachineEvent) -> None:
        """Reject events that do not apply to this approved machine profile."""

        if event.asset_id != self.asset_id:
            raise MachineProfileError(
                f"event asset {event.asset_id!r} does not match profile asset {self.asset_id!r}"
            )
        if event.component_id not in self.component_ids:
            raise MachineProfileError(
                f"event references undeclared component {event.component_id!r}"
            )

        allowed_components = {
            binding.component_id
            for binding in self.event_bindings
            if binding.event_type == event.event_type
        }
        if not allowed_components:
            raise MachineProfileError(
                f"event type {event.event_type!r} is not declared by profile {self.profile_id!r}"
            )
        if event.component_id not in allowed_components:
            expected = ", ".join(sorted(allowed_components))
            raise MachineProfileError(
                f"event type {event.event_type!r} is not bound to component "
                f"{event.component_id!r}; expected one of: {expected}"
            )

        mode = event.attributes.get("operating_mode")
        if mode is not None and self.operating_modes and mode not in self.operating_modes:
            allowed = ", ".join(sorted(self.operating_modes))
            raise MachineProfileError(
                f"operating mode {mode!r} is not approved; expected one of: {allowed}"
            )
