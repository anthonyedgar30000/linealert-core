"""Bridge Labeler 2 OPC UA evidence and bounded simulator-only demo controls to Plant Canvas."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .labeler_demo_opcua_server import ASSET_ID, NAMESPACE_URI, NODE_IDS, PROFILE_ID
from .opcua_adapter import classify_status
from .opcua_bridge import JsonlRecorder, ObservationHistory

SOURCE_ID = "linealert-labeler2-opcua-local"
ALLOWED_DEMO_CONTROLS = {
    "stop_for_diagnostic": "/control/stop-for-diagnostic",
    "inspect_guide": "/control/inspect-guide",
    "restore_guide": "/control/restore-guide",
    "run_diagnostic_batch": "/control/run-diagnostic-batch",
    "resume_production": "/control/resume-production",
    "fast_forward_to_next_concern": "/control/fast-forward-next-concern",
}


@dataclass(frozen=True, slots=True)
class LabelerNodeMapping:
    signal: str
    node_id: str
    unit: str
    kind: str


LABELER_NODE_MAPPINGS = (
    LabelerNodeMapping(
        "emulator_sequence",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['emulator_sequence']}",
        "count",
        "int",
    ),
    LabelerNodeMapping(
        "run_state_code",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['run_state_code']}",
        "code",
        "int",
    ),
    LabelerNodeMapping(
        "line_speed_cpm",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['line_speed_cpm']}",
        "containers/min",
        "float",
    ),
    LabelerNodeMapping(
        "presentation_interval_stddev_ms",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['presentation_interval_stddev_ms']}",
        "ms",
        "float",
    ),
    LabelerNodeMapping(
        "camera_observed_containers",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['camera_observed_containers']}",
        "containers",
        "int",
    ),
    LabelerNodeMapping(
        "camera_aligned_containers",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['camera_aligned_containers']}",
        "containers",
        "int",
    ),
    LabelerNodeMapping(
        "apparent_skew_events",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['apparent_skew_events']}",
        "events",
        "int",
    ),
    LabelerNodeMapping(
        "max_abs_alignment_offset_mm",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['max_abs_alignment_offset_mm']}",
        "mm",
        "float",
    ),
    LabelerNodeMapping(
        "accepted_containers",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['accepted_containers']}",
        "containers",
        "int",
    ),
    LabelerNodeMapping(
        "reject_candidates",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['reject_candidates']}",
        "containers",
        "int",
    ),
    LabelerNodeMapping(
        "roll_change_recent",
        f"nsu={NAMESPACE_URI};s={NODE_IDS['roll_change_recent']}",
        "boolean",
        "bool",
    ),
)


class LabelerSnapshot:
    """Thread-safe current snapshot that preserves source identity when stale."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload: dict[str, Any] = {
            "schema_version": "linealert.observation.snapshot.v1",
            "connected": False,
            "profile": PROFILE_ID,
            "source_id": SOURCE_ID,
            "source_kind": "simulator",
            "source_scope": "simulator_only",
            "asset_id": ASSET_ID,
            "read_only": True,
            "reason_code": "EVIDENCE.OPCUA_NOT_CONNECTED",
            "signals": {},
        }

    def replace(self, payload: dict[str, Any]) -> None:
        immutable_copy = json.loads(json.dumps(payload))
        with self._lock:
            self._payload = immutable_copy

    def get(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._payload))

    def mark_unavailable(self, *, reason_code: str, error: str) -> dict[str, Any]:
        received = datetime.now(UTC)
        with self._lock:
            stale_signals: dict[str, Any] = {}
            for name, signal in self._payload.get("signals", {}).items():
                stale = dict(signal)
                source_timestamp = stale.get("source_timestamp")
                age_ms: float | None = None
                try:
                    if source_timestamp:
                        observed = datetime.fromisoformat(source_timestamp)
                        if observed.tzinfo is None:
                            observed = observed.replace(tzinfo=UTC)
                        age_ms = (received - observed).total_seconds() * 1000
                except (TypeError, ValueError):
                    age_ms = None
                stale.update(
                    {
                        "quality": "stale",
                        "reason_code": "EVIDENCE.TELEMETRY_STALE",
                        "age_ms": age_ms,
                    }
                )
                stale_signals[name] = stale

            self._payload = {
                "schema_version": "linealert.observation.snapshot.v1",
                "connected": False,
                "profile": PROFILE_ID,
                "source_id": SOURCE_ID,
                "source_kind": "simulator",
                "source_scope": "simulator_only",
                "asset_id": ASSET_ID,
                "read_only": True,
                "bridge_timestamp": received.isoformat(),
                "reason_code": reason_code,
                "error": error,
                "signals": stale_signals,
            }
            return json.loads(json.dumps(self._payload))


async def _runtime_node_id(client: Any, expanded_node_id: str) -> str:
    prefix = "nsu="
    marker = ";s="
    if not expanded_node_id.startswith(prefix) or marker not in expanded_node_id:
        raise ValueError("only declared nsu string node identifiers are supported")
    namespace_uri, identifier = expanded_node_id[len(prefix) :].split(marker, 1)
    namespace_index = await client.get_namespace_index(namespace_uri)
    return f"ns={namespace_index};s={identifier}"


def _qualified_signal(
    mapping: LabelerNodeMapping,
    data_value: Any,
    *,
    received_timestamp: datetime,
    observation_id: str,
) -> dict[str, Any]:
    status = getattr(data_value, "StatusCode", None)
    quality, reason_code = classify_status(status)
    source_timestamp = getattr(data_value, "SourceTimestamp", None)
    if source_timestamp is not None and source_timestamp.tzinfo is None:
        source_timestamp = source_timestamp.replace(tzinfo=UTC)

    raw = getattr(getattr(data_value, "Value", None), "Value", None)
    value: float | int | bool | None = None

    if quality == "good":
        try:
            if mapping.kind == "bool":
                if not isinstance(raw, bool):
                    raise ValueError("expected bool")
                value = raw
            elif mapping.kind == "int":
                numeric = float(raw)
                if not math.isfinite(numeric) or not numeric.is_integer():
                    raise ValueError("expected finite integer")
                value = int(numeric)
            elif mapping.kind == "float":
                numeric = float(raw)
                if not math.isfinite(numeric):
                    raise ValueError("expected finite number")
                value = numeric
            else:
                raise ValueError("unsupported mapping kind")
        except (TypeError, ValueError, OverflowError):
            quality = "bad"
            reason_code = "EVIDENCE.OPCUA_VALUE_TYPE_MISMATCH"
            value = None

    if source_timestamp is None:
        quality = "unknown"
        reason_code = "EVIDENCE.SOURCE_TIMESTAMP_MISSING"
        value = None

    return {
        "signal": mapping.signal,
        "value": value,
        "unit": mapping.unit,
        "source_timestamp": source_timestamp.isoformat() if source_timestamp else None,
        "received_timestamp": received_timestamp.isoformat(),
        "observation_id": observation_id,
        "status_code": str(status),
        "quality": quality,
        "reason_code": reason_code,
        "node_id": mapping.node_id,
    }


async def poll_labeler_opcua(
    endpoint: str,
    snapshot: LabelerSnapshot,
    interval: float,
    recorder: JsonlRecorder | None = None,
    history: ObservationHistory | None = None,
) -> None:
    if interval <= 0:
        raise ValueError("poll interval must be positive")

    try:
        from asyncua import Client
        from asyncua.ua.uaerrors import UaError
    except ImportError as exc:
        raise SystemExit("Install the OPC UA extra: python -m pip install -e '.[opcua]'") from exc

    observation_sequence = 0
    while True:
        try:
            async with Client(url=endpoint) as client:
                runtime_ids = [
                    await _runtime_node_id(client, mapping.node_id)
                    for mapping in LABELER_NODE_MAPPINGS
                ]
                nodes = [client.get_node(node_id) for node_id in runtime_ids]

                while True:
                    received_timestamp = datetime.now(UTC)
                    values = await asyncio.gather(*(node.read_data_value() for node in nodes))
                    observation_sequence += 1
                    signal_map = {
                        mapping.signal: _qualified_signal(
                            mapping,
                            value,
                            received_timestamp=received_timestamp,
                            observation_id=f"{SOURCE_ID}:{observation_sequence}:{mapping.signal}",
                        )
                        for mapping, value in zip(
                            LABELER_NODE_MAPPINGS,
                            values,
                            strict=True,
                        )
                    }
                    all_good = all(
                        signal["quality"] == "good" for signal in signal_map.values()
                    )
                    payload = {
                        "schema_version": "linealert.observation.snapshot.v1",
                        "connected": True,
                        "profile": PROFILE_ID,
                        "source_id": SOURCE_ID,
                        "source_kind": "simulator",
                        "source_scope": "simulator_only",
                        "asset_id": ASSET_ID,
                        "read_only": True,
                        "proxy_warning": (
                            "Labeler 2 simulator evidence; not verified physical machine state."
                        ),
                        "bridge_timestamp": received_timestamp.isoformat(),
                        "observation_sequence": observation_sequence,
                        "reason_code": (
                            "EVIDENCE.OPCUA_SAMPLE_QUALIFIED"
                            if all_good
                            else "EVIDENCE.OPCUA_SAMPLE_UNQUALIFIED"
                        ),
                        "semantic_admission": {
                            "scope": "simulator_only",
                            "admitted": all_good,
                            "reason_code": (
                                "EVIDENCE.SIMULATOR_SOURCE_ADMITTED"
                                if all_good
                                else "EVIDENCE.SIMULATOR_SOURCE_NOT_ADMITTED"
                            ),
                        },
                        "signals": signal_map,
                    }
                    snapshot.replace(payload)
                    if history is not None:
                        history.append(payload)
                    if recorder is not None:
                        recorder.append(payload)
                    await asyncio.sleep(interval)
        except (TimeoutError, OSError, ConnectionError, UaError) as exc:
            unavailable = snapshot.mark_unavailable(
                reason_code="EVIDENCE.OPCUA_CONNECTION_UNAVAILABLE",
                error=type(exc).__name__,
            )
            if history is not None:
                history.append(unavailable)
            if recorder is not None:
                recorder.append(unavailable)
            await asyncio.sleep(1.0)


def _simulator_target_url(base_url: str, path: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("simulator control endpoint must be loopback HTTP")
    return base_url.rstrip("/") + path


def _control_target_url(base_url: str, action: str) -> str:
    path = ALLOWED_DEMO_CONTROLS.get(action)
    if path is None:
        raise ValueError("unknown simulator control action")
    return _simulator_target_url(base_url, path)


def forward_demo_control(
    base_url: str,
    action: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Forward one allow-listed simulator-only control without touching OPC UA."""

    target = _control_target_url(base_url, action)
    body = json.dumps(payload or {}, separators=(",", ":")).encode()
    request = Request(
        target,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=2.0) as response:  # noqa: S310 - validated loopback URL
            data = json.loads(response.read().decode())
            return int(response.status), data
    except HTTPError as exc:
        try:
            data = json.loads(exc.read().decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = {"accepted": False, "reason": "simulator control rejected"}
        return int(exc.code), data
    except (URLError, TimeoutError, OSError) as exc:
        return 502, {
            "schema_version": "linealert.simulator-control-result.v1",
            "accepted": False,
            "source_scope": "simulator_only",
            "asset_id": ASSET_ID,
            "reason": "simulator_control_unavailable",
            "error": type(exc).__name__,
            "equipment_effect": "none",
        }


def fetch_demo_plant_events(base_url: str, after: int) -> tuple[int, dict[str, Any]]:
    """Fetch source-owned public simulator events over the validated loopback channel."""

    if after < 0:
        raise ValueError("after must be non-negative")
    target = _simulator_target_url(base_url, f"/events?after={after}")
    request = Request(target, method="GET")
    try:
        with urlopen(request, timeout=2.0) as response:  # noqa: S310 - validated loopback URL
            data = json.loads(response.read().decode())
            return int(response.status), data
    except HTTPError as exc:
        try:
            data = json.loads(exc.read().decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = {"events": [], "error": "simulator event feed rejected"}
        return int(exc.code), data
    except (URLError, TimeoutError, OSError) as exc:
        return 502, {
            "schema_version": "linealert.simulator-plant-events.v1",
            "source_scope": "simulator_only",
            "asset_id": ASSET_ID,
            "events": [],
            "error": "simulator_event_feed_unavailable",
            "error_type": type(exc).__name__,
        }


def labeler_handler_for(
    docs: Path,
    snapshot: LabelerSnapshot,
    history: ObservationHistory,
    *,
    control_base_url: str,
) -> type[SimpleHTTPRequestHandler]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(docs), **kwargs)

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json_body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 0 or length > 8192:
                raise ValueError("invalid request length")
            if length == 0:
                return {}
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            return payload

        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if request.path == "/api/telemetry":
                self._send_json(200, snapshot.get())
                return
            if request.path == "/api/history":
                self._send_json(200, history.get(limit=240))
                return
            if request.path == "/api/plant-events":
                try:
                    raw_after = parse_qs(request.query).get("after", ["0"])[0]
                    after = int(raw_after)
                    status, payload = fetch_demo_plant_events(control_base_url, after)
                except (TypeError, ValueError) as exc:
                    self._send_json(400, {"events": [], "error": str(exc)})
                    return
                self._send_json(status, payload)
                return
            return super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if request.path != "/api/demo-control":
                self._send_json(404, {"accepted": False, "reason": "not_found"})
                return
            try:
                body = self._json_body()
                action = body.pop("action", None)
                if not isinstance(action, str):
                    raise ValueError("action is required")
                status, result = forward_demo_control(control_base_url, action, body)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._send_json(
                    400,
                    {
                        "schema_version": "linealert.simulator-control-result.v1",
                        "accepted": False,
                        "source_scope": "simulator_only",
                        "asset_id": ASSET_ID,
                        "reason": str(exc),
                        "equipment_effect": "none",
                    },
                )
                return
            self._send_json(status, result)

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint",
        default="opc.tcp://127.0.0.1:4841/linealert/labeler2/",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8775)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--capture-jsonl", type=Path)
    parser.add_argument("--history-size", type=int, default=7200)
    parser.add_argument("--sim-control-url", default="http://127.0.0.1:4842")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _control_target_url(args.sim_control_url, "inspect_guide")
    docs = Path(__file__).resolve().parents[2] / "docs"
    snapshot = LabelerSnapshot()
    history = ObservationHistory(maxlen=args.history_size, persistence="memory_only")
    recorder = JsonlRecorder(args.capture_jsonl) if args.capture_jsonl else None

    thread = threading.Thread(
        target=lambda: asyncio.run(
            poll_labeler_opcua(
                args.endpoint,
                snapshot,
                args.poll_seconds,
                recorder,
                history,
            )
        ),
        daemon=True,
    )
    thread.start()

    server = ThreadingHTTPServer(
        (args.host, args.port),
        labeler_handler_for(
            docs,
            snapshot,
            history,
            control_base_url=args.sim_control_url,
        ),
    )
    print(f"LineAlert Labeler Canvas: http://{args.host}:{args.port}/triage/")
    print(f"Qualified telemetry: http://{args.host}:{args.port}/api/telemetry")
    print(f"Plant events: http://{args.host}:{args.port}/api/plant-events")
    print(f"Simulator controls: {args.sim_control_url} via /api/demo-control")
    print("OPC UA source: read_only · simulator control: localhost_only · no equipment control")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
