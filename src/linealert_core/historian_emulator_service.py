"""HTTP service for deterministic live LineAlert historian emulation."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .historian_emulator import (
    ASSET_ID,
    PERSISTENCE,
    PROFILE_ID,
    SOURCE_ID,
    SOURCE_MODE,
    EmulatedHistorianStore,
    HistorianEmulatorError,
)

STATUS_SCHEMA = "linealert.historian-service-status.v1"


class EmulatorRuntimeState:
    """Thread-safe stream health separate from retained-history availability."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._source_available = False
        self._reason_code = "EVIDENCE.EMULATED_HISTORIAN_STARTING"
        self._error: str | None = None
        self._updated_at = datetime.now(UTC)

    def mark_success(self) -> None:
        with self._lock:
            self._source_available = True
            self._reason_code = "EVIDENCE.EMULATED_HISTORIAN_STREAMING"
            self._error = None
            self._updated_at = datetime.now(UTC)

    def mark_failure(self, error: Exception) -> None:
        with self._lock:
            self._source_available = False
            self._reason_code = "EVIDENCE.EMULATED_HISTORIAN_SOURCE_UNAVAILABLE"
            self._error = type(error).__name__
            self._updated_at = datetime.now(UTC)

    def get(self) -> dict[str, Any]:
        with self._lock:
            return {
                "source_available": self._source_available,
                "reason_code": self._reason_code,
                "error": self._error,
                "updated_at": self._updated_at.isoformat(),
            }


def default_database_path() -> Path:
    explicit = os.environ.get("LINEALERT_EMULATED_HISTORIAN_DB")
    if explicit:
        return Path(explicit)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return (
            Path(local_app_data)
            / "LineAlert"
            / "historian-emulator-v1"
            / "historian.sqlite3"
        )
    return Path.home() / ".linealert" / "historian-emulator-v1" / "historian.sqlite3"


def _parse_time(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not value.strip():
        raise HistorianEmulatorError(f"{field_name} must not be empty")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HistorianEmulatorError(f"{field_name} must be ISO 8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HistorianEmulatorError(f"{field_name} must be timezone-aware")
    return parsed


def _query_text(query: dict[str, list[str]], name: str) -> str | None:
    value = query.get(name, [None])[0]
    if value is None or not value.strip():
        return None
    return value


def _query_limit(query: dict[str, list[str]], *, default: int = 240) -> int:
    raw = query.get("limit", [str(default)])[0]
    try:
        return int(raw)
    except ValueError as exc:
        raise HistorianEmulatorError("limit must be an integer") from exc


def status_payload(
    store: EmulatedHistorianStore,
    runtime_state: EmulatorRuntimeState,
    *,
    interval_seconds: float,
    started_at: datetime,
) -> dict[str, Any]:
    latest = store.latest_cycle()
    runtime = runtime_state.get()
    return {
        "schema_version": STATUS_SCHEMA,
        "connected": True,
        "source_available": runtime["source_available"],
        "reason_code": runtime["reason_code"],
        "updated_at": runtime["updated_at"],
        "error": runtime["error"],
        "historian_backend": "sqlite_emulator",
        "persistence": PERSISTENCE,
        "source_mode": SOURCE_MODE,
        "source_classification": "controlled_synthetic_demo",
        "emulated": True,
        "asset_id": ASSET_ID,
        "profile_id": PROFILE_ID,
        "source_id": SOURCE_ID,
        "record_interval_seconds": interval_seconds,
        "retained_cycle_count": store.retained_cycle_count(),
        "latest_cycle_id": latest["cycle_id"] if latest else None,
        "latest_scenario_phase": latest["scenario_phase"] if latest else None,
        "latest_observed_at": latest["observed_at"] if latest else None,
        "service_started_at": started_at.isoformat(),
        "physical_state_authority": False,
        "production_authority": False,
    }


def _unavailable_capability(
    *,
    schema_version: str,
    reason_code: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "disposition": "UNAVAILABLE",
        "reason_code": reason_code,
        "detail": detail,
        "emulated": True,
        "physical_state_authority": False,
        "production_authority": False,
    }


def handler_for(
    store: EmulatedHistorianStore,
    runtime_state: EmulatorRuntimeState,
    *,
    interval_seconds: float,
    started_at: datetime,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send_json(
            self,
            payload: dict[str, Any],
            *,
            status_code: int = 200,
        ) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            query = parse_qs(request.query)
            try:
                if request.path == "/api/status":
                    self._send_json(
                        status_payload(
                            store,
                            runtime_state,
                            interval_seconds=interval_seconds,
                            started_at=started_at,
                        )
                    )
                    return

                if request.path == "/api/history/functional-temporal":
                    self._send_json(
                        store.functional_temporal_history(
                            limit=_query_limit(query),
                            asset_id=_query_text(query, "asset_id"),
                            episode_id=_query_text(query, "episode_id"),
                            cycle_id=_query_text(query, "cycle_id"),
                            phase_id=_query_text(query, "phase_id"),
                            record_kind=_query_text(query, "record_kind"),
                            from_time=_parse_time(
                                _query_text(query, "from_time"),
                                "from_time",
                            ),
                            to_time=_parse_time(
                                _query_text(query, "to_time"),
                                "to_time",
                            ),
                        )
                    )
                    return

                if request.path == "/api/history/conditions":
                    self._send_json(
                        store.condition_history(
                            limit=_query_limit(query),
                            asset_id=_query_text(query, "asset_id"),
                            relationship_id=_query_text(query, "relationship_id"),
                            episode_id=_query_text(query, "episode_id"),
                            cycle_id=_query_text(query, "cycle_id"),
                            phase_id=_query_text(query, "phase_id"),
                            from_time=_parse_time(
                                _query_text(query, "from_time"),
                                "from_time",
                            ),
                            to_time=_parse_time(
                                _query_text(query, "to_time"),
                                "to_time",
                            ),
                        )
                    )
                    return

                if request.path == "/api/history/observations":
                    self._send_json(
                        store.observation_history(
                            limit=_query_limit(query),
                            asset_id=_query_text(query, "asset_id"),
                        )
                    )
                    return
                episode_prefix = "/api/history/episodes/"
                if request.path.startswith(episode_prefix):
                    episode_id = unquote(request.path[len(episode_prefix) :])
                    self._send_json(
                        store.episode(
                            episode_id,
                            limit=_query_limit(query, default=1000),
                        )
                    )
                    return

                if request.path == "/api/history/conditions/localize":
                    self._send_json(
                        _unavailable_capability(
                            schema_version=(
                                "linealert.configured-condition-localization.v1"
                            ),
                            reason_code=(
                                "EVIDENCE.EMULATED_LOCALIZATION_NOT_IMPLEMENTED"
                            ),
                            detail=(
                                "Live emulation currently exposes retained synthetic "
                                "condition evidence but does not claim configured-policy "
                                "localization equivalence with Timescale history."
                            ),
                        ),
                        status_code=503,
                    )
                    return

                if request.path == "/api/history/functional-temporal/compare":
                    self._send_json(
                        _unavailable_capability(
                            schema_version=(
                                "linealert.functional-temporal-selected-comparison.v1"
                            ),
                            reason_code=(
                                "EVIDENCE.EMULATED_COMPARISON_NOT_IMPLEMENTED"
                            ),
                            detail=(
                                "The emulated historian does not yet expose the governed "
                                "reference-versus-selected comparison endpoint."
                            ),
                        ),
                        status_code=503,
                    )
                    return

                self._send_json(
                    {
                        "error": "not found",
                        "emulated": True,
                    },
                    status_code=404,
                )
            except HistorianEmulatorError as exc:
                self._send_json(
                    {
                        "schema_version": "linealert.historian-emulator-error.v1",
                        "reason_code": "EVIDENCE.EMULATED_HISTORIAN_QUERY_REFUSED",
                        "detail": str(exc),
                        "emulated": True,
                        "physical_state_authority": False,
                    },
                    status_code=400,
                )

        def do_POST(self) -> None:  # noqa: N802
            self._send_json(
                {
                    "schema_version": "linealert.historian-emulator-write-refusal.v1",
                    "accepted": False,
                    "reason_code": "AUTHORITY.EMULATED_HISTORIAN_HTTP_READ_ONLY",
                    "detail": (
                        "The live historian emulator generates its own synthetic evidence "
                        "and does not accept external historian writes."
                    ),
                    "emulated": True,
                    "equipment_effect": "none",
                    "authorized_action": False,
                },
                status_code=405,
            )

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def run_generator(
    store: EmulatedHistorianStore,
    runtime_state: EmulatorRuntimeState,
    *,
    interval_seconds: float,
    stop_event: threading.Event,
) -> None:
    while not stop_event.wait(interval_seconds):
        try:
            store.append_next_cycle()
            runtime_state.mark_success()
        except HistorianEmulatorError as exc:
            runtime_state.mark_failure(exc)
            # Query status remains available from retained evidence. A later
            # successful cycle may resume streaming without inventing data.
            time.sleep(min(interval_seconds, 1.0))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic local LineAlert historian emulation."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--database", type=Path, default=default_database_path())
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("examples/labeler_demo_config.json"),
    )
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--seed-cycles", type=int, default=36)
    parser.add_argument("--retention-cycles", type=int, default=1800)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.interval_seconds <= 0:
        raise SystemExit("--interval-seconds must be positive")
    if args.seed_cycles < 0:
        raise SystemExit("--seed-cycles must be non-negative")

    store = EmulatedHistorianStore(
        args.database,
        config_path=args.config,
        retention_cycles=args.retention_cycles,
    )
    store.seed_window(
        cycles=args.seed_cycles,
        interval_seconds=args.interval_seconds,
    )
    store.append_next_cycle()

    started_at = datetime.now(UTC)
    runtime_state = EmulatorRuntimeState()
    runtime_state.mark_success()
    stop_event = threading.Event()
    generator = threading.Thread(
        target=run_generator,
        args=(store, runtime_state),
        kwargs={
            "interval_seconds": args.interval_seconds,
            "stop_event": stop_event,
        },
        daemon=True,
    )
    generator.start()

    server = ThreadingHTTPServer(
        (args.host, args.port),
        handler_for(
            store,
            runtime_state,
            interval_seconds=args.interval_seconds,
            started_at=started_at,
        ),
    )
    print(f"LineAlert emulated historian: http://{args.host}:{args.port}")
    print(f"SQLite retention: {store.database_path}")
    print(
        "Boundary: live emulated historian != TimescaleDB != verified physical history"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.shutdown()
        generator.join(timeout=max(args.interval_seconds * 2, 2.0))
        store.close()


if __name__ == "__main__":
    main()
