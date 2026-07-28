"""Deterministic read-only transport simulator for LineAlert lab evidence."""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from types import MappingProxyType
from typing import Any

from .events import MachineEvent
from .streaming import StreamEnvelope, StreamInputError


@dataclass(frozen=True, slots=True)
class DeterministicStreamSimulator:
    """Wrap supplied machine events in reproducible transport envelopes."""

    events: tuple[MachineEvent, ...]
    session_id: str
    ingestion_delay_seconds: float = 0.05
    clock_quality: str = "synchronized"
    transport_attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise StreamInputError("session_id must be a non-empty string")
        if not math.isfinite(self.ingestion_delay_seconds):
            raise StreamInputError("ingestion_delay_seconds must be finite")
        if self.ingestion_delay_seconds < 0:
            raise StreamInputError("ingestion_delay_seconds must be non-negative")
        if not isinstance(self.clock_quality, str) or not self.clock_quality.strip():
            raise StreamInputError("clock_quality must be a non-empty string")
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(
            self,
            "transport_attributes",
            MappingProxyType(dict(self.transport_attributes)),
        )

    def __iter__(self) -> Iterator[StreamEnvelope]:
        delay = timedelta(seconds=self.ingestion_delay_seconds)
        for sequence_number, event in enumerate(self.events):
            yield StreamEnvelope(
                session_id=self.session_id,
                sequence_number=sequence_number,
                received_at=event.timestamp + delay,
                event=event,
                clock_quality=self.clock_quality,
                transport_attributes=self.transport_attributes,
            )
