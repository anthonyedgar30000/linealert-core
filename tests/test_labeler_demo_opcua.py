import math

import pytest

from linealert_core.labeler_demo_opcua_server import (
    ASSET_ID,
    DISTURBED_GUIDE_OFFSET_MM,
    GUIDE_REFERENCE_TOLERANCE_MM,
    NODE_IDS,
    PROFILE_ID,
    ControlRejected,
    LabelerDemoState,
    observable_for_sequence,
)

ESCAPED_CONCERN_SEQUENCE = 2 * 160 + 70


def test_labeler_emulator_contract_is_deterministic_and_observable_only():
    first = observable_for_sequence(67)
    second = observable_for_sequence(67)

    assert first == second
    assert ASSET_ID == "Labeler 2"
    assert PROFILE_ID == "linealert-labeler2-observable-v1"
    assert set(first.opcua_nodes()) == set(NODE_IDS.values())
    exported = " ".join(first.opcua_nodes()).lower()
    assert all(
        forbidden not in exported
        for forbidden in ("root_cause", "fault_truth", "hidden_mechanism", "guideoffset")
    )


def test_labeler_emulator_episode_moves_through_observable_states():
    baseline = observable_for_sequence(10)
    approach = observable_for_sequence(55)
    concern = observable_for_sequence(70)
    stopped = observable_for_sequence(104)
    diagnostic = observable_for_sequence(114)
    late_production = observable_for_sequence(135)

    assert baseline.run_state_code == 1
    assert baseline.presentation_interval_stddev_ms < 10
    assert baseline.camera_aligned_containers == baseline.camera_observed_containers

    assert approach.roll_change_recent is True
    assert 9 <= approach.presentation_interval_stddev_ms <= 14

    assert concern.presentation_interval_stddev_ms >= 20
    assert concern.camera_aligned_containers == 3
    assert concern.reject_candidates == 2

    assert stopped.run_state_code == 0
    assert stopped.line_speed_cpm == 0
    assert stopped.camera_observed_containers == 0

    assert diagnostic.run_state_code == 2
    assert diagnostic.camera_observed_containers == 5
    assert diagnostic.camera_aligned_containers == 3
    assert diagnostic.presentation_interval_stddev_ms >= 19

    assert late_production.run_state_code == 1
    assert late_production.roll_change_recent is False
    assert late_production.camera_aligned_containers == 3
    assert late_production.reject_candidates == 2


def test_stateful_guide_verification_must_precede_restore_and_changes_future_evidence():
    state = LabelerDemoState()
    concern = state.observation(ESCAPED_CONCERN_SEQUENCE)
    assert concern.presentation_interval_stddev_ms >= 20
    assert concern.camera_aligned_containers == 3

    state.stop_for_diagnostic()
    with pytest.raises(ControlRejected, match="latest matching guide observation"):
        state.restore_guide("missing")

    observation = state.inspect_guide()
    assert observation["classification"] == "synthetic_human_observation"
    assert observation["within_reference"] is False
    assert observation["observed_offset_mm"] == pytest.approx(DISTURBED_GUIDE_OFFSET_MM)
    assert observation["reference_tolerance_mm"] == GUIDE_REFERENCE_TOLERANCE_MM

    receipt = state.restore_guide(observation["observation_id"])
    assert receipt["classification"] == "simulator_control_only"
    assert receipt["result"] == "restored_to_approved_reference"

    state.run_diagnostic_batch()
    diagnostic = state.observation(ESCAPED_CONCERN_SEQUENCE + 1)
    assert diagnostic.run_state_code == 2
    assert diagnostic.presentation_interval_stddev_ms < 11
    assert diagnostic.camera_aligned_containers == diagnostic.camera_observed_containers == 5
    assert diagnostic.accepted_containers == diagnostic.camera_observed_containers


def test_stateful_diagnostic_batch_remains_bad_without_restore():
    state = LabelerDemoState()
    state.observation(ESCAPED_CONCERN_SEQUENCE)
    state.stop_for_diagnostic()
    state.run_diagnostic_batch()

    diagnostic = state.observation(ESCAPED_CONCERN_SEQUENCE + 1)
    assert diagnostic.run_state_code == 2
    assert diagnostic.presentation_interval_stddev_ms >= 19
    assert diagnostic.camera_aligned_containers == 3
    assert diagnostic.reject_candidates == 2


def test_guide_inspection_requires_stopped_diagnostic_state():
    state = LabelerDemoState()
    state.observation(ESCAPED_CONCERN_SEQUENCE)

    with pytest.raises(ControlRejected, match="stopped diagnostic state"):
        state.inspect_guide()


def test_runtime_scenario_sequence_freezes_while_stopped_and_advances_for_diagnostic_run():
    state = LabelerDemoState()
    state.observation(ESCAPED_CONCERN_SEQUENCE)
    state.stop_for_diagnostic()

    first_stopped = state.next_observation()
    second_stopped = state.next_observation()

    assert first_stopped.sequence == second_stopped.sequence == ESCAPED_CONCERN_SEQUENCE
    assert first_stopped.run_state_code == second_stopped.run_state_code == 0
    assert first_stopped.roll_change_recent is True
    assert second_stopped.roll_change_recent is True

    state.run_diagnostic_batch()
    diagnostic = state.next_observation()

    assert diagnostic.sequence == ESCAPED_CONCERN_SEQUENCE + 1
    assert diagnostic.run_state_code == 2


def test_runtime_scenario_sequence_advances_again_after_resume():
    state = LabelerDemoState()
    state.observation(ESCAPED_CONCERN_SEQUENCE)
    state.stop_for_diagnostic()
    state.next_observation()
    state.resume_production()

    resumed = state.next_observation()

    assert resumed.sequence == ESCAPED_CONCERN_SEQUENCE + 1
    assert resumed.run_state_code == 1


def test_labeler_emulator_outputs_finite_numeric_evidence():
    for sequence in range(0, 320, 7):
        observation = observable_for_sequence(sequence)
        values = (
            observation.line_speed_cpm,
            observation.presentation_interval_stddev_ms,
            observation.max_abs_alignment_offset_mm,
        )
        assert all(math.isfinite(value) for value in values)


def test_labeler_emulator_rejects_negative_sequence():
    with pytest.raises(ValueError, match="non-negative"):
        observable_for_sequence(-1)
