from statistics import mean

from linealert_core.causal_emulator import EmulatorConfig, LaneBDegradationEmulator


def test_same_seed_produces_identical_evidence() -> None:
    first = LaneBDegradationEmulator(EmulatorConfig(seed=44)).run()
    second = LaneBDegradationEmulator(EmulatorConfig(seed=44)).run()
    assert first.evidence_fingerprint == second.evidence_fingerprint
    assert first.visible_records() == second.visible_records()


def test_visible_evidence_excludes_private_cause_variables() -> None:
    run = LaneBDegradationEmulator().run()
    visible = run.visible_records()[0]
    assert "pneumatic_leak_fraction" not in visible
    assert "actuator_stiction_fraction" not in visible
    assert "degradation_fraction" not in visible


def test_gradual_drift_increases_latency_and_downstream_offset() -> None:
    run = LaneBDegradationEmulator(EmulatorConfig(seed=9, cycles=150)).run()
    early = run.records[10:30]
    late = run.records[-20:]
    assert mean(record.evidence.camera_actuator_latency_ms for record in late) > mean(
        record.evidence.camera_actuator_latency_ms for record in early
    ) + 25.0
    assert mean(record.evidence.s1_arrival_ms for record in late) > mean(
        record.evidence.s1_arrival_ms for record in early
    ) + 25.0
    assert mean(abs(record.evidence.label_offset_mm) for record in late) > mean(
        abs(record.evidence.label_offset_mm) for record in early
    ) + 1.0


def test_stable_wrapper_ratio_does_not_follow_lane_b_drift() -> None:
    run = LaneBDegradationEmulator(EmulatorConfig(seed=71, cycles=150)).run()
    ratios = [record.evidence.feed_wrapper_ratio for record in run.records]
    assert max(abs(value - 1.0) for value in ratios) < 0.01


def test_intervention_reduces_observed_latency_and_defects() -> None:
    run = LaneBDegradationEmulator(
        EmulatorConfig(seed=19, cycles=160, intervention_cycle=120)
    ).run()
    before = run.records[100:120]
    after = run.records[120:140]
    assert mean(record.evidence.camera_actuator_latency_ms for record in after) < mean(
        record.evidence.camera_actuator_latency_ms for record in before
    ) - 15.0
    assert sum(not record.evidence.product_accepted for record in after) <= sum(
        not record.evidence.product_accepted for record in before
    )


def test_opcua_snapshot_has_only_observable_nodes() -> None:
    evidence = LaneBDegradationEmulator().run().records[0].evidence
    nodes = evidence.opcua_nodes()
    assert "Line04.Merge.S1ArrivalMs" in nodes
    assert "Line04.Quality.ProductAccepted" in nodes
    assert all("Leak" not in node and "Stiction" not in node for node in nodes)


def test_machine_event_export_is_replay_ready_and_excludes_hidden_truth() -> None:
    run = LaneBDegradationEmulator(EmulatorConfig(cycles=8, drift_onset_cycle=2)).run()
    events = run.machine_event_records()
    assert len(events) == 40
    assert events[0]["event_type"] == "ActuatorCommand"
    assert all("pneumatic_leak_fraction" not in event["attributes"] for event in events)
