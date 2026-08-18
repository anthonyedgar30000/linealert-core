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
            "connected": False,
            "profile": "microsoft-opc-plc-proxy-v1",
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


def _sample_json(sample: QualifiedSample) -> dict[str, Any]:
    result = asdict(sample)
    result["signal"] = sample.signal.value
    result["source_timestamp"] = (
        sample.source_timestamp.isoformat() if sample.source_timestamp else None
    )
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


async def poll_opcua(endpoint: str, snapshot: Snapshot, interval: float) -> None:
    try:
        from asyncua import Client
        from asyncua.ua.uaerrors import UaError
    except ImportError as exc:
        raise SystemExit("Install the OPC UA extra: python -m pip install -e .[opcua]") from exc

    while True:
        try:
            async with Client(url=endpoint) as client:
                runtime_ids = [
                    await _runtime_node_id(client, mapping.node_id)
                    for mapping in DEFAULT_MAPPINGS
                ]
                nodes = [client.get_node(node_id) for node_id in runtime_ids]
                while True:
                    values = await asyncio.gather(*(node.read_data_value() for node in nodes))
                    samples = [
                        qualify_value(mapping, value)
                        for mapping, value in zip(DEFAULT_MAPPINGS, values, strict=True)
                    ]
                    signal_map = {sample.signal.value: _sample_json(sample) for sample in samples}
                    rpm_sample = next(
                        sample for sample in samples if sample.signal is ProxySignal.RPM
                    )
                    if rpm_sample.quality == "good" and rpm_sample.value is not None:
                        signal_map["arrival_ms"] = {
                            "signal": "arrival_ms",
                            "value": conveyor_arrival_ms(rpm_sample.value),
                            "unit": "ms",
                            "source_timestamp": rpm_sample.source_timestamp.isoformat(),
                            "status_code": rpm_sample.status_code,
                            "quality": "good",
                            "reason_code": "LINEALERT.MODEL.CONVEYOR_MOTION_DERIVED",
                            "node_id": "derived:conveyor-motion-v1",
                            "provenance": "derived_from:rpm",
                        }
                    all_good = all(sample.quality == "good" for sample in samples)
                    snapshot.replace(
                        {
                            "connected": True,
                            "profile": "microsoft-opc-plc-proxy-v1",
                            "read_only": True,
                            "proxy_warning": (
                                "Simulator proxy evidence; not verified physical conveyor state."
                            ),
                            "bridge_timestamp": datetime.now(UTC).isoformat(),
                            "reason_code": (
                                "EVIDENCE.OPCUA_SAMPLE_QUALIFIED"
                                if all_good
                                else "EVIDENCE.OPCUA_SAMPLE_UNQUALIFIED"
                            ),
                            "signals": signal_map,
                        }
                    )
                    await asyncio.sleep(interval)
        except (OSError, asyncio.TimeoutError, ConnectionError, UaError) as exc:
            snapshot.replace(
                {
                    "connected": False,
                    "profile": "microsoft-opc-plc-proxy-v1",
                    "read_only": True,
                    "proxy_warning": "Simulator proxy evidence; not verified physical conveyor state.",
                    "reason_code": "EVIDENCE.OPCUA_CONNECTION_UNAVAILABLE",
                    "error": type(exc).__name__,
                    "signals": {},
                }
            )
            await asyncio.sleep(2)


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
    args = parser.parse_args()
    docs = Path(__file__).resolve().parents[2] / "docs"
    snapshot = Snapshot()
    thread = threading.Thread(
        target=lambda: asyncio.run(poll_opcua(args.endpoint, snapshot, args.poll_seconds)),
        daemon=True,
    )
    thread.start()
    server = ThreadingHTTPServer((args.host, args.port), handler_for(docs, snapshot))
    print(f"LineAlert dashboard: http://{args.host}:{args.port}")
    print(f"Read-only OPC UA endpoint: {args.endpoint}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
