"""Expose deterministic Labeler 2 demo observations through read-only OPC UA.

The OPC UA surface is evidence-only. Bounded simulator controls use a separate localhost HTTP
channel so demo actions never become OPC UA writes or equipment-control precedent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .labeler_demo_plant_events import (
    CONCERN_PHASE,
    ROLL_CHANGE_CORRECTION_PHASE,
    ROLL_CHANGE_PHASE,
    ROLL_CHANGE_RESUME_PHASE,
    ROLL_CHANGE_STOP_PHASE,
    SCENARIO_LENGTH,
    SIM_SECONDS_PER_SEQUENCE,
    fast_forward_target,
    public_events_at_sequence,
    roll_change_outcome,
)

NAMESPACE_URI = "urn:linealert:emulator:labeler2"
PROFILE_ID = "linealert-labeler2-observable-v1"
ASSET_ID = "Labeler 2"
CONTROL_SCOPE = "simulator_only"
GUIDE_REFERENCE_MM = 0.0
GUIDE_REFERENCE_TOLERANCE_MM = 0.4
DISTURBED_GUIDE_OFFSET_MM = 2.1

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


class ControlRejected(ValueError):
    """A simulator-only control request failed a declared prerequisite."""


class LabelerDemoState:
    """Private demo state; mechanism variables never cross the OPC UA evidence boundary."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cycle = -1
        self._sequence = 0
        self._guide_offset_mm = GUIDE_REFERENCE_MM
        self._roll_change_applied = False
        self._private_roll_outcome = "clean"
        self._production_enabled = True
        self._diagnostic_batches_remaining = 0
        self._inspection_counter = 0
        self._last_inspection_id: str | None = None
        self._last_inspection_cycle: int | None = None
        self._last_inspection_outside = False
        self._plant_events: dict[int, dict[str, Any]] = {}

    def _reset_cycle_locked(self, cycle: int) -> None:
        self._cycle = cycle
        self._guide_offset_mm = GUIDE_REFERENCE_MM
        self._roll_change_applied = False
        self._private_roll_outcome = roll_change_outcome(cycle)
        self._production_enabled = True
        self._diagnostic_batches_remaining = 0
        self._last_inspection_id = None
        self._last_inspection_cycle = None
        self._last_inspection_outside = False

    def _prepare_locked(self, sequence: int) -> None:
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        cycle = sequence // SCENARIO_LENGTH
        phase = sequence % SCENARIO_LENGTH
        if cycle != self._cycle:
            self._reset_cycle_locked(cycle)
        if phase >= ROLL_CHANGE_PHASE and not self._roll_change_applied:
            self._guide_offset_mm = (
                DISTURBED_GUIDE_OFFSET_MM
                if self._private_roll_outcome in {"caught", "escaped"}
                else GUIDE_REFERENCE_MM
            )
            self._roll_change_applied = True
        if (
            self._private_roll_outcome == "caught"
            and self._roll_change_applied
            and phase >= ROLL_CHANGE_CORRECTION_PHASE
        ):
            self._guide_offset_mm = GUIDE_REFERENCE_MM
        self._sequence = sequence

    def _record_events_at_locked(self, sequence: int) -> None:
        for event in public_events_at_sequence(sequence):
            payload = event.as_dict()
            self._plant_events[event.source_event_sequence] = payload

    def _record_events_through_locked(self, start: int, end: int) -> None:
        if end < start:
            return
        for sequence in range(start, end + 1):
            self._record_events_at_locked(sequence)

    def _run_state_locked(self) -> int:
        if self._diagnostic_batches_remaining > 0:
            return 2
        if not self._production_enabled:
            return 0
        phase = self._sequence % SCENARIO_LENGTH
        if ROLL_CHANGE_STOP_PHASE <= phase < ROLL_CHANGE_RESUME_PHASE:
            return 0
        return 1

    def _observation_locked(self) -> LabelerObservable:
        run_state_code = self._run_state_locked()
        if self._diagnostic_batches_remaining > 0:
            self._diagnostic_batches_remaining -= 1
        return observable_for_sequence(
            self._sequence,
            guide_offset_mm=self._guide_offset_mm,
            run_state_code=run_state_code,
        )

    def observation(self, sequence: int) -> LabelerObservable:
        """Evaluate an explicit scenario sequence for deterministic tests and replay fixtures."""

        with self._lock:
            self._prepare_locked(sequence)
            return self._observation_locked()

    def next_observation(self) -> LabelerObservable:
        """Advance production/scenario progression while keeping explicit diagnostic stops frozen."""

        with self._lock:
            if self._cycle < 0:
                self._prepare_locked(0)
                self._record_events_at_locked(0)
            elif self._production_enabled or self._diagnostic_batches_remaining > 0:
                next_sequence = self._sequence + 1
                self._record_events_at_locked(next_sequence)
                self._prepare_locked(next_sequence)
            return self._observation_locked()

    def plant_events_after(self, after: int) -> list[dict[str, Any]]:
        """Return source-owned public plant events after the supplied event sequence."""

        if after < 0:
            raise ControlRejected("after must be non-negative")
        with self._lock:
            return [
                dict(self._plant_events[key])
                for key in sorted(self._plant_events)
                if key > after
            ]

    def fast_forward_to_next_concern(self) -> dict[str, Any]:
        """Advance source simulation time to just before a future escaped-changeover concern."""

        with self._lock:
            if self._cycle < 0:
                self._prepare_locked(0)
            if not self._production_enabled or self._diagnostic_batches_remaining:
                raise ControlRejected("fast-forward requires ordinary production progression")
            from_sequence = self._sequence
            target_sequence, target_kind = fast_forward_target(from_sequence)
            if target_sequence > from_sequence:
                self._record_events_through_locked(from_sequence + 1, target_sequence)
                self._prepare_locked(target_sequence)
            advanced = target_sequence - from_sequence
            return self._receipt(
                "fast_forward_to_next_concern",
                "source_advanced_to_concern_precursor",
                from_sequence=from_sequence,
                target_sequence=target_sequence,
                advanced_sequences=advanced,
                advanced_simulated_seconds=advanced * SIM_SECONDS_PER_SEQUENCE,
                target_kind=target_kind,
            )

    def stop_for_diagnostic(self) -> dict[str, Any]:
        with self._lock:
            self._production_enabled = False
            self._diagnostic_batches_remaining = 0
            return self._receipt("stop_for_diagnostic", "stopped_for_bounded_diagnostic")

    def inspect_guide(self) -> dict[str, Any]:
        with self._lock:
            if self._production_enabled or self._diagnostic_batches_remaining:
                raise ControlRejected("guide verification requires the stopped diagnostic state")
            outside = abs(self._guide_offset_mm - GUIDE_REFERENCE_MM) > GUIDE_REFERENCE_TOLERANCE_MM
            self._inspection_counter += 1
            observation_id = (
                f"SIM-GUIDE-{self._cycle:04d}-{self._sequence:06d}-{self._inspection_counter:03d}"
            )
            self._last_inspection_id = observation_id
            self._last_inspection_cycle = self._cycle
            self._last_inspection_outside = outside
            return {
                "schema_version": "linealert.synthetic-human-observation.v1",
                "classification": "synthetic_human_observation",
                "source_kind": "simulated_operator",
                "source_scope": CONTROL_SCOPE,
                "asset_id": ASSET_ID,
                "action_id": "verify-guide-spacing",
                "observation_id": observation_id,
                "observed_offset_mm": round(self._guide_offset_mm - GUIDE_REFERENCE_MM, 2),
                "reference_tolerance_mm": GUIDE_REFERENCE_TOLERANCE_MM,
                "within_reference": not outside,
                "sequence_at_observation": self._sequence,
                "observed_at": datetime.now(UTC).isoformat(),
                "boundary": (
                    "Synthetic operator observation for demo workflow; it is not OPC UA evidence, "
                    "OEM truth, or verified physical state."
                ),
            }

    def restore_guide(self, observation_id: str | None) -> dict[str, Any]:
        with self._lock:
            if self._production_enabled or self._diagnostic_batches_remaining:
                raise ControlRejected("guide restoration requires the stopped diagnostic state")
            if not observation_id or observation_id != self._last_inspection_id:
                raise ControlRejected("restore requires the latest matching guide observation")
            if self._last_inspection_cycle != self._cycle:
                raise ControlRejected("guide observation belongs to a different simulator cycle")
            if not self._last_inspection_outside:
                raise ControlRejected(
                    "guide observation did not establish an out-of-reference condition"
                )
            self._guide_offset_mm = GUIDE_REFERENCE_MM
            self._last_inspection_outside = False
            return self._receipt("restore_guide_spacing", "restored_to_approved_reference")

    def run_diagnostic_batch(self) -> dict[str, Any]:
        with self._lock:
            if self._production_enabled:
                raise ControlRejected("diagnostic batch requires the stopped diagnostic state")
            self._diagnostic_batches_remaining = 4
            return self._receipt("run_diagnostic_batch", "diagnostic_batch_armed")

    def resume_production(self) -> dict[str, Any]:
        with self._lock:
            if self._diagnostic_batches_remaining:
                raise ControlRejected("cannot resume while a diagnostic batch is still emitting")
            self._production_enabled = True
            return self._receipt("resume_production", "production_resumed_in_simulator")

    def _receipt(self, action: str, result: str, **extra: Any) -> dict[str, Any]:
        return {
            "schema_version": "linealert.simulator-control-result.v1",
            "classification": "simulator_control_only",
            "source_scope": CONTROL_SCOPE,
            "asset_id": ASSET_ID,
            "action": action,
            "accepted": True,
            "result": result,
            "sequence_at_action": self._sequence,
            "recorded_at": datetime.now(UTC).isoformat(),
            "equipment_effect": "none_physical_simulator_only",
            "boundary": "Simulator control changes synthetic state only; it is not equipment control.",
            **extra,
        }


def _wave(sequence: int, base: float, amplitude: float, divisor: float) -> float:
    return base + math.sin(sequence / divisor) * amplitude


def observable_for_sequence(
    sequence: int,
    *,
    guide_offset_mm: float | None = None,
    run_state_code: int | None = None,
) -> LabelerObservable:
    """Return deterministic observable evidence for declared synthetic conditions.

    Optional private-state inputs let the running emulator respond to simulator controls without
    publishing those private mechanism variables as OPC UA evidence.
    """

    if sequence < 0:
        raise ValueError("sequence must be non-negative")

    phase = sequence % SCENARIO_LENGTH
    if guide_offset_mm is None:
        guide_offset_mm = DISTURBED_GUIDE_OFFSET_MM if phase >= ROLL_CHANGE_PHASE else GUIDE_REFERENCE_MM
    if run_state_code is None:
        if 100 <= phase < 110:
            run_state_code = 0
        elif 110 <= phase < 120:
            run_state_code = 2
        else:
            run_state_code = 1
    if run_state_code not in {0, 1, 2}:
        raise ValueError("run_state_code must be 0, 1, or 2")

    guide_outside = abs(guide_offset_mm - GUIDE_REFERENCE_MM) > GUIDE_REFERENCE_TOLERANCE_MM
    roll_recent = ROLL_CHANGE_PHASE <= phase < 120

    if run_state_code == 0:
        presentation = 21.0 if guide_outside else 9.4
        return LabelerObservable(
            sequence=sequence,
            run_state_code=0,
            line_speed_cpm=0.0,
            presentation_interval_stddev_ms=presentation,
            camera_observed_containers=0,
            camera_aligned_containers=0,
            apparent_skew_events=0,
            max_abs_alignment_offset_mm=0.0,
            accepted_containers=0,
            reject_candidates=0,
            roll_change_recent=roll_recent,
        )

    if run_state_code == 2:
        if guide_outside:
            presentation = _wave(sequence, 20.4, 0.5, 3.0)
            aligned = 3
            offset = 2.8
        else:
            presentation = _wave(sequence, 9.1, 0.2, 3.0)
            aligned = 5
            offset = 0.9
        return LabelerObservable(
            sequence=sequence,
            run_state_code=2,
            line_speed_cpm=24.0,
            presentation_interval_stddev_ms=presentation,
            camera_observed_containers=5,
            camera_aligned_containers=aligned,
            apparent_skew_events=5 - aligned,
            max_abs_alignment_offset_mm=offset,
            accepted_containers=aligned,
            reject_candidates=5 - aligned,
            roll_change_recent=roll_recent,
        )

    if phase < ROLL_CHANGE_PHASE:
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

    if guide_outside and phase < CONCERN_PHASE:
        progress = (phase - ROLL_CHANGE_PHASE) / (CONCERN_PHASE - ROLL_CHANGE_PHASE - 1)
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

    if guide_outside:
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
            roll_change_recent=roll_recent,
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
        roll_change_recent=roll_recent,
    )


def control_handler_for(state: LabelerDemoState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "LineAlertLabelerDemoControl/1"

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 0 or length > 8192:
                raise ControlRejected("invalid control payload length")
            if length == 0:
                return {}
            try:
                payload = json.loads(self.rfile.read(length))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ControlRejected("control payload must be valid JSON") from exc
            if not isinstance(payload, dict):
                raise ControlRejected("control payload must be a JSON object")
            return payload

        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if request.path == "/health":
                self._send_json(
                    200,
                    {
                        "schema_version": "linealert.simulator-control-health.v1",
                        "status": "ready",
                        "source_scope": CONTROL_SCOPE,
                        "asset_id": ASSET_ID,
                        "equipment_control": False,
                        "plant_event_orchestration": True,
                    },
                )
                return
            if request.path == "/events":
                try:
                    raw_after = parse_qs(request.query).get("after", ["0"])[0]
                    after = int(raw_after)
                    events = state.plant_events_after(after)
                except (TypeError, ValueError, ControlRejected) as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                self._send_json(
                    200,
                    {
                        "schema_version": "linealert.simulator-plant-events.v1",
                        "source_scope": CONTROL_SCOPE,
                        "asset_id": ASSET_ID,
                        "sim_seconds_per_sequence": SIM_SECONDS_PER_SEQUENCE,
                        "events": events,
                    },
                )
                return
            self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                body = self._body()
                if self.path == "/control/stop-for-diagnostic":
                    result = state.stop_for_diagnostic()
                elif self.path == "/control/inspect-guide":
                    result = state.inspect_guide()
                elif self.path == "/control/restore-guide":
                    result = state.restore_guide(body.get("observation_id"))
                elif self.path == "/control/run-diagnostic-batch":
                    result = state.run_diagnostic_batch()
                elif self.path == "/control/resume-production":
                    result = state.resume_production()
                elif self.path == "/control/fast-forward-next-concern":
                    result = state.fast_forward_to_next_concern()
                else:
                    self._send_json(404, {"error": "not_found"})
                    return
            except ControlRejected as exc:
                self._send_json(
                    409,
                    {
                        "schema_version": "linealert.simulator-control-result.v1",
                        "accepted": False,
                        "source_scope": CONTROL_SCOPE,
                        "asset_id": ASSET_ID,
                        "reason": str(exc),
                        "equipment_effect": "none",
                    },
                )
                return
            self._send_json(200, result)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


async def serve_emulator(
    *,
    endpoint: str,
    publish_interval_seconds: float,
    loop: bool,
    control_host: str,
    control_port: int,
) -> None:
    """Publish observable evidence and host a separate localhost simulator-control channel."""

    if publish_interval_seconds <= 0:
        raise ValueError("publish_interval_seconds must be positive")

    try:
        from asyncua import Server, ua  # type: ignore[import-not-found,import-untyped]
    except ImportError as exc:
        raise SystemExit("Install the OPC UA extra: python -m pip install -e '.[opcua]'") from exc

    state = LabelerDemoState()
    control_server = ThreadingHTTPServer(
        (control_host, control_port),
        control_handler_for(state),
    )
    control_thread = threading.Thread(target=control_server.serve_forever, daemon=True)
    control_thread.start()

    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("LineAlert Labeler 2 Observable Emulator")
    namespace_index = await server.register_namespace(NAMESPACE_URI)
    root = await server.nodes.objects.add_object(namespace_index, "LineAlertLabeler2")

    first_observation = state.next_observation()
    variables: dict[str, Any] = {}
    for node_id, value in first_observation.opcua_nodes().items():
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
            "read_only_opcua": True,
            "simulator_control": f"http://{control_host}:{control_port}",
            "simulator_control_scope": CONTROL_SCOPE,
            "plant_event_orchestration": True,
        }
    )

    try:
        async with server:
            while True:
                observation = state.next_observation()
                for node_id, value in observation.opcua_nodes().items():
                    await variables[node_id].write_value(value)
                if not loop and observation.sequence >= SCENARIO_LENGTH - 1:
                    return
                await asyncio.sleep(publish_interval_seconds)
    finally:
        control_server.shutdown()
        control_server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint",
        default="opc.tcp://127.0.0.1:4841/linealert/labeler2/",
    )
    parser.add_argument("--publish-seconds", type=float, default=0.5)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--control-host", default="127.0.0.1")
    parser.add_argument("--control-port", type=int, default=4842)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    asyncio.run(
        serve_emulator(
            endpoint=args.endpoint,
            publish_interval_seconds=args.publish_seconds,
            loop=args.loop,
            control_host=args.control_host,
            control_port=args.control_port,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
