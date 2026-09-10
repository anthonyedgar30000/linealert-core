"""Bridge the read-only Labeler 2 OPC UA emulator into the local Plant Canvas."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .labeler_demo_opcua_server import ASSET_ID, NAMESPACE_URI, NODE_IDS, PROFILE_ID
from .opcua_adapter import classify_status
from .opcua_bridge import JsonlRecorder, ObservationHistory, handler_for

SOURCE_ID = "linealert-labeler2-opcua-local"


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
        handler_for(docs, snapshot, history),
    )
    print(f"LineAlert Labeler Canvas: http://{args.host}:{args.port}/triage/")
    print(f"Qualified telemetry: http://{args.host}:{args.port}/api/telemetry")
    print("Source mode: simulator_only · read_only · no equipment control")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
