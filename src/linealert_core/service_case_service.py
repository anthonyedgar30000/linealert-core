"""Loopback HTTP service for bounded local LineAlert service-case persistence."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .service_case import (
    ServiceCaseError,
    plant_reported_context_from_dict,
    service_case_from_dict,
)
from .service_case_store import (
    STORE_CLASSIFICATION,
    STORE_SCHEMA_VERSION,
    ServiceCaseConflictError,
    ServiceCaseNotFoundError,
    ServiceCaseStore,
    ServiceCaseStoreError,
    stored_service_case_to_dict,
)

MAX_REQUEST_BYTES = 64 * 1024


def default_data_dir() -> Path:
    explicit = os.environ.get("LINEALERT_SERVICE_CASE_DATA_DIR")
    if explicit:
        return Path(explicit)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "LineAlert" / "service-cases-v1"
    return Path.home() / ".linealert" / "service-cases-v1"


def seed_service_case(store: ServiceCaseStore, seed_path: Path) -> None:
    try:
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ServiceCaseStoreError("service-case seed is unreadable") from exc
    if not isinstance(raw, Mapping):
        raise ServiceCaseStoreError("service-case seed must be a JSON object")
    try:
        service_case = service_case_from_dict(raw)
    except ServiceCaseError as exc:
        raise ServiceCaseStoreError(str(exc)) from exc
    if service_case.plant_reported_context_ids:
        raise ServiceCaseStoreError(
            "service-case seed must not reference contexts that are not seeded"
        )
    store.seed_if_absent(service_case)


def _error_payload(
    *,
    reason_code: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "schema_version": "linealert.service-case-service-error.v1",
        "reason_code": reason_code,
        "detail": detail,
        "authorized_action": False,
        "equipment_effect": "none",
    }


def handler_for(store: ServiceCaseStore) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send_json(
            self,
            payload: Mapping[str, Any],
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

        def _read_json(self) -> Mapping[str, Any]:
            raw_length = self.headers.get("Content-Length")
            try:
                content_length = int(raw_length or "0")
            except ValueError as exc:
                raise ServiceCaseStoreError("Content-Length must be an integer") from exc
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                raise ServiceCaseStoreError(
                    f"request body must be between 1 and {MAX_REQUEST_BYTES} bytes"
                )
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ServiceCaseStoreError("request body must be valid UTF-8 JSON") from exc
            if not isinstance(payload, Mapping):
                raise ServiceCaseStoreError("request body must be a JSON object")
            return payload

        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            if request.path == "/api/status":
                try:
                    retained = store.count()
                    self._send_json(
                        {
                            "schema_version": "linealert.service-case-service-status.v1",
                            "connected": True,
                            "storage_available": True,
                            "persistence": STORE_CLASSIFICATION,
                            "store_schema_version": STORE_SCHEMA_VERSION,
                            "retained_service_case_count": retained,
                            "reason_code": "SERVICE_CASE.LOCAL_STORE_AVAILABLE",
                            "production_record_authority": False,
                            "equipment_authority": False,
                        }
                    )
                except ServiceCaseStoreError as exc:
                    self._send_json(
                        _error_payload(
                            reason_code="SERVICE_CASE.LOCAL_STORE_UNAVAILABLE",
                            detail=str(exc),
                        ),
                        status_code=503,
                    )
                return

            prefix = "/api/service-cases/"
            if request.path.startswith(prefix):
                service_case_id = unquote(request.path[len(prefix) :])
                if not service_case_id or "/" in service_case_id:
                    self._send_json(
                        _error_payload(
                            reason_code="SERVICE_CASE.INVALID_ID",
                            detail="service_case_id is required",
                        ),
                        status_code=400,
                    )
                    return
                try:
                    self._send_json(
                        stored_service_case_to_dict(store.get(service_case_id))
                    )
                except ServiceCaseNotFoundError:
                    self._send_json(
                        _error_payload(
                            reason_code="SERVICE_CASE.NOT_FOUND",
                            detail="service case is not retained in the local store",
                        ),
                        status_code=404,
                    )
                except ServiceCaseStoreError as exc:
                    self._send_json(
                        _error_payload(
                            reason_code="SERVICE_CASE.LOCAL_STORE_UNAVAILABLE",
                            detail=str(exc),
                        ),
                        status_code=503,
                    )
                return

            self._send_json(
                _error_payload(
                    reason_code="SERVICE_CASE.ROUTE_NOT_FOUND",
                    detail="route not found",
                ),
                status_code=404,
            )
        def do_POST(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            try:
                payload = self._read_json()
                if request.path == "/api/service-cases":
                    try:
                        service_case = service_case_from_dict(payload)
                    except ServiceCaseError as exc:
                        raise ServiceCaseStoreError(str(exc)) from exc
                    created = store.create(service_case)
                    self._send_json(
                        stored_service_case_to_dict(created),
                        status_code=201,
                    )
                    return

                prefix = "/api/service-cases/"
                suffix = "/plant-context"
                if request.path.startswith(prefix) and request.path.endswith(suffix):
                    encoded_id = request.path[len(prefix) : -len(suffix)].rstrip("/")
                    service_case_id = unquote(encoded_id)
                    if not service_case_id or "/" in service_case_id:
                        raise ServiceCaseStoreError("service_case_id is invalid")
                    try:
                        context = plant_reported_context_from_dict(payload)
                    except ServiceCaseError as exc:
                        raise ServiceCaseStoreError(str(exc)) from exc
                    if context.service_case_id != service_case_id:
                        raise ServiceCaseStoreError(
                            "plant context service_case_id must match request path"
                        )
                    updated = store.append_plant_context(service_case_id, context)
                    self._send_json(
                        stored_service_case_to_dict(updated),
                        status_code=201,
                    )
                    return

                self._send_json(
                    _error_payload(
                        reason_code="SERVICE_CASE.ROUTE_NOT_FOUND",
                        detail="route not found",
                    ),
                    status_code=404,
                )
            except ServiceCaseConflictError as exc:
                self._send_json(
                    _error_payload(
                        reason_code="SERVICE_CASE.IDENTITY_CONFLICT",
                        detail=str(exc),
                    ),
                    status_code=409,
                )
            except ServiceCaseNotFoundError:
                self._send_json(
                    _error_payload(
                        reason_code="SERVICE_CASE.NOT_FOUND",
                        detail="service case is not retained in the local store",
                    ),
                    status_code=404,
                )
            except ServiceCaseStoreError as exc:
                self._send_json(
                    _error_payload(
                        reason_code="SERVICE_CASE.INVALID_REQUEST",
                        detail=str(exc),
                    ),
                    status_code=400,
                )

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local LineAlert service-case persistence service."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--seed-service-case", type=Path)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    store = ServiceCaseStore(args.data_dir)
    if args.seed_service_case is not None:
        seed_service_case(store, args.seed_service_case)

    server = ThreadingHTTPServer(
        (args.host, args.port),
        handler_for(store),
    )
    print(f"LineAlert service-case store: http://{args.host}:{args.port}")
    print(f"Local persistence: {store.data_dir}")
    print("Boundary: local persistence != production CMMS/service record")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
