"""Seeded packaging-machine emulator with gradual, causally linked degradation."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .events import EventQuality, MachineEvent


@dataclass(frozen=True, slots=True)
class EmulatorConfig:
    """Configuration for one replayable Lane B degradation experiment."""

    seed: int = 20260825
    cycles: int = 120
    cycle_interval_ms: float = 1200.0
    drift_onset_cycle: int = 20
    baseline_actuator_latency_ms: float = 18.0
    maximum_added_latency_ms: float = 58.0
    baseline_arrival_ms: float = 185.0
    commissioned_arrival_min_ms: float = 180.0
    commissioned_arrival_max_ms: float = 210.0
    label_tolerance_mm: float = 3.0
    intervention_cycle: int | None = None
    intervention_effectiveness: float = 0.88
    start_time: datetime = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
    asset_id: str = "LABELER-04"
    recipe: str = "500ml-round"

    def __post_init__(self) -> None:
        if self.cycles < 3:
            raise ValueError("cycles must be at least 3")
        if not 0 <= self.drift_onset_cycle < self.cycles:
            raise ValueError("drift_onset_cycle must occur inside the run")
        if self.intervention_cycle is not None and not 0 < self.intervention_cycle < self.cycles:
            raise ValueError("intervention_cycle must occur inside the run")
        if not 0.0 <= self.intervention_effectiveness <= 1.0:
            raise ValueError("intervention_effectiveness must be between 0 and 1")
        positive = (
            self.cycle_interval_ms,
            self.baseline_actuator_latency_ms,
            self.maximum_added_latency_ms,
            self.baseline_arrival_ms,
            self.label_tolerance_mm,
        )
        if not all(math.isfinite(value) and value > 0 for value in positive):
            raise ValueError("timing and tolerance values must be finite and positive")
        if self.start_time.tzinfo is None or self.start_time.utcoffset() is None:
            raise ValueError("start_time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CycleGroundTruth:
    """Private simulator state; never exposed as LineAlert evidence."""

    cycle: int
    degradation_fraction: float
    pneumatic_leak_fraction: float
    actuator_stiction_fraction: float
    actuator_latency_ms: float
    incomplete_release: bool
    intervention_active: bool


@dataclass(frozen=True, slots=True)
class CycleEvidence:
    """Observations that a real PLC, camera, or inspection source could expose."""

    cycle: int
    command_interval_ms: float
    camera_actuator_latency_ms: float
    camera_track_confidence: float
    s1_arrival_ms: float
    feed_wrapper_ratio: float
    label_offset_mm: float
    product_accepted: bool
    actuator_motion_complete: bool

    def opcua_nodes(self) -> dict[str, float | bool]:
        """Return an OPC-UA-shaped node snapshot without coupling to a server library."""

        return {
            "Line04.LaneB.ReleaseCommandIntervalMs": self.command_interval_ms,
            "Line04.LaneB.CameraActuatorLatencyMs": self.camera_actuator_latency_ms,
            "Line04.LaneB.CameraTrackConfidence": self.camera_track_confidence,
            "Line04.Merge.S1ArrivalMs": self.s1_arrival_ms,
            "Line04.Wrapper.FeedRatio": self.feed_wrapper_ratio,
            "Line04.Quality.LabelOffsetMm": self.label_offset_mm,
            "Line04.Quality.ProductAccepted": self.product_accepted,
            "Line04.LaneB.ActuatorMotionComplete": self.actuator_motion_complete,
        }


@dataclass(frozen=True, slots=True)
class CycleRecord:
    ground_truth: CycleGroundTruth
    evidence: CycleEvidence
    events: tuple[MachineEvent, ...]


@dataclass(frozen=True, slots=True)
class EmulatorRun:
    config: EmulatorConfig
    records: tuple[CycleRecord, ...]

    @property
    def evidence_fingerprint(self) -> str:
        payload = [event.canonical_payload() for record in self.records for event in record.events]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def visible_records(self) -> list[dict[str, Any]]:
        """Return evidence only; hidden causal variables are deliberately excluded."""

        return [asdict(record.evidence) for record in self.records]

    def machine_event_records(self) -> list[dict[str, Any]]:
        """Return replay-ready canonical MachineEvent dictionaries."""

        return [event.canonical_payload() for record in self.records for event in record.events]

    def ground_truth_records(self) -> list[dict[str, Any]]:
        return [asdict(record.ground_truth) for record in self.records]


class LaneBDegradationEmulator:
    """Generate gradual pneumatic/stiction drift and correlated downstream evidence."""

    def __init__(self, config: EmulatorConfig | None = None) -> None:
        self.config = config if config is not None else EmulatorConfig()

    def run(self) -> EmulatorRun:
        rng = random.Random(self.config.seed)
        records = tuple(self._cycle(cycle, rng) for cycle in range(self.config.cycles))
        return EmulatorRun(config=self.config, records=records)

    def _cycle(self, cycle: int, rng: random.Random) -> CycleRecord:
        config = self.config
        progress_denominator = max(1, config.cycles - config.drift_onset_cycle - 1)
        raw_progress = max(0.0, (cycle - config.drift_onset_cycle) / progress_denominator)
        degradation = min(1.0, raw_progress**1.35)
        intervention_active = (
            config.intervention_cycle is not None and cycle >= config.intervention_cycle
        )
        if intervention_active:
            degradation *= 1.0 - config.intervention_effectiveness

        thermal_fraction = 1.0 - math.exp(-cycle / 24.0)
        pneumatic_leak = min(1.0, degradation * 0.72 + thermal_fraction * 0.05)
        stiction = min(1.0, degradation * 0.88)
        latency_center = (
            config.baseline_actuator_latency_ms
            + config.maximum_added_latency_ms * (0.58 * pneumatic_leak + 0.42 * stiction)
        )
        latency_jitter = 1.8 + 11.0 * stiction
        actuator_latency = max(1.0, rng.gauss(latency_center, latency_jitter))
        incomplete_probability = 0.22 * stiction**2.4
        incomplete_release = rng.random() < incomplete_probability
        if incomplete_release:
            actuator_latency += rng.uniform(18.0, 42.0)

        command_interval = config.cycle_interval_ms + rng.gauss(0.0, 0.8)
        camera_noise = 1.0 + 2.2 * degradation
        camera_latency = max(0.0, actuator_latency + rng.gauss(0.0, camera_noise))
        track_confidence = max(
            0.45,
            min(0.995, 0.985 - 0.12 * degradation - (0.22 if incomplete_release else 0.0)),
        )
        arrival_ms = (
            config.baseline_arrival_ms
            + actuator_latency
            - config.baseline_actuator_latency_ms
            + rng.gauss(0.0, 2.0 + 3.5 * degradation)
        )
        feed_ratio = 1.0 + rng.gauss(0.0, 0.0022)
        late_by_ms = max(0.0, arrival_ms - config.commissioned_arrival_max_ms)
        label_offset = rng.gauss(0.0, 0.55) + 0.115 * late_by_ms
        if incomplete_release:
            label_offset += rng.uniform(1.2, 2.8)
        accepted = abs(label_offset) <= config.label_tolerance_mm

        truth = CycleGroundTruth(
            cycle=cycle,
            degradation_fraction=degradation,
            pneumatic_leak_fraction=pneumatic_leak,
            actuator_stiction_fraction=stiction,
            actuator_latency_ms=actuator_latency,
            incomplete_release=incomplete_release,
            intervention_active=intervention_active,
        )
        evidence = CycleEvidence(
            cycle=cycle,
            command_interval_ms=command_interval,
            camera_actuator_latency_ms=camera_latency,
            camera_track_confidence=track_confidence,
            s1_arrival_ms=arrival_ms,
            feed_wrapper_ratio=feed_ratio,
            label_offset_mm=label_offset,
            product_accepted=accepted,
            actuator_motion_complete=not incomplete_release,
        )
        return CycleRecord(
            ground_truth=truth,
            evidence=evidence,
            events=self._events(cycle, evidence),
        )

    def _events(self, cycle: int, evidence: CycleEvidence) -> tuple[MachineEvent, ...]:
        config = self.config
        cycle_start = config.start_time + timedelta(
            milliseconds=config.cycle_interval_ms * cycle
        )
        correlation_id = f"lane-b-cycle-{cycle:05d}"
        common = {"recipe": config.recipe, "emulator": "lane-b-gradual-drift-v1"}

        def event(
            suffix: str,
            source: str,
            component: str,
            event_type: str,
            offset_ms: float,
            value: float | None = None,
            unit: str | None = None,
            quality: EventQuality = EventQuality.GOOD,
            attributes: dict[str, Any] | None = None,
        ) -> MachineEvent:
            return MachineEvent(
                event_id=f"{correlation_id}-{suffix}",
                source_id=source,
                asset_id=config.asset_id,
                component_id=component,
                event_type=event_type,
                timestamp=cycle_start + timedelta(milliseconds=offset_ms),
                correlation_id=correlation_id,
                value=value,
                unit=unit,
                quality=quality,
                attributes={**common, **(attributes or {})},
            )

        return (
            event("command", "plc-line04", "lane-b-release", "ActuatorCommand", 0.0),
            event(
                "motion",
                "camera-line04",
                "lane-b-release",
                "ActuatorMotionObserved",
                evidence.camera_actuator_latency_ms,
                evidence.camera_actuator_latency_ms,
                "ms",
                attributes={
                    "track_confidence": round(evidence.camera_track_confidence, 6),
                    "motion_complete": evidence.actuator_motion_complete,
                },
            ),
            event(
                "arrival",
                "photoeye-s1",
                "merge-s1",
                "BottleArrival",
                evidence.s1_arrival_ms,
                evidence.s1_arrival_ms,
                "ms",
            ),
            event(
                "feed-ratio",
                "plc-line04",
                "wrapper",
                "FeedWrapperRatio",
                evidence.s1_arrival_ms + 12.0,
                evidence.feed_wrapper_ratio,
                "ratio",
            ),
            event(
                "inspection",
                "camera-quality04",
                "label-inspection",
                "LabelOffset",
                evidence.s1_arrival_ms + 85.0,
                evidence.label_offset_mm,
                "mm",
                attributes={"product_accepted": evidence.product_accepted},
            ),
        )
