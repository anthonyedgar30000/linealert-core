from collections import Counter

import pytest

from linealert_core.labeler_demo_opcua_server import ControlRejected, LabelerDemoState
from linealert_core.labeler_demo_plant_events import (
    CONCERN_PHASE,
    ROLL_CHANGE_CORRECTION_PHASE,
    ROLL_CHANGE_PHASE,
    ROLL_CHANGE_STOP_PHASE,
    SCENARIO_LENGTH,
    SIM_SECONDS_PER_SEQUENCE,
    fast_forward_target,
    public_events_at_sequence,
    roll_change_outcome,
)


def test_declared_demo_prior_is_deterministic_92_4_4_over_seeded_reference_window():
    outcomes = [roll_change_outcome(cycle) for cycle in range(100)]

    assert Counter(outcomes) == {"clean": 92, "caught": 4, "escaped": 4}
    assert roll_change_outcome(2) == "escaped"
    assert roll_change_outcome(38) == "caught"


def test_public_roll_change_record_does_not_reveal_private_outcome():
    clean_sequence = ROLL_CHANGE_PHASE
    escaped_sequence = 2 * SCENARIO_LENGTH + ROLL_CHANGE_PHASE

    clean = public_events_at_sequence(clean_sequence)[0].as_dict()
    escaped = public_events_at_sequence(escaped_sequence)[0].as_dict()

    assert clean["message"] == escaped["message"] == "Label roll change completed"
    assert clean["source"] == escaped["source"] == "synthetic-cmms/labeler2"
    for event in (clean, escaped):
        serialized = str(event).lower()
        assert "private_roll_outcome" not in serialized
        assert "guide_offset" not in serialized
        assert "sloppy" not in serialized
        assert "escaped" not in serialized
        assert event["fields"]["boundary"] == "work_record_is_not_causal_proof"


def test_caught_changeover_emits_recorded_first_off_correction_but_clean_does_not():
    caught_sequence = 38 * SCENARIO_LENGTH + ROLL_CHANGE_CORRECTION_PHASE
    clean_sequence = ROLL_CHANGE_CORRECTION_PHASE

    caught = public_events_at_sequence(caught_sequence)
    clean = public_events_at_sequence(clean_sequence)

    assert len(caught) == 1
    assert caught[0].message == "First-off guide reference correction completed"
    assert clean == ()


def test_stateful_clean_roll_change_stays_healthy_while_known_escaped_cycle_degrades():
    clean_state = LabelerDemoState()
    escaped_state = LabelerDemoState()

    clean = clean_state.observation(CONCERN_PHASE + 10)
    escaped = escaped_state.observation(2 * SCENARIO_LENGTH + CONCERN_PHASE + 10)

    assert clean.presentation_interval_stddev_ms < 11
    assert clean.camera_aligned_containers == clean.camera_observed_containers == 5
    assert escaped.presentation_interval_stddev_ms >= 20
    assert escaped.camera_aligned_containers == 3
    assert escaped.reject_candidates == 2


def test_caught_roll_change_is_back_at_reference_before_concern_window():
    state = LabelerDemoState()
    sequence = 38 * SCENARIO_LENGTH + CONCERN_PHASE

    observation = state.observation(sequence)

    assert observation.presentation_interval_stddev_ms < 11
    assert observation.camera_aligned_containers == observation.camera_observed_containers == 5


def test_fast_forward_selects_next_escaped_changeover_and_lands_before_roll_completion():
    target, kind = fast_forward_target(0)

    assert target == 2 * SCENARIO_LENGTH + ROLL_CHANGE_STOP_PHASE
    assert kind == "roll_change_precursor"
    assert (2 * SCENARIO_LENGTH + ROLL_CHANGE_PHASE - target) * SIM_SECONDS_PER_SEQUENCE == 20


def test_source_fast_forward_preserves_crossed_public_events_without_private_truth():
    state = LabelerDemoState()
    state.observation(0)

    receipt = state.fast_forward_to_next_concern()
    events = state.plant_events_after(0)

    assert receipt["target_sequence"] == 2 * SCENARIO_LENGTH + ROLL_CHANGE_STOP_PHASE
    assert receipt["target_kind"] == "roll_change_precursor"
    assert receipt["advanced_simulated_seconds"] > 0
    assert "outcome" not in receipt
    assert events
    assert events[-1]["message"] == "Labeler 2 stopped for scheduled label roll change"
    serialized = str(events).lower()
    assert "private_roll_outcome" not in serialized
    assert "guide_offset" not in serialized
    assert "escaped" not in serialized


def test_fast_forwarded_escaped_changeover_unfolds_through_planned_stop_then_opc_evidence():
    state = LabelerDemoState()
    state.observation(0)
    receipt = state.fast_forward_to_next_concern()

    precursor = state.observation(receipt["target_sequence"])
    assert precursor.run_state_code == 0
    assert precursor.roll_change_recent is False

    current = precursor
    while current.sequence < 2 * SCENARIO_LENGTH + CONCERN_PHASE:
        current = state.next_observation()

    assert current.run_state_code == 1
    assert current.roll_change_recent is True
    assert current.presentation_interval_stddev_ms >= 20
    assert current.camera_aligned_containers == 3

    event_messages = [event["message"] for event in state.plant_events_after(0)]
    assert "Label roll change completed" in event_messages
    assert "Labeler 2 resumed after recorded roll change" in event_messages


def test_fast_forward_rejects_explicit_stopped_diagnostic_state():
    state = LabelerDemoState()
    state.observation(0)
    state.stop_for_diagnostic()

    with pytest.raises(ControlRejected, match="ordinary production progression"):
        state.fast_forward_to_next_concern()
