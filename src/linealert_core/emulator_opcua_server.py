"""Expose causal-emulator evidence through a local OPC UA server."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .causal_emulator import CycleEvidence, EmulatorConfig, LaneBDegradationEmulator

NAMESPACE_URI = "urn:linealert:emulator:lane-b"
PROFILE_ID = "linealert-lane-b-observable-v1"


@dataclass(frozen=True, slots=True)
class ObservableSnapshot:
    """Transport manifest containing observable values and a replay-resistant hash chain."""

    cycle: int
    source_timestamp: str
    profile: str
    nodes: dict[str, float | bool]
    previous_sha256: str
    snapshot_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "cycle": self.cycle,
            "source_timestamp": self.source_timestamp,
            "profile": self.profile,
            "nodes": self.nodes,
            "previous_sha256": self.previous_sha256,
            "snapshot_sha256": self.snapshot_sha256,
        }


def build_observable_snapshot(
    evidence: CycleEvidence,
    *,
    source_timestamp: datetime,
    previous_sha256: str = "GENESIS",
) -> ObservableSnapshot:
    """Bind one observable cycle to its predecessor without exposing hidden truth."""

    if source_timestamp.tzinfo is None or source_timestamp.utcoffset() is None:
        raise ValueError("source_timestamp must be timezone-aware")
    content: dict[str, object] = {
        "cycle": evidence.cycle,
        "source_timestamp": source_timestamp.isoformat(),
        "profile": PROFILE_ID,
        "nodes": evidence.opcua_nodes(),
        "previous_sha256": previous_sha256,
    }
    digest = hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ObservableSnapshot(
        cycle=evidence.cycle,
        source_timestamp=source_timestamp.isoformat(),
        profile=PROFILE_ID,
        nodes=evidence.opcua_nodes(),
        previous_sha256=previous_sha256,
        snapshot_sha256=digest,
    )


def verify_snapshot_chain(snapshots: Sequence[ObservableSnapshot]) -> bool:
    previous = "GENESIS"
    for snapshot in snapshots:
        if snapshot.previous_sha256 != previous:
            return False
        content = snapshot.to_dict()
        claimed = str(content.pop("snapshot_sha256"))
        actual = hashlib.sha256(
            json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if claimed != actual:
            return False
        previous = claimed
    return True


async def serve_emulator(
    *,
    endpoint: str,
    config: EmulatorConfig,
    publish_interval_seconds: float,
    loop: bool,
) -> None:
    """Publish only observable emulator evidence as read-only OPC UA variables."""

    if publish_interval_seconds <= 0:
        raise ValueError("publish_interval_seconds must be positive")
    try:
        from asyncua import Server, ua  # type: ignore[import-not-found,import-untyped]
    except ImportError as exc:
        raise SystemExit("Install the OPC UA extra: python -m pip install -e .[opcua]") from exc

    run = LaneBDegradationEmulator(config).run()
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("LineAlert Lane B Causal Emulator")
    namespace_index = await server.register_namespace(NAMESPACE_URI)
    root = await server.nodes.objects.add_object(namespace_index, "LineAlertEmulator")

    first_nodes = run.records[0].evidence.opcua_nodes()
    variables: dict[str, Any] = {}
    for path, value in first_nodes.items():
        node_id = ua.NodeId(path, namespace_index)
        variables[path] = await root.add_variable(node_id, path.rsplit(".", 1)[-1], value)
    cycle_node = await root.add_variable(
        ua.NodeId("Line04.Emulator.Cycle", namespace_index), "Cycle", 0
    )
    hash_node = await root.add_variable(
        ua.NodeId("Line04.Emulator.SnapshotSha256", namespace_index),
        "SnapshotSha256",
        "",
    )

    print(json.dumps({"endpoint": endpoint, "namespace_uri": NAMESPACE_URI, "read_only": True}))
    async with server:
        while True:
            previous = "GENESIS"
            for record in run.records:
                timestamp = config.start_time + (
                    record.events[0].timestamp - config.start_time
                )
                snapshot = build_observable_snapshot(
                    record.evidence,
                    source_timestamp=timestamp,
                    previous_sha256=previous,
                )
                for path, value in snapshot.nodes.items():
                    await variables[path].write_value(value)
                await cycle_node.write_value(snapshot.cycle)
                await hash_node.write_value(snapshot.snapshot_sha256)
                previous = snapshot.snapshot_sha256
                await asyncio.sleep(publish_interval_seconds)
            if not loop:
                return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="opc.tcp://0.0.0.0:4840/linealert/emulator/")
    parser.add_argument("--cycles", type=int, default=160)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--drift-onset", type=int, default=20)
    parser.add_argument("--intervention-cycle", type=int)
    parser.add_argument("--publish-seconds", type=float, default=0.25)
    parser.add_argument("--loop", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = EmulatorConfig(
        cycles=args.cycles,
        seed=args.seed,
        drift_onset_cycle=args.drift_onset,
        intervention_cycle=args.intervention_cycle,
        start_time=datetime.now(UTC),
    )
    asyncio.run(
        serve_emulator(
            endpoint=args.endpoint,
            config=config,
            publish_interval_seconds=args.publish_seconds,
            loop=args.loop,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
