"""Local read-only OPC UA to LineAlert dashboard bridge."""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .opcua_adapter import (
    DEFAULT_MAPPINGS,
    ProxySignal,
    QualifiedSample,
    conveyor_arrival_ms,
    qualify_value,
)


class Snapshot:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload: dict[str, Any] = {
            "schema_version": "linealert.observation.snapshot.v1",
            "connected": False,
            "profile": "microsoft-opc-plc-proxy-v1",
            "source_id": "microsoft-opc-plc-local",
            "asset_id": "SIM-OPCPLC-01",
            "read_only": True,
            "proxy_warning": "Simulator proxy evidence; not verified physical conveyor state.",
            "reason_code": "EVIDENCE.OPCUA_NOT_CONNECTED",
            "signals": {},
        }

    def replace(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._payload = payload

    def get(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._payload)

    def mark_unavailable(self, *, reason_code: str, error: str) -> dict[str, Any]:
        """Retain the last observation as stale evidence without publishing it as current."""

        received = datetime.now(UTC)
        with self._lock:
            stale_signals: dict[str, Any] = {}
            for name, signal in self._payload.get("signals", {}).items():
                stale = dict(signal)
                source_timestamp = stale.get("source_timestamp")
                try:
                    observed = datetime.fromisoformat(source_timestamp) if source_timestamp else None
                    if observed is not None and observed.tzinfo is None:
                        observed = observed.replace(tzinfo=UTC)
                    age_ms = (received - observed).total_seconds() * 1000 if observed else None
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
                "profile": "microsoft-opc-plc-proxy-v1",
                "source_id": "microsoft-opc-plc-local",
                "asset_id": "SIM-OPCPLC-01",
                "read_only": True,
                "proxy_warning": "Simulator proxy evidence; not verified physical conveyor state.",
                "bridge_timestamp": received.isoformat(),
                "reason_code": reason_code,
                "error": error,
                "signals": stale_signals,
            }
            return dict(self._payload)


class JsonlRecorder:
    """Append complete immutable observation snapshots for deterministic replay."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _sample_json(
    sample: QualifiedSample, *, received_timestamp: datetime, observation_id: str
) -> dict[str, Any]:
    result = asdict(sample)
    result["signal"] = sample.signal.value
    result["source_timestamp"] = (
        sample.source_timestamp.isoformat() if sample.source_timestamp else None
    )
    result["received_timestamp"] = received_timestamp.isoformat()
    result["observation_id"] = observation_id
    return result


async def _runtime_node_id(client: Any, expanded_node_id: str) -> str:
    """Resolve an nsu-based simulator identifier without pinning a namespace index."""

    prefix = "nsu="
    marker = ";s="
    if not expanded_node_id.startswith(prefix) or marker not in expanded_node_id:
        raise ValueError("only declared nsu string node identifiers are supported")
    namespace_uri, identifier = expanded_node_id[len(prefix) :].split(marker, 1)
    namespace_index = await client.get_namespace_index(namespace_uri)
    return f"ns={namespace_index};s={identifier}"


async def poll_opcua(
    endpoint: str,
    snapshot: Snapshot,
    interval: float,
    recorder: JsonlRecorder | None = None,
) -> None:
    try:
        from asyncua import Client
        from asyncua.ua.uaerrors import UaError
    except ImportError as exc:
        raise SystemExit("Install the OPC UA extra: python -m pip install -e .[opcua]") from exc

    observation_sequence = 0
    while True:
        try:
            async with Client(url=endpoint) as client:
                runtime_ids = [
                    await _runtime_node_id(client, mapping.node_id)
                    for mapping in DEFAULT_MAPPINGS
                ]
                nodes = [client.get_node(node_id) for node_id in runtime_ids]
                while True:
                    received_timestamp = datetime.now(UTC)
                    values = await asyncio.gather(*(node.read_data_value() for node in nodes))
                    samples = [
                        qualify_value(mapping, value)
                        for mapping, value in zip(DEFAULT_MAPPINGS, values, strict=True)
                    ]
                    observation_sequence += 1
                    signal_map = {
                        sample.signal.value: _sample_json(
                            sample,
                            received_timestamp=received_timestamp,
                            observation_id=(
                                f"microsoft-opc-plc-local:{observation_sequence}:{sample.signal.value}"
                            ),
                        )
                        for sample in samples
                    }
                    rpm_sample = next(
                        sample for sample in samples if sample.signal is ProxySignal.RPM
                    )
                    if rpm_sample.quality == "good" and rpm_sample.value is not None:
                        signal_map["arrival_ms"] = {
                            "signal": "arrival_ms",
                            "value": conveyor_arrival_ms(rpm_sample.value),
                            "unit": "ms",
                            "source_timestamp": rpm_sample.source_timestamp.isoformat(),
                            "received_timestamp": received_timestamp.isoformat(),
                            "observation_id": (
                                f"microsoft-opc-plc-local:{observation_sequence}:arrival_ms"
                            ),
                            "status_code": rpm_sample.status_code,
                            "quality": "good",
                            "reason_code": "LINEALERT.MODEL.CONVEYOR_MOTION_DERIVED",
                            "node_id": "derived:conveyor-motion-v1",
                            "provenance": "derived_from:rpm",
                        }
                    all_good = all(sample.quality == "good" for sample in samples)
                    payload = {
                        "schema_version": "linealert.observation.snapshot.v1",
                        "connected": True,
                        "profile": "microsoft-opc-plc-proxy-v1",
                        "source_id": "microsoft-opc-plc-local",
                        "asset_id": "SIM-OPCPLC-01",
                        "read_only": True,
                        "proxy_warning": (
                            "Simulator proxy evidence; not verified physical conveyor state."
                        ),
                        "bridge_timestamp": received_timestamp.isoformat(),
                        "observation_sequence": observation_sequence,
                        "reason_code": (
                            "EVIDENCE.OPCUA_SAMPLE_QUALIFIED"
                            if all_good
                            else "EVIDENCE.OPCUA_SAMPLE_UNQUALIFIED"
                        ),
                        "signals": signal_map,
                    }
                    snapshot.replace(payload)
                    if recorder is not None:
                        recorder.append(payload)
                    await asyncio.sleep(interval)
        except (TimeoutError, OSError, ConnectionError, UaError) as exc:
            unavailable = snapshot.mark_unavailable(
                reason_code="EVIDENCE.OPCUA_CONNECTION_UNAVAILABLE",
                error=type(exc).__name__,
            )
            if recorder is not None:
                recorder.append(unavailable)
            await asyncio.sleep(2)


async def replay_jsonl(
    path: Path, snapshot: Snapshot, interval: float, *, loop: bool = False
) -> None:
    """Serve captured snapshots in file order without reinterpreting their evidence."""

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not records:
        raise ValueError("replay capture contains no observation snapshots")
    while True:
        for record in records:
            replayed = dict(record)
            replayed["transport"] = "deterministic-replay"
            replayed["replay_timestamp"] = datetime.now(UTC).isoformat()
            snapshot.replace(replayed)
            await asyncio.sleep(interval)
        if not loop:
            return


def handler_for(docs: Path, snapshot: Snapshot) -> type[SimpleHTTPRequestHandler]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(docs), **kwargs)

        def do_GET(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] != "/api/telemetry":
                return super().do_GET()
            body = json.dumps(snapshot.get(), separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="opc.tcp://localhost:50000")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--capture-jsonl", type=Path)
    parser.add_argument("--replay-jsonl", type=Path)
    parser.add_argument("--loop-replay", action="store_true")
    args = parser.parse_args()
    docs = Path(__file__).resolve().parents[2] / "docs"
    snapshot = Snapshot()
    recorder = JsonlRecorder(args.capture_jsonl) if args.capture_jsonl else None

    async def runtime() -> None:
        if args.replay_jsonl:
            await replay_jsonl(
                args.replay_jsonl, snapshot, args.poll_seconds, loop=args.loop_replay
            )
        else:
            await poll_opcua(args.endpoint, snapshot, args.poll_seconds, recorder)

    thread = threading.Thread(
        target=lambda: asyncio.run(runtime()),
        daemon=True,
    )
    thread.start()
    server = ThreadingHTTPServer((args.host, args.port), handler_for(docs, snapshot))
    print(f"LineAlert dashboard: http://{args.host}:{args.port}")
    if args.replay_jsonl:
        print(f"Deterministic replay: {args.replay_jsonl}")
    else:
        print(f"Read-only OPC UA endpoint: {args.endpoint}")
        if args.capture_jsonl:
            print(f"Capturing observation snapshots: {args.capture_jsonl}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
