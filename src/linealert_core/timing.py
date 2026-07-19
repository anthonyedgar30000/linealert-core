"""Deterministic temporal relationship monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .events import MachineEvent


class TimingStatus(StrEnum):
    """Observed relationship to an approved timing envelope."""

    EARLY = "early"
    WITHIN = "within"
    LATE = "late"


@dataclass(frozen=True, slots=True)
class TemporalRule:
    """Expected delay between two correlated machine events."""

    rule_id: str
    start_event: str
    end_event: str
    min_delay_seconds: float
    max_delay_seconds: float
    topology_from: str
    topology_to: str

    def __post_init__(self) -> None:
        for field_name in (
            "rule_id",
            "start_event",
            "end_event",
            "topology_from",
            "topology_to",
        ):
            value = getattr(self, field_name)
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.min_delay_seconds < 0:
            raise ValueError("min_delay_seconds must be non-negative")
        if self.max_delay_seconds < self.min_delay_seconds:
            raise ValueError("max_delay_seconds must be >= min_delay_seconds")


@dataclass(frozen=True, slots=True)
class TimingFinding:
    """Measured delay and bounded comparison against one temporal rule."""

    rule_id: str
    asset_id: str
    correlation_id: str
    start_timestamp: datetime
    end_timestamp: datetime
    delay_seconds: float
    min_delay_seconds: float
    max_delay_seconds: float
    status: TimingStatus
    topology_from: str
    topology_to: str

    @property
    def observation_key(self) -> str:
        return f"lag:{self.topology_from}->{self.topology_to}"


class TimingMonitor:
    """Correlate explicit event pairs and emit timing findings."""

    def __init__(self, rules: list[TemporalRule]) -> None:
        if not rules:
            raise ValueError("at least one temporal rule is required")
        rule_ids = [rule.rule_id for rule in rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("temporal rule IDs must be unique")

        self.rules = tuple(rules)
        self._starts: dict[tuple[str, str, str], MachineEvent] = {}

    @property
    def event_types(self) -> frozenset[str]:
        return frozenset(
            event_type
            for rule in self.rules
            for event_type in (rule.start_event, rule.end_event)
        )

    def handle(self, event: MachineEvent) -> tuple[TimingFinding, ...]:
        findings: list[TimingFinding] = []

        for rule in self.rules:
            key = (rule.rule_id, event.asset_id, event.correlation_id)

            if event.event_type == rule.start_event:
                self._starts[key] = event

            if event.event_type != rule.end_event:
                continue

            start = self._starts.pop(key, None)
            if start is None:
                continue

            delay_seconds = (event.timestamp - start.timestamp).total_seconds()
            if delay_seconds < 0:
                raise ValueError(
                    f"end event {event.event_id!r} precedes start event {start.event_id!r}"
                )

            if delay_seconds < rule.min_delay_seconds:
                status = TimingStatus.EARLY
            elif delay_seconds > rule.max_delay_seconds:
                status = TimingStatus.LATE
            else:
                status = TimingStatus.WITHIN

            findings.append(
                TimingFinding(
                    rule_id=rule.rule_id,
                    asset_id=event.asset_id,
                    correlation_id=event.correlation_id,
                    start_timestamp=start.timestamp,
                    end_timestamp=event.timestamp,
                    delay_seconds=delay_seconds,
                    min_delay_seconds=rule.min_delay_seconds,
                    max_delay_seconds=rule.max_delay_seconds,
                    status=status,
                    topology_from=rule.topology_from,
                    topology_to=rule.topology_to,
                )
            )

        return tuple(findings)
