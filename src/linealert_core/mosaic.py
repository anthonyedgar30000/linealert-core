"""Fusion Mosaic: a typed, governed in-process event fabric."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .events import MachineEvent


class EventIdentityCollision(ValueError):
    """Raised when one event identity is reused for different content."""


EventHandler = Callable[[MachineEvent], Iterable[Any] | None]


@dataclass(frozen=True, slots=True)
class Subscription:
    """A declared dependency between event types and one consumer."""

    name: str
    event_types: frozenset[str]
    handler: EventHandler

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("subscription name must not be empty")
        if not self.event_types:
            raise ValueError("subscription must declare at least one event type")
        if any(not event_type.strip() for event_type in self.event_types):
            raise ValueError("subscription event types must not be empty")


@dataclass(frozen=True, slots=True)
class ConsumerOutput:
    """Output emitted by one registered consumer."""

    consumer: str
    value: Any


@dataclass(frozen=True, slots=True)
class EventReceipt:
    """Deterministic record of Mosaic delivery for one event."""

    event_id: str
    delivered_to: tuple[str, ...]
    outputs: tuple[ConsumerOutput, ...]
    duplicate: bool = False


class FusionMosaic:
    """Validate event identity and deliver events only to declared consumers."""

    def __init__(self) -> None:
        self._subscriptions: list[Subscription] = []
        self._subscription_names: set[str] = set()
        self._fingerprints_by_event_id: dict[str, str] = {}

    def register(self, subscription: Subscription) -> None:
        """Register a consumer in explicit deterministic order."""

        if subscription.name in self._subscription_names:
            raise ValueError(f"duplicate subscription name: {subscription.name}")
        self._subscriptions.append(subscription)
        self._subscription_names.add(subscription.name)

    def publish(self, event: MachineEvent) -> EventReceipt:
        """Deliver an event and return its exact delivery and derived outputs."""

        existing = self._fingerprints_by_event_id.get(event.event_id)
        if existing is not None:
            if existing != event.fingerprint:
                raise EventIdentityCollision(
                    f"event_id {event.event_id!r} was reused for different content"
                )
            return EventReceipt(
                event_id=event.event_id,
                delivered_to=(),
                outputs=(),
                duplicate=True,
            )

        self._fingerprints_by_event_id[event.event_id] = event.fingerprint
        delivered_to: list[str] = []
        outputs: list[ConsumerOutput] = []

        for subscription in self._subscriptions:
            matches_type = event.event_type in subscription.event_types
            receives_all = "*" in subscription.event_types
            if not matches_type and not receives_all:
                continue

            delivered_to.append(subscription.name)
            emitted = subscription.handler(event)
            if emitted is None:
                continue
            outputs.extend(
                ConsumerOutput(consumer=subscription.name, value=value)
                for value in emitted
            )

        return EventReceipt(
            event_id=event.event_id,
            delivered_to=tuple(delivered_to),
            outputs=tuple(outputs),
        )
