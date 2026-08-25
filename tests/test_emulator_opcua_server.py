from dataclasses import replace
from datetime import UTC, datetime, timedelta

from linealert_core.causal_emulator import EmulatorConfig, LaneBDegradationEmulator
from linealert_core.emulator_opcua_server import (
    build_observable_snapshot,
    verify_snapshot_chain,
)


def snapshots(count: int = 5):
    run = LaneBDegradationEmulator(
        EmulatorConfig(cycles=8, drift_onset_cycle=2)
    ).run()
    result = []
    previous = "GENESIS"
    start = datetime(2026, 8, 25, tzinfo=UTC)
    for index, record in enumerate(run.records[:count]):
        snapshot = build_observable_snapshot(
            record.evidence,
            source_timestamp=start + timedelta(seconds=index),
            previous_sha256=previous,
        )
        result.append(snapshot)
        previous = snapshot.snapshot_sha256
    return result


def test_snapshot_exposes_observations_but_not_hidden_cause() -> None:
    snapshot = snapshots(1)[0]
    assert "Line04.LaneB.CameraActuatorLatencyMs" in snapshot.nodes
    assert "Line04.Merge.S1ArrivalMs" in snapshot.nodes
    assert all("Leak" not in name and "Stiction" not in name for name in snapshot.nodes)


def test_snapshot_chain_verifies_in_order() -> None:
    assert verify_snapshot_chain(snapshots())


def test_snapshot_chain_rejects_reorder_and_tampering() -> None:
    valid = snapshots()
    assert not verify_snapshot_chain([valid[1], valid[0], *valid[2:]])
    bad_nodes = dict(valid[2].nodes)
    bad_nodes["Line04.Merge.S1ArrivalMs"] = 999.0
    tampered = replace(valid[2], nodes=bad_nodes)
    assert not verify_snapshot_chain([*valid[:2], tampered, *valid[3:]])
