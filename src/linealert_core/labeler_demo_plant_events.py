"""Deterministic synthetic plant-event model for the Labeler 2 localhost demo.

The model gives the simulator a shared source for changeover chronology and private setup outcomes.
Public event records deliberately omit the private outcome. The probabilities below are demo priors,
not measured plant or OEM rates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SCENARIO_LENGTH = 160
SIM_SECONDS_PER_SEQUENCE = 10
ROLL_CHANGE_STOP_PHASE = 38
ROLL_CHANGE_PHASE = 40
ROLL_CHANGE_CORRECTION_PHASE = 41
ROLL_CHANGE_RESUME_PHASE = 42
CONCERN_PHASE = 60
FAST_FORWARD_LEAD_STEPS = 2
OUTCOME_SEED = "linealert-labeler2-roll-v1-675"

RollChangeOutcome = Literal["clean", "caught", "escaped"]


def hash32(text: str) -> int:
    """Return a stable FNV-1a 32-bit hash."""

    value = 2166136261
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 16777619) & 0xFFFFFFFF
    return value


def roll_change_outcome(cycle: int) -> RollChangeOutcome:
    """Choose a deterministic outcome using the declared 92/4/4 synthetic demo prior."""

    if cycle < 0:
        raise ValueError("cycle must be non-negative")
    bucket = hash32(f"{OUTCOME_SEED}|{cycle}") % 100
    if bucket < 92:
        return "clean"
    if bucket < 96:
        return "caught"
    return "escaped"


def next_escaped_cycle(start_cycle: int) -> int:
    """Find the next cycle whose private changeover outcome is an escaped deviation."""

    if start_cycle < 0:
        raise ValueError("start_cycle must be non-negative")
    for cycle in range(start_cycle, start_cycle + 10_000):
        if roll_change_outcome(cycle) == "escaped":
            return cycle
    raise RuntimeError("no escaped synthetic roll-change cycle found in search window")


@dataclass(frozen=True, slots=True)
class PlantEvent:
    source_event_sequence: int
    plant_sequence: int
    source: str
    event_class: str
    severity: str
    asset: str
    message: str
    fields: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "linealert.simulator-plant-event.v1",
            "source_event_sequence": self.source_event_sequence,
            "plant_sequence": self.plant_sequence,
            "simulated_elapsed_seconds": self.plant_sequence * SIM_SECONDS_PER_SEQUENCE,
            "source": self.source,
            "event_class": self.event_class,
            "severity": self.severity,
            "asset": self.asset,
            "message": self.message,
            "fields": dict(self.fields),
        }


def _event(
    sequence: int,
    slot: int,
    source: str,
    event_class: str,
    asset: str,
    message: str,
    fields: dict[str, Any],
) -> PlantEvent:
    return PlantEvent(
        source_event_sequence=sequence * 10 + slot,
        plant_sequence=sequence,
        source=source,
        event_class=event_class,
        severity="Information",
        asset=asset,
        message=message,
        fields={
            **fields,
            "source_owned_plant_event": True,
            "clock_quality": "deterministic_simulator_sequence",
        },
    )


def public_events_at_sequence(sequence: int) -> tuple[PlantEvent, ...]:
    """Return only outwardly recordable events for one simulator sequence.

    The ordinary roll-change record is intentionally identical for clean and escaped private
    outcomes. A caught deviation may add a correction record because that intervention itself is
    observable plant history.
    """

    if sequence < 0:
        raise ValueError("sequence must be non-negative")
    cycle = sequence // SCENARIO_LENGTH
    phase = sequence % SCENARIO_LENGTH
    work_order_id = f"SIM-WO-RC-{cycle:04d}"
    common = {
        "work_order_id": work_order_id,
        "activity": "label_roll_change",
        "setup_reference": "Approved marked setup reference",
    }

    if phase == ROLL_CHANGE_STOP_PHASE:
        return (
            _event(
                sequence,
                1,
                "synthetic-hmi/packaging-line-1",
                "PRODUCTION",
                "Labeler 2",
                "Labeler 2 stopped for scheduled label roll change",
                {**common, "run_state": "stopped_changeover"},
            ),
        )
    if phase == ROLL_CHANGE_PHASE:
        return (
            _event(
                sequence,
                1,
                "synthetic-cmms/labeler2",
                "MAINTENANCE",
                "Labeler 2",
                "Label roll change completed",
                {**common, "status": "completed", "boundary": "work_record_is_not_causal_proof"},
            ),
        )
    if phase == ROLL_CHANGE_CORRECTION_PHASE and roll_change_outcome(cycle) == "caught":
        return (
            _event(
                sequence,
                1,
                "synthetic-cmms/labeler2",
                "MAINTENANCE",
                "Labeler 2",
                "First-off guide reference correction completed",
                {
                    **common,
                    "status": "corrected_during_first_off",
                    "boundary": "recorded_correction_does_not_establish_future_machine_state",
                },
            ),
        )
    if phase == ROLL_CHANGE_RESUME_PHASE:
        return (
            _event(
                sequence,
                1,
                "synthetic-hmi/packaging-line-1",
                "PRODUCTION",
                "Labeler 2",
                "Labeler 2 resumed after recorded roll change",
                {**common, "run_state": "production"},
            ),
        )
    return ()


def fast_forward_target(current_sequence: int) -> tuple[int, str]:
    """Return a source-owned target just before the next consequential synthetic event.

    If an escaped changeover is already unfolding, stay in that cycle and move only to the next
    useful precursor boundary. Otherwise select the next escaped cycle and land just before its
    scheduled roll-change stop.
    """

    if current_sequence < 0:
        raise ValueError("current_sequence must be non-negative")
    cycle = current_sequence // SCENARIO_LENGTH
    phase = current_sequence % SCENARIO_LENGTH

    if roll_change_outcome(cycle) == "escaped" and phase < CONCERN_PHASE:
        if phase < ROLL_CHANGE_STOP_PHASE:
            return cycle * SCENARIO_LENGTH + ROLL_CHANGE_STOP_PHASE, "roll_change_precursor"
        target = cycle * SCENARIO_LENGTH + CONCERN_PHASE - FAST_FORWARD_LEAD_STEPS
        return max(current_sequence, target), "concern_precursor"

    target_cycle = next_escaped_cycle(cycle + 1)
    target = target_cycle * SCENARIO_LENGTH + ROLL_CHANGE_STOP_PHASE
    return target, "roll_change_precursor"
