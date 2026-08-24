"""Local read-only OPC UA to LineAlert dashboard bridge."""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
from collections import deque
from dataclasses import asdict
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .condition_runtime import ConditionRuntimeSnapshot, replay_condition_events
from .evidence_hierarchy import evaluate_claim_evidence, load_evidence_hierarchy_profile
from .opcua_adapter import (
    DEFAULT_MAPPINGS,
    ProxySignal,
    QualifiedSample,
    conveyor_arrival_ms,
    qualify_value,
)
from .operating_mode import (
    enforce_operating_mode,
    evaluate_operating_mode,
    load_operating_mode_profile,
)
from .semantic_admission import evaluate_semantic_admission, load_semantic_binding_profile


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
                    observed = (
                        datetime.fromisoformat(source_timestamp) if source_timestamp else None
                    )
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


class ObservationHistory:
    """Thread-safe recent observation history for condition-monitoring clients."""

    def __init__(self, maxlen: int = 7200, *, persistence: str = "memory_only") -> None:
        if maxlen < 1:
            raise ValueError("history maxlen must be at least 1")
        self._lock = threading.Lock()
        self._records: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._maxlen = maxlen
        self.persistence = persistence

    def append(self, payload: dict[str, Any]) -> None:
        immutable_copy = json.loads(json.dumps(payload))
        with self._lock:
            self._records.append(immutable_copy)

    def get(self, *, limit: int = 240) -> dict[str, Any]:
        bounded_limit = max(1, min(limit, self._maxlen))
        with self._lock:
            observations = list(self._records)[-bounded_limit:]
        return {
            "schema_version": "linealert.observation.history.v1",
            "persistence": self.persistence,
            "count": len(observations),
            "observations": observations,
        }


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


def evaluate_proxy_claims(
    payload: dict[str, Any], hierarchy_profile: dict[str, Any]
) -> dict[str, Any]:
    """Assess one admitted proxy against simulator and physical claims separately."""

    rpm = payload.get("signals", {}).get("rpm", {})
    decision = payload.get("semantic_admission", {}).get("signals", {}).get("rpm", {})
    observation = {
        "observation_id": rpm.get("observation_id"),
        "category": "controller_internal_state",
        "supported_claims": ["simulator.motor_speed_proxy", "physical.motor_speed"],
        "supports": True,
        "failure_domain": "microsoft-opc-plc-simulator",
        "scope": decision.get("scope"),
        "semantic_admitted": decision.get("admitted", False),
        "quality": rpm.get("quality"),
        "fresh": decision.get("admitted", False),
        "binding_verified": decision.get("admitted", False),
    }
    return {
        "schema_version": "linealert.claim-evidence-set.v1",
        "assessments": {
            claim_id: evaluate_claim_evidence(
                claim_id=claim_id,
                observations=[observation],
                profile=hierarchy_profile,
            )
            for claim_id in ("simulator.motor_speed_proxy", "physical.motor_speed")
        },
        "authorized_action": False,
    }


async def poll_opcua(
    endpoint: str,
    snapshot: Snapshot,
    interval: float,
    recorder: JsonlRecorder | None = None,
    history: ObservationHistory | None = None,
    *,
    operating_mode: str = "demo_emulation",
) -> None:
    try:
        from asyncua import Client
        from asyncua.ua.uaerrors import UaError
    except ImportError as exc:
        raise SystemExit("Install the OPC UA extra: python -m pip install -e .[opcua]") from exc

    semantic_profile = load_semantic_binding_profile(
        Path(__file__).resolve().parents[2]
        / "profiles"
        / "microsoft-opc-plc-proxy-v1.semantic-bindings.json"
    )
    hierarchy_profile = load_evidence_hierarchy_profile(
        Path(__file__).resolve().parents[2] / "profiles" / "evidence-hierarchy-v1.json"
    )
    operating_mode_profile = load_operating_mode_profile(
        Path(__file__).resolve().parents[2] / "profiles" / "operating-modes-v1.json"
    )
    observation_sequence = 0
    while True:
        try:
            async with Client(url=endpoint) as client:
                runtime_ids = [
                    await _runtime_node_id(client, mapping.node_id) for mapping in DEFAULT_MAPPINGS
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
                                f"microsoft-opc-plc-local:{observation_sequence}:"
                                f"{sample.signal.value}"
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
                        "source_kind": "simulator",
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
                    payload["semantic_admission"] = evaluate_semantic_admission(
                        payload, semantic_profile, now=received_timestamp
                    )
                    mode_assessment = evaluate_operating_mode(
                        configured_mode=operating_mode,
                        source_kinds=[payload["source_kind"]],
                        profile=operating_mode_profile,
                    )
                    enforce_operating_mode(payload, mode_assessment)
                    payload["claim_evidence"] = evaluate_proxy_claims(
                        payload, hierarchy_profile
                    )
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
            await asyncio.sleep(2)


async def replay_jsonl(
    path: Path,
    snapshot: Snapshot,
    interval: float,
    history: ObservationHistory | None = None,
    *,
    loop: bool = False,
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
            if history is not None:
                history.append(replayed)
            await asyncio.sleep(interval)
        if not loop:
            return


def handler_for(
    docs: Path,
    snapshot: Snapshot,
    history: ObservationHistory | None = None,
    condition: ConditionRuntimeSnapshot | None = None,
) -> type[SimpleHTTPRequestHandler]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(docs), **kwargs)

        def _send_json(self, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if request.path == "/api/telemetry":
                self._send_json(snapshot.get())
                return
            if request.path == "/api/history":
                query = parse_qs(request.query)
                try:
                    limit = int(query.get("limit", ["240"])[0])
                except ValueError:
                    limit = 240
                payload = (
                    history.get(limit=limit)
                    if history is not None
                    else {
                        "schema_version": "linealert.observation.history.v1",
                        "persistence": "unavailable",
                        "count": 0,
                        "observations": [],
                    }
                )
                self._send_json(payload)
                return
            if request.path == "/api/condition":
                payload = (
                    condition.get()
                    if condition is not None
                    else ConditionRuntimeSnapshot().get()
                )
                self._send_json(payload)
                return
            return super().do_GET()

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
    parser.add_argument("--condition-events-jsonl", type=Path)
    parser.add_argument("--condition-config", type=Path)
    parser.add_argument("--condition-bindings", type=Path)
    parser.add_argument(
        "--condition-replay-seconds",
        type=float,
        default=0.1,
        help="Delay between deterministic condition-event replay envelopes.",
    )
    parser.add_argument(
        "--condition-clock-quality",
        choices=("synchronized", "degraded", "unsynchronized", "unknown"),
        default="synchronized",
        help="Transport clock evidence declared by the deterministic condition replay.",
    )
    parser.add_argument(
        "--history-size",
        type=int,
        default=7200,
        help="Recent snapshots retained for the dashboard history API.",
    )
    parser.add_argument(
        "--operating-mode",
        choices=("demo_emulation", "physical_commissioning", "physical_operational"),
        default="demo_emulation",
        help="Explicit evidence-source mode; physical modes refuse this simulator bridge.",
    )
    args = parser.parse_args()

    condition_paths = (
        args.condition_events_jsonl,
        args.condition_config,
        args.condition_bindings,
    )
    condition_requested = any(path is not None for path in condition_paths)
    if condition_requested and not all(path is not None for path in condition_paths):
        parser.error(
            "--condition-events-jsonl, --condition-config, and --condition-bindings "
            "must be supplied together"
        )

    docs = Path(__file__).resolve().parents[2] / "docs"
    snapshot = Snapshot()
    recorder = JsonlRecorder(args.capture_jsonl) if args.capture_jsonl else None
    if args.replay_jsonl:
        history_persistence = "deterministic_replay"
    elif recorder is not None:
        history_persistence = "jsonl_capture"
    else:
        history_persistence = "memory_only"
    history = ObservationHistory(args.history_size, persistence=history_persistence)
    condition_snapshot = ConditionRuntimeSnapshot()

    async def runtime() -> None:
        if args.replay_jsonl:
            await replay_jsonl(
                args.replay_jsonl,
                snapshot,
                args.poll_seconds,
                history,
                loop=args.loop_replay,
            )
        else:
            await poll_opcua(
                args.endpoint,
                snapshot,
                args.poll_seconds,
                recorder,
                history,
                operating_mode=args.operating_mode,
            )

    thread = threading.Thread(
        target=lambda: asyncio.run(runtime()),
        daemon=True,
    )
    thread.start()

    if condition_requested:
        condition_events = args.condition_events_jsonl
        condition_config = args.condition_config
        condition_bindings = args.condition_bindings
        if condition_events is None or condition_config is None or condition_bindings is None:
            raise AssertionError("condition replay paths passed parser validation")

        async def condition_runtime() -> None:
            await replay_condition_events(
                condition_events,
                condition_config,
                condition_bindings,
                condition_snapshot,
                interval_seconds=args.condition_replay_seconds,
                clock_quality=args.condition_clock_quality,
            )

        condition_thread = threading.Thread(
            target=lambda: asyncio.run(condition_runtime()),
            daemon=True,
        )
        condition_thread.start()

    server = ThreadingHTTPServer(
        (args.host, args.port),
        handler_for(docs, snapshot, history, condition_snapshot),
    )
    print(f"LineAlert dashboard: http://{args.host}:{args.port}")
    print(
        f"Recent history API: http://{args.host}:{args.port}/api/history "
        f"({args.history_size} snapshots · {history_persistence})"
    )
    print(f"Condition API: http://{args.host}:{args.port}/api/condition")
    if condition_requested:
        print(f"Condition event replay: {args.condition_events_jsonl}")
    if args.replay_jsonl:
        print(f"Deterministic replay: {args.replay_jsonl}")
    else:
        print(f"Read-only OPC UA endpoint: {args.endpoint}")
        print(f"Operating mode: {args.operating_mode}")
        if args.capture_jsonl:
            print(f"Capturing observation snapshots: {args.capture_jsonl}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
