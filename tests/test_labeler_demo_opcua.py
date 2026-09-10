import math

import pytest

from linealert_core.labeler_demo_opcua_server import (
    ASSET_ID,
    NODE_IDS,
    PROFILE_ID,
    observable_for_sequence,
)


def test_labeler_emulator_contract_is_deterministic_and_observable_only():
    first = observable_for_sequence(67)
    second = observable_for_sequence(67)

    assert first == second
    assert ASSET_ID == "Labeler 2"
    assert PROFILE_ID == "linealert-labeler2-observable-v1"
    assert set(first.opcua_nodes()) == set(NODE_IDS.values())
    assert all(
        forbidden not in " ".join(first.opcua_nodes()).lower()
        for forbidden in ("root_cause", "fault_truth", "hidden_mechanism")
    )


def test_labeler_emulator_episode_moves_through_observable_states():
    baseline = observable_for_sequence(10)
    approach = observable_for_sequence(55)
    concern = observable_for_sequence(70)
    stopped = observable_for_sequence(104)
    diagnostic = observable_for_sequence(114)
    recovered = observable_for_sequence(135)

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
    assert diagnostic.camera_aligned_containers == 5
    assert diagnostic.presentation_interval_stddev_ms < 11

    assert recovered.run_state_code == 1
    assert recovered.roll_change_recent is False
    assert recovered.camera_aligned_containers == recovered.camera_observed_containers
    assert recovered.accepted_containers == recovered.camera_observed_containers


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
