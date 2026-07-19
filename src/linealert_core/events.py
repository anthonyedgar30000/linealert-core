"""Typed machine events used by the Fusion Mosaic."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class EventQuality(StrEnum):
    """Quality assigned by the source adapter before analysis."""

    GOOD = "good"
    SUSPECT = "suspect"
    BAD = "bad"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MachineEvent:
    """One immutable observation from a machine or supporting evidence source."""

    event_id: str
    source_id: str
    asset_id: str
    component_id: str
    event_type: str
    timestamp: datetime
    correlation_id: str
    value: float | None = None
    unit: str | None = None
    quality: EventQuality = EventQuality.GOOD
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "event_id",
            "source_id",
            "asset_id",
            "component_id",
            "event_type",
            "correlation_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")

        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        if self.value is not None:
            if not math.isfinite(self.value):
                raise ValueError("value must be finite")
            if self.unit is None or not self.unit.strip():
                raise ValueError("unit is required when value is supplied")
        elif self.unit is not None:
            raise ValueError("unit must be omitted when value is absent")

        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))

    def canonical_payload(self) -> dict[str, Any]:
        """Return stable, JSON-compatible event content for identity checks."""

        return {
            "event_id": self.event_id,
            "source_id": self.source_id,
            "asset_id": self.asset_id,
            "component_id": self.component_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "value": self.value,
            "unit": self.unit,
            "quality": self.quality.value,
            "attributes": dict(sorted(self.attributes.items())),
        }

    @property
    def fingerprint(self) -> str:
        """Return a deterministic SHA-256 fingerprint of the full event."""

        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
