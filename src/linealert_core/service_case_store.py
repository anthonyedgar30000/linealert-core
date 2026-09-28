"""Atomic local persistence for bounded LineAlert service-case records."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from .service_case import (
    PlantReportedContext,
    ServiceCase,
    ServiceCaseError,
    plant_reported_context_from_dict,
    plant_reported_context_to_dict,
    service_case_from_dict,
    service_case_to_dict,
    validate_plant_reported_context_binding,
)

STORE_SCHEMA_VERSION = "linealert.service-case-store.v1"
STORE_CLASSIFICATION = "local_atomic_json_single_process_v1"


class ServiceCaseStoreError(RuntimeError):
    """Base error for local service-case persistence."""


class ServiceCaseNotFoundError(ServiceCaseStoreError):
    """Raised when a service case is not present in the local store."""


class ServiceCaseConflictError(ServiceCaseStoreError):
    """Raised when a create or append would duplicate retained identity."""


@dataclass(frozen=True, slots=True)
class StoredServiceCase:
    service_case: ServiceCase
    plant_reported_contexts: tuple[PlantReportedContext, ...]
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ServiceCaseStoreError("updated_at must be timezone-aware")
        _validate_bundle(self.service_case, self.plant_reported_contexts)


def _validate_bundle(
    service_case: ServiceCase,
    contexts: Sequence[PlantReportedContext],
) -> None:
    ids = tuple(context.context_id for context in contexts)
    if len(ids) != len(set(ids)):
        raise ServiceCaseStoreError("plant-reported context IDs must be unique")
    if set(ids) != set(service_case.plant_reported_context_ids):
        raise ServiceCaseStoreError(
            "stored plant context IDs must exactly match service-case references"
        )
    for context in contexts:
        try:
            validate_plant_reported_context_binding(service_case, context)
        except ServiceCaseError as exc:
            raise ServiceCaseStoreError(str(exc)) from exc


def stored_service_case_to_dict(value: StoredServiceCase) -> dict[str, Any]:
    return {
        "schema_version": STORE_SCHEMA_VERSION,
        "persistence": STORE_CLASSIFICATION,
        "updated_at": value.updated_at.isoformat(),
        "service_case": service_case_to_dict(value.service_case),
        "plant_reported_contexts": [
            plant_reported_context_to_dict(context)
            for context in value.plant_reported_contexts
        ],
        "authority": {
            "production_record": False,
            "direct_cmms_record": False,
            "equipment_authority": False,
            "return_to_service_authority": False,
        },
    }


def stored_service_case_from_dict(payload: Mapping[str, Any]) -> StoredServiceCase:
    if payload.get("schema_version") != STORE_SCHEMA_VERSION:
        raise ServiceCaseStoreError(
            f"schema_version must be {STORE_SCHEMA_VERSION}"
        )
    raw_case = payload.get("service_case")
    raw_contexts = payload.get("plant_reported_contexts")
    updated_at_raw = payload.get("updated_at")
    if not isinstance(raw_case, Mapping):
        raise ServiceCaseStoreError("service_case must be an object")
    if not isinstance(raw_contexts, Sequence) or isinstance(
        raw_contexts,
        (str, bytes),
    ):
        raise ServiceCaseStoreError("plant_reported_contexts must be an array")
    if not isinstance(updated_at_raw, str):
        raise ServiceCaseStoreError("updated_at must be an ISO 8601 string")
    try:
        updated_at = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ServiceCaseStoreError("updated_at must be ISO 8601") from exc
    if updated_at.tzinfo is None or updated_at.utcoffset() is None:
        raise ServiceCaseStoreError("updated_at must be timezone-aware")
    try:
        service_case = service_case_from_dict(raw_case)
        contexts = tuple(
            plant_reported_context_from_dict(item)
            for item in raw_contexts
            if isinstance(item, Mapping)
        )
    except ServiceCaseError as exc:
        raise ServiceCaseStoreError(str(exc)) from exc
    if len(contexts) != len(raw_contexts):
        raise ServiceCaseStoreError(
            "plant_reported_contexts entries must be objects"
        )
    return StoredServiceCase(
        service_case=service_case,
        plant_reported_contexts=contexts,
        updated_at=updated_at,
    )
class ServiceCaseStore:
    """Single-process local JSON store with atomic replace writes."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def _path_for(self, service_case_id: str) -> Path:
        identity = service_case_id.strip()
        if not identity:
            raise ServiceCaseStoreError("service_case_id must not be empty")
        digest = sha256(identity.encode("utf-8")).hexdigest()
        return self._data_dir / f"{digest}.json"

    def _read_unlocked(self, service_case_id: str) -> StoredServiceCase:
        path = self._path_for(service_case_id)
        if not path.exists():
            raise ServiceCaseNotFoundError(service_case_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ServiceCaseStoreError(
                f"stored service case is unreadable: {service_case_id}"
            ) from exc
        if not isinstance(raw, Mapping):
            raise ServiceCaseStoreError("stored service case must be a JSON object")
        bundle = stored_service_case_from_dict(raw)
        if bundle.service_case.service_case_id != service_case_id:
            raise ServiceCaseStoreError(
                "stored service_case_id does not match requested identity"
            )
        return bundle

    def get(self, service_case_id: str) -> StoredServiceCase:
        with self._lock:
            return self._read_unlocked(service_case_id)

    def create(
        self,
        service_case: ServiceCase,
        *,
        contexts: Sequence[PlantReportedContext] = (),
    ) -> StoredServiceCase:
        with self._lock:
            path = self._path_for(service_case.service_case_id)
            if path.exists():
                raise ServiceCaseConflictError(service_case.service_case_id)
            bundle = StoredServiceCase(
                service_case=service_case,
                plant_reported_contexts=tuple(contexts),
                updated_at=datetime.now(UTC),
            )
            self._write_unlocked(path, bundle)
            return bundle

    def seed_if_absent(self, service_case: ServiceCase) -> StoredServiceCase:
        with self._lock:
            try:
                return self._read_unlocked(service_case.service_case_id)
            except ServiceCaseNotFoundError:
                return self.create(service_case)

    def append_plant_context(
        self,
        service_case_id: str,
        context: PlantReportedContext,
    ) -> StoredServiceCase:
        with self._lock:
            current = self._read_unlocked(service_case_id)
            if context.context_id in current.service_case.plant_reported_context_ids:
                raise ServiceCaseConflictError(context.context_id)
            updated_case = replace(
                current.service_case,
                plant_reported_context_ids=(
                    *current.service_case.plant_reported_context_ids,
                    context.context_id,
                ),
            )
            try:
                validate_plant_reported_context_binding(updated_case, context)
            except ServiceCaseError as exc:
                raise ServiceCaseStoreError(str(exc)) from exc
            updated = StoredServiceCase(
                service_case=updated_case,
                plant_reported_contexts=(
                    *current.plant_reported_contexts,
                    context,
                ),
                updated_at=datetime.now(UTC),
            )
            self._write_unlocked(self._path_for(service_case_id), updated)
            return updated

    def count(self) -> int:
        with self._lock:
            count = 0
            for path in self._data_dir.glob("*.json"):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, Mapping):
                        stored_service_case_from_dict(raw)
                        count += 1
                except (OSError, json.JSONDecodeError, ServiceCaseStoreError):
                    continue
            return count

    def _write_unlocked(
        self,
        path: Path,
        bundle: StoredServiceCase,
    ) -> None:
        payload = stored_service_case_to_dict(bundle)
        serialized = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ) + "\n"
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self._data_dir,
                prefix=".service-case-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)
            os.replace(temp_path, path)
        except OSError as exc:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise ServiceCaseStoreError("atomic local persistence failed") from exc
