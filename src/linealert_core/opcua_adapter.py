"""Read-only translation of allow-listed OPC UA samples into bounded proxy evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import math
from typing import Any


class ProxySignal(StrEnum):
    RPM = "rpm"
    ARRIVAL_MS = "arrival_ms"
    PRESSURE_PSI = "pressure_psi"


@dataclass(frozen=True, slots=True)
class NodeMapping:
    node_id: str
    signal: ProxySignal
    unit: str
    scale: float = 1.0
    offset: float = 0.0


@dataclass(frozen=True, slots=True)
class QualifiedSample:
    signal: ProxySignal
    value: float | None
    unit: str
    source_timestamp: datetime | None
    status_code: str
    quality: str
    reason_code: str
    node_id: str


def classify_status(status: Any) -> tuple[str, str]:
    """Map an asyncua-like status code without treating unknown status as good."""

    try:
        if bool(status.is_good()):
            return "good", "EVIDENCE.OPCUA_STATUS_GOOD"
        if bool(status.is_bad()):
            return "bad", "EVIDENCE.OPCUA_STATUS_BAD"
    except (AttributeError, TypeError, ValueError):
        pass
    return "unknown", "EVIDENCE.OPCUA_STATUS_UNKNOWN"


def qualify_value(mapping: NodeMapping, data_value: Any) -> QualifiedSample:
    """Translate one DataValue while preserving timestamp and status evidence."""

    status = getattr(data_value, "StatusCode", None)
    quality, reason = classify_status(status)
    timestamp = getattr(data_value, "SourceTimestamp", None)
    if timestamp is not None and timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    raw = getattr(getattr(data_value, "Value", None), "Value", None)
    value: float | None = None
    if quality == "good":
        try:
            value = float(raw) * mapping.scale + mapping.offset
            if not math.isfinite(value):
                raise ValueError("non-finite OPC UA value")
        except (TypeError, ValueError, OverflowError):
            quality, reason = "bad", "EVIDENCE.OPCUA_VALUE_NOT_NUMERIC"
    if timestamp is None:
        quality, reason = "unknown", "EVIDENCE.SOURCE_TIMESTAMP_MISSING"
        value = None
    return QualifiedSample(
        signal=mapping.signal,
        value=value,
        unit=mapping.unit,
        source_timestamp=timestamp,
        status_code=str(status),
        quality=quality,
        reason_code=reason,
        node_id=mapping.node_id,
    )


DEFAULT_MAPPINGS = (
    NodeMapping("nsu=http://microsoft.com/Opc/OpcPlc/;s=FastDouble1", ProxySignal.RPM, "rpm"),
    NodeMapping(
        "nsu=http://microsoft.com/Opc/OpcPlc/;s=FastDouble2",
        ProxySignal.ARRIVAL_MS,
        "ms",
        scale=10.0,
        offset=1300.0,
    ),
    NodeMapping(
        "nsu=http://microsoft.com/Opc/OpcPlc/;s=SlowDouble1",
        ProxySignal.PRESSURE_PSI,
        "psi",
    ),
)
