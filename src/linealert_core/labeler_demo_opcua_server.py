"""Expose deterministic Labeler 2 demo observations through read-only OPC UA."""

from __future__ import annotations

import argparse
import asyncio
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

NAMESPACE_URI = "urn:linealert:emulator:labeler2"
PROFILE_ID = "linealert-labeler2-observable-v1"
ASSET_ID = "Labeler 2"

NODE_IDS = {
    "emulator_sequence": "LineAlert.Labeler2.EmulatorSequence",
    "run_state_code": "LineAlert.Labeler2.RunStateCode",
    "line_speed_cpm": "LineAlert.Labeler2.LineSpeedCpm",
    "presentation_interval_stddev_ms": "LineAlert.Labeler2.PresentationIntervalStddevMs",
    "camera_observed_containers": "LineAlert.Labeler2.CameraObservedContainers",
    "camera_aligned_containers": "LineAlert.Labeler2.CameraAlignedContainers",
    "apparent_skew_events": "LineAlert.Labeler2.ApparentSkewEvents",
    "max_abs_alignment_offset_mm": "LineAlert.Labeler2.MaxAbsAlignmentOffsetMm",
    "accepted_containers": "LineAlert.Labeler2.AcceptedContainers",
    "reject_candidates": "LineAlert.Labeler2.RejectCandidates",
    "roll_change_recent": "LineAlert.Labeler2.RollChangeRecent",
}


@dataclass(frozen=True, slots=True)
class LabelerObservable:
    """One synthetic source snapshot containing only externally observable demo signals."""

    sequence: int
    run_state_code: int
    line_speed_cpm: float
    presentation_interval_stddev_ms: float
    camera_observed_containers: int
    camera_aligned_containers: int
    apparent_skew_events: int
    max_abs_alignment_offset_mm: float
    accepted_containers: int
    reject_candidates: int
    roll_change_recent: bool

    def opcua_nodes(self) -> dict[str, float | int | bool]:
        return {
            NODE_IDS["emulator_sequence"]: self.sequence,
            NODE_IDS["run_state_code"]: self.run_state_code,
            NODE_IDS["line_speed_cpm"]: self.line_speed_cpm,
            NODE_IDS["presentation_interval_stddev_ms"]: self.presentation_interval_stddev_ms,
            NODE_IDS["camera_observed_containers"]: self.camera_observed_containers,
            NODE_IDS["camera_aligned_containers"]: self.camera_aligned_containers,
            NODE_IDS["apparent_skew_events"]: self.apparent_skew_events,
            NODE_IDS["max_abs_alignment_offset_mm"]: self.max_abs_alignment_offset_mm,
            NODE_IDS["accepted_containers"]: self.accepted_containers,
            NODE_IDS["reject_candidates"]: self.reject_candidates,
            NODE_IDS["roll_change_recent"]: self.roll_change_recent,
        }


def _wave(sequence: int, base: float, amplitude: float, divisor: float) -> float:
    return base + math.sin(sequence / divisor) * amplitude


def observable_for_sequence(sequence: int) -> LabelerObservable:
    """Return deterministic observable evidence for one point in the repeating demo episode."""

    if sequence < 0:
        raise ValueError("sequence must be non-negative")

    phase = sequence % 160

    if phase < 40:
        return LabelerObservable(
            sequence=sequence,
            run_state_code=1,
            line_speed_cpm=_wave(sequence, 78.0, 0.45, 5.0),
            presentation_interval_stddev_ms=_wave(sequence, 8.0, 0.35, 4.0),
            camera_observed_containers=5,
            camera_aligned_containers=5,
            apparent_skew_events=0,
            max_abs_alignment_offset_mm=0.7,
            accepted_containers=5,
            reject_candidates=0,
            roll_change_recent=False,
        )

    if phase < 60:
        progress = (phase - 40) / 19
        presentation = 9.0 + progress * 5.0
        aligned = 5 if phase < 52 else 4
        return LabelerObservable(
            sequence=sequence,
            run_state_code=1,
            line_speed_cpm=_wave(sequence, 78.0, 0.35, 5.0),
            presentation_interval_stddev_ms=presentation,
            camera_observed_containers=5,
            camera_aligned_containers=aligned,
            apparent_skew_events=0 if aligned == 5 else 1,
            max_abs_alignment_offset_mm=0.9 if aligned == 5 else 1.8,
            accepted_containers=aligned,
            reject_candidates=5 - aligned,
            roll_change_recent=True,
        )

    if phase < 100:
        return LabelerObservable(
            sequence=sequence,
            run_state_code=1,
            line_speed_cpm=_wave(sequence, 78.0, 0.3, 6.0),
            presentation_interval_stddev_ms=_wave(sequence, 21.0, 0.8, 4.5),
            camera_observed_containers=5,
            camera_aligned_containers=3,
            apparent_skew_events=2,
            max_abs_alignment_offset_mm=2.9,
            accepted_containers=3,
            reject_candidates=2,
            roll_change_recent=True,
        )

    if phase < 110:
        return LabelerObservable(
            sequence=sequence,
            run_state_code=0,
            line_speed_cpm=0.0,
            presentation_interval_stddev_ms=21.0,
            camera_observed_containers=0,
            camera_aligned_containers=0,
            apparent_skew_events=0,
            max_abs_alignment_offset_mm=0.0,
            accepted_containers=0,
            reject_candidates=0,
            roll_change_recent=True,
        )

    if phase < 120:
        return LabelerObservable(
            sequence=sequence,
            run_state_code=2,
            line_speed_cpm=24.0,
            presentation_interval_stddev_ms=_wave(sequence, 9.1, 0.2, 3.0),
            camera_observed_containers=5,
            camera_aligned_containers=5,
            apparent_skew_events=0,
            max_abs_alignment_offset_mm=0.9,
            accepted_containers=5,
            reject_candidates=0,
            roll_change_recent=True,
        )

    return LabelerObservable(
        sequence=sequence,
        run_state_code=1,
        line_speed_cpm=_wave(sequence, 78.0, 0.4, 5.0),
        presentation_interval_stddev_ms=_wave(sequence, 9.5, 0.45, 4.0),
        camera_observed_containers=5,
        camera_aligned_containers=5,
        apparent_skew_events=0,
        max_abs_alignment_offset_mm=0.9,
        accepted_containers=5,
        reject_candidates=0,
        roll_change_recent=False,
    )


async def serve_emulator(
    *,
    endpoint: str,
    publish_interval_seconds: float,
    loop: bool,
) -> None:
    """Publish the observable episode without exposing simulator-private mechanism truth."""

    if publish_interval_seconds <= 0:
        raise ValueError("publish_interval_seconds must be positive")

    try:
        from asyncua import Server, ua  # type: ignore[import-not-found,import-untyped]
    except ImportError as exc:
        raise SystemExit("Install the OPC UA extra: python -m pip install -e '.[opcua]'") from exc

    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("LineAlert Labeler 2 Observable Emulator")
    namespace_index = await server.register_namespace(NAMESPACE_URI)
    root = await server.nodes.objects.add_object(namespace_index, "LineAlertLabeler2")

    first = observable_for_sequence(0).opcua_nodes()
    variables: dict[str, Any] = {}
    for node_id, value in first.items():
        browse_name = node_id.rsplit(".", 1)[-1]
        variables[node_id] = await root.add_variable(
            ua.NodeId(node_id, namespace_index),
            browse_name,
            value,
        )

    print(
        {
            "endpoint": endpoint,
            "namespace_uri": NAMESPACE_URI,
            "profile": PROFILE_ID,
            "asset_id": ASSET_ID,
            "read_only": True,
        }
    )

    sequence = 0
    async with server:
        while True:
            observation = observable_for_sequence(sequence)
            for node_id, value in observation.opcua_nodes().items():
                await variables[node_id].write_value(value)
            sequence += 1
            if not loop and sequence >= 160:
                return
            await asyncio.sleep(publish_interval_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint",
        default="opc.tcp://127.0.0.1:4841/linealert/labeler2/",
    )
    parser.add_argument("--publish-seconds", type=float, default=0.5)
    parser.add_argument("--loop", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    asyncio.run(
        serve_emulator(
            endpoint=args.endpoint,
            publish_interval_seconds=args.publish_seconds,
            loop=args.loop,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
