from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from linealert_core.service_case import (
    PlantReportedContext,
    ServiceCase,
    ServiceCaseError,
    plant_reported_context_from_dict,
    service_case_from_dict,
)
from linealert_core.service_case_service import handler_for, seed_service_case
from linealert_core.service_case_store import (
    ServiceCaseConflictError,
    ServiceCaseStore,
    ServiceCaseStoreError,
    stored_service_case_to_dict,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED = PROJECT_ROOT / "examples" / "speedway_service_case_workspace_seed_v1.json"


def _seed_case() -> ServiceCase:
    payload = json.loads(SEED.read_text(encoding="utf-8"))
    return service_case_from_dict(payload)


def _context_payload(
    *,
    context_id: str = "plant-context-test-001",
    service_case_id: str = "svc-2026-0042",
    asset_id: str = "LABELER-02",
) -> dict[str, object]:
    return {
        "schema_version": "linealert.plant-reported-context.v1",
        "context_id": context_id,
        "service_case_id": service_case_id,
        "asset_id": asset_id,
        "entered_at": "2026-09-28T22:45:00+00:00",
        "entered_by": "speedway-technician-local",
        "reported_source_class": "cmms",
        "reported_source": "Plant CMMS",
        "original_wording_or_bounded_summary": (
            "Guide rail adjusted after intermittent bottle backup."
        ),
        "source_verification_state": "technician_viewed_source",
        "reported_time_kind": "window",
        "reported_clock_quality": "unknown",
        "reported_event_start": "2026-09-27T13:40:00+00:00",
        "reported_event_end": "2026-09-27T14:20:00+00:00",
        "source_record_reference": "WO-1842",
        "plant_contact_role": "Plant maintenance",
        "provenance": [
            "speedway-service-workspace:manual-entry",
            "plant-maintenance-contact",
        ],
        "direct_system_observation": False,
        "verified_source_record": False,
        "causal_claim_established": False,
    }


def _context(**overrides: object) -> PlantReportedContext:
    payload = _context_payload()
    payload.update(overrides)
    return plant_reported_context_from_dict(payload)

def test_store_persists_service_case_across_reopen(tmp_path: Path) -> None:
    store = ServiceCaseStore(tmp_path)
    created = store.create(_seed_case())

    reopened = ServiceCaseStore(tmp_path).get("svc-2026-0042")

    assert reopened.service_case == created.service_case
    assert reopened.plant_reported_contexts == ()
    payload = stored_service_case_to_dict(reopened)
    assert payload["persistence"] == "local_atomic_json_single_process_v1"
    authority = payload["authority"]
    assert authority["production_record"] is False
    assert authority["direct_cmms_record"] is False
    assert authority["equipment_authority"] is False


def test_store_appends_context_and_updates_case_binding_atomically(
    tmp_path: Path,
) -> None:
    store = ServiceCaseStore(tmp_path)
    store.create(_seed_case())

    updated = store.append_plant_context("svc-2026-0042", _context())
    reopened = ServiceCaseStore(tmp_path).get("svc-2026-0042")

    assert updated.service_case.plant_reported_context_ids == (
        "plant-context-test-001",
    )
    assert reopened.service_case.plant_reported_context_ids == (
        "plant-context-test-001",
    )
    assert len(reopened.plant_reported_contexts) == 1
    assert reopened.plant_reported_contexts[0].reported_source == "Plant CMMS"


def test_store_refuses_duplicate_context_identity(tmp_path: Path) -> None:
    store = ServiceCaseStore(tmp_path)
    store.create(_seed_case())
    store.append_plant_context("svc-2026-0042", _context())

    with pytest.raises(ServiceCaseConflictError, match="plant-context-test-001"):
        store.append_plant_context("svc-2026-0042", _context())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("service_case_id", "svc-other", "service_case_id must match"),
        ("asset_id", "FILLER-01", "asset_id must match"),
    ],
)
def test_store_refuses_cross_identity_context(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    store = ServiceCaseStore(tmp_path)
    store.create(_seed_case())
    context = _context(**{field: value})

    with pytest.raises(ServiceCaseStoreError, match=message):
        store.append_plant_context("svc-2026-0042", context)


def test_store_fails_closed_on_corrupt_retained_record(tmp_path: Path) -> None:
    store = ServiceCaseStore(tmp_path)
    store.create(_seed_case())
    retained = next(tmp_path.glob("*.json"))
    retained.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ServiceCaseStoreError, match="unreadable"):
        store.get("svc-2026-0042")


def test_seed_is_idempotent_and_does_not_overwrite_context(tmp_path: Path) -> None:
    store = ServiceCaseStore(tmp_path)
    seed_service_case(store, SEED)
    store.append_plant_context("svc-2026-0042", _context())

    seed_service_case(ServiceCaseStore(tmp_path), SEED)
    reopened = ServiceCaseStore(tmp_path).get("svc-2026-0042")

    assert reopened.service_case.plant_reported_context_ids == (
        "plant-context-test-001",
    )

def _request(
    store: ServiceCaseStore,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(store))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        body = None if payload is None else json.dumps(payload)
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        parsed = json.loads(response.read().decode("utf-8"))
        assert isinstance(parsed, dict)
        return response.status, parsed
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_http_service_reports_store_status_and_retained_case(tmp_path: Path) -> None:
    store = ServiceCaseStore(tmp_path)
    seed_service_case(store, SEED)

    status_code, status = _request(store, "GET", "/api/status")
    case_code, case = _request(
        store,
        "GET",
        "/api/service-cases/svc-2026-0042",
    )

    assert status_code == 200
    assert status["connected"] is True
    assert status["storage_available"] is True
    assert status["retained_service_case_count"] == 1
    assert status["production_record_authority"] is False
    assert case_code == 200
    stored = case["service_case"]
    assert stored["service_case_id"] == "svc-2026-0042"
    assert case["plant_reported_contexts"] == []


def test_http_service_persists_context_and_rejects_authority_promotion(
    tmp_path: Path,
) -> None:
    store = ServiceCaseStore(tmp_path)
    seed_service_case(store, SEED)
    payload = _context_payload()
    payload["verified_source_record"] = True
    payload["direct_system_observation"] = True
    payload["causal_claim_established"] = True

    code, response = _request(
        store,
        "POST",
        "/api/service-cases/svc-2026-0042/plant-context",
        payload,
    )

    assert code == 201
    contexts = response["plant_reported_contexts"]
    assert isinstance(contexts, list)
    assert len(contexts) == 1
    persisted = contexts[0]
    assert persisted["verified_source_record"] is False
    assert persisted["direct_system_observation"] is False
    assert persisted["causal_claim_established"] is False

    reopened = ServiceCaseStore(tmp_path).get("svc-2026-0042")
    assert len(reopened.plant_reported_contexts) == 1


def test_http_service_rejects_direct_source_retrieval_state(
    tmp_path: Path,
) -> None:
    store = ServiceCaseStore(tmp_path)
    seed_service_case(store, SEED)
    payload = _context_payload()
    payload["source_verification_state"] = "direct_source_retrieval"

    code, response = _request(
        store,
        "POST",
        "/api/service-cases/svc-2026-0042/plant-context",
        payload,
    )

    assert code == 400
    assert response["reason_code"] == "SERVICE_CASE.INVALID_REQUEST"
    assert "source_verification_state" in str(response["detail"])


def test_seed_fixture_contains_no_unresolved_context_reference() -> None:
    case = _seed_case()

    assert case.service_case_id == "svc-2026-0042"
    assert case.plant_reported_context_ids == ()
    assert case.first_detected_departure is not None
    assert case.first_detected_departure.asset_id == case.asset_id


def test_plant_context_contract_still_requires_timezone_aware_time() -> None:
    payload = _context_payload()
    payload["reported_event_start"] = "2026-09-27T13:40:00"

    with pytest.raises(ServiceCaseError, match="timezone-aware"):
        plant_reported_context_from_dict(payload)
