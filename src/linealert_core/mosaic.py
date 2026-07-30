"""Fusion Mosaic: a typed, governed in-process event fabric."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .events import MachineEvent


class EventIdentityCollision(ValueError):
    """Raised when one event identity is reused for different content."""


EventHandler = Callable[[MachineEvent], Iterable[Any] | None]
StateCheckpoint = Callable[[], Any]
StateRestore = Callable[[Any], None]


@dataclass(frozen=True, slots=True)
class Subscription:
    """A declared dependency between event types and one consumer."""

    name: str
    event_types: frozenset[str]
    handler: EventHandler
    checkpoint: StateCheckpoint | None = None
    restore: StateRestore | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("subscription name must not be empty")
        if not self.event_types:
            raise ValueError("subscription must declare at least one event type")
        if any(not event_type.strip() for event_type in self.event_types):
            raise ValueError("subscription event types must not be empty")
        if (self.checkpoint is None) != (self.restore is None):
            raise ValueError("checkpoint and restore must be provided together")


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


@dataclass(slots=True)
class MosaicTransaction:
    """Prepared delivery that can be committed or rolled back exactly once."""

    receipt: EventReceipt
    _mosaic: FusionMosaic
    _event: MachineEvent | None
    _checkpoints: list[tuple[StateRestore, Any]]
    _finalized: bool = False

    def commit(self) -> EventReceipt:
        """Commit event identity after all downstream derivation succeeds."""

        if self._finalized:
            raise RuntimeError("mosaic transaction is already finalized")
        if self._event is not None:
            self._mosaic._fingerprints_by_event_id[
                self._event.event_id
            ] = self._event.fingerprint
        self._checkpoints.clear()
        self._finalized = True
        return self.receipt

    def rollback(self) -> None:
        """Restore declared consumer state without committing event identity."""

        if self._finalized:
            raise RuntimeError("mosaic transaction is already finalized")
        checkpoints = self._checkpoints
        self._checkpoints = []
        self._finalized = True
        self._mosaic._restore_checkpoints(checkpoints)


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

    @staticmethod
    def _restore_checkpoints(
        checkpoints: list[tuple[StateRestore, Any]],
    ) -> None:
        errors: list[Exception] = []
        for restore, checkpoint in reversed(checkpoints):
            try:
                restore(checkpoint)
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("one or more consumer state restores failed", errors)

    def prepare(self, event: MachineEvent) -> MosaicTransaction:
        """Deliver an event provisionally and retain declared rollback state."""

        existing = self._fingerprints_by_event_id.get(event.event_id)
        if existing is not None:
            if existing != event.fingerprint:
                raise EventIdentityCollision(
                    f"event_id {event.event_id!r} was reused for different content"
                )
            return MosaicTransaction(
                receipt=EventReceipt(
                    event_id=event.event_id,
                    delivered_to=(),
                    outputs=(),
                    duplicate=True,
                ),
                _mosaic=self,
                _event=None,
                _checkpoints=[],
            )

        delivered_to: list[str] = []
        outputs: list[ConsumerOutput] = []
        checkpoints: list[tuple[StateRestore, Any]] = []

        try:
            for subscription in self._subscriptions:
                matches_type = event.event_type in subscription.event_types
                receives_all = "*" in subscription.event_types
                if not matches_type and not receives_all:
                    continue

                restore = subscription.restore
                if subscription.checkpoint is not None and restore is not None:
                    checkpoints.append((restore, subscription.checkpoint()))

                delivered_to.append(subscription.name)
                emitted = subscription.handler(event)
                if emitted is None:
                    continue
                outputs.extend(
                    ConsumerOutput(consumer=subscription.name, value=value)
                    for value in emitted
                )
        except Exception as error:
            try:
                self._restore_checkpoints(checkpoints)
            except Exception as rollback_error:
                raise ExceptionGroup(
                    "consumer delivery failed and state rollback was incomplete",
                    [error, rollback_error],
                ) from error
            raise

        return MosaicTransaction(
            receipt=EventReceipt(
                event_id=event.event_id,
                delivered_to=tuple(delivered_to),
                outputs=tuple(outputs),
            ),
            _mosaic=self,
            _event=event,
            _checkpoints=checkpoints,
        )

    def publish(self, event: MachineEvent) -> EventReceipt:
        """Deliver and immediately commit one event."""

        return self.prepare(event).commit()
