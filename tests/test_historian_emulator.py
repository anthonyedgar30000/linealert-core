from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from linealert_core.historian_emulator import (
    PERSISTENCE,
    SOURCE_MODE,
    EmulatedHistorianStore,
    HistorianEmulatorError,
    cycle_profile,
)
from linealert_core.historian_emulator_service import (
    EmulatorRuntimeState,
    handler_for,
    run_generator,
    status_payload,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "examples" / "labeler_demo_config.json"


def test_cycle_profile_is_deterministic_and_has_bounded_scenario_phases() -> None:
    stable = cycle_profile(3)
    incipient = cycle_profile(21)
    persistent = cycle_profile(28)
    observation = cycle_profile(37)
    recovered = cycle_profile(44)

    assert stable.scenario_phase == "stable_reference"
    assert stable.label_presentation_delay_ms <= 350.0
    assert incipient.scenario_phase == "incipient_presentation_drift"
    assert persistent.scenario_phase == "persistent_presentation_drift"
    assert persistent.label_presentation_delay_ms > 350.0
    assert observation.scenario_phase == "bounded_diagnostic_observation"
    assert recovered.scenario_phase == "post_intervention_observation"
    assert recovered.label_presentation_delay_ms <= 350.0

    assert cycle_profile(28) == persistent
    assert cycle_profile(48).episode_id != stable.episode_id

    with pytest.raises(HistorianEmulatorError, match="non-negative"):
        cycle_profile(-1)


def test_store_seeds_live_history_and_preserves_changed_vs_held_relationships(
    tmp_path: Path,
) -> None:
    store = EmulatedHistorianStore(
        tmp_path / "historian.sqlite3",
        config_path=CONFIG,
        retention_cycles=96,
    )
    anchor = datetime(2026, 9, 28, 22, 0, tzinfo=UTC)
    store.seed_window(cycles=30, interval_seconds=2.0, now=anchor)

    assert store.retained_cycle_count() == 30

    functional = store.functional_temporal_history(limit=8)
    assert functional["schema_version"] == (
        "linealert.historian.functional-temporal-history.v1"
    )
    assert functional["persistence"] == PERSISTENCE
    assert functional["source_mode"] == SOURCE_MODE
    assert functional["emulated"] is True
    assert functional["count"] == 8
    assert functional["truncated"] is True

    records = functional["records"]
    assert isinstance(records, list)
    assert records[-1]["asset_id"] == "LABELER-DEMO-01"
    assert records[-1]["operating_context"]["context_tags"][
        "source_classification"
    ] == "controlled_synthetic_demo"

    label = store.condition_history(
        relationship_id="relationship:label-presentation-delay",
        limit=30,
    )
    spacing = store.condition_history(
        relationship_id="relationship:bottle-spacing-delay",
        limit=30,
    )
    assert label["count"] == 30
    assert spacing["count"] == 30
    assert any(
        measurement["temporal_rule_status"] == "late"
        for measurement in label["measurements"]
    )
    assert all(
        measurement["temporal_rule_status"] == "within"
        for measurement in spacing["measurements"]
    )
    assert all(
        measurement["evidence_authority"]["physical_state_authority"] is False
        for measurement in label["measurements"]
    )
    store.close()


def test_store_persists_sequence_and_records_across_restart(tmp_path: Path) -> None:
    database = tmp_path / "historian.sqlite3"
    first = EmulatedHistorianStore(
        database,
        config_path=CONFIG,
        retention_cycles=96,
    )
    first.append_next_cycle(
        observed_at=datetime(2026, 9, 28, 22, 0, tzinfo=UTC),
    )
    before = first.latest_cycle()
    first.close()

    reopened = EmulatedHistorianStore(
        database,
        config_path=CONFIG,
        retention_cycles=96,
    )
    retained = reopened.functional_temporal_history(limit=10)
    assert retained["count"] == 2
    assert before is not None
    assert reopened.latest_cycle() == before

    next_cycle = reopened.append_next_cycle(
        observed_at=datetime(2026, 9, 28, 22, 0, 2, tzinfo=UTC),
    )
    assert next_cycle.sequence == 1
    assert reopened.retained_cycle_count() == 2
    reopened.close()


def test_store_retention_is_cycle_bounded(tmp_path: Path) -> None:
    store = EmulatedHistorianStore(
        tmp_path / "historian.sqlite3",
        config_path=CONFIG,
        retention_cycles=48,
    )
    anchor = datetime(2026, 9, 28, 22, 0, tzinfo=UTC)
    for index in range(60):
        store.append_next_cycle(observed_at=anchor + timedelta(seconds=index))

    assert store.retained_cycle_count() == 48
    observations = store.observation_history(limit=100)
    assert observations["count"] == 48
    assert observations["observations"][0]["observation_sequence"] == 12
    store.close()
def test_history_query_rejects_invalid_bounds_kind_and_limit(tmp_path: Path) -> None:
    store = EmulatedHistorianStore(
        tmp_path / "historian.sqlite3",
        config_path=CONFIG,
        retention_cycles=96,
    )
    store.append_next_cycle()

    with pytest.raises(HistorianEmulatorError, match="between 1 and 5000"):
        store.functional_temporal_history(limit=5001)
    with pytest.raises(HistorianEmulatorError, match="record_kind is invalid"):
        store.functional_temporal_history(record_kind="NOT_A_KIND")
    with pytest.raises(HistorianEmulatorError, match="timezone-aware"):
        store.functional_temporal_history(
            from_time=datetime(2026, 9, 28, 22, 0),
        )
    with pytest.raises(HistorianEmulatorError, match="less than or equal"):
        store.functional_temporal_history(
            from_time=datetime(2026, 9, 28, 23, 0, tzinfo=UTC),
            to_time=datetime(2026, 9, 28, 22, 0, tzinfo=UTC),
        )
    store.close()


def _request(
    store: EmulatedHistorianStore,
    runtime_state: EmulatorRuntimeState,
    method: str,
    path: str,
) -> tuple[int, dict[str, object]]:
    started_at = datetime(2026, 9, 28, 22, 0, tzinfo=UTC)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        handler_for(
            store,
            runtime_state,
            interval_seconds=2.0,
            started_at=started_at,
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert isinstance(payload, dict)
        return response.status, payload
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_http_status_and_history_expose_explicit_emulation_identity(
    tmp_path: Path,
) -> None:
    store = EmulatedHistorianStore(
        tmp_path / "historian.sqlite3",
        config_path=CONFIG,
        retention_cycles=96,
    )
    store.seed_window(cycles=20, interval_seconds=2.0)
    runtime = EmulatorRuntimeState()
    runtime.mark_success()

    status_code, status = _request(store, runtime, "GET", "/api/status")
    history_code, history = _request(
        store,
        runtime,
        "GET",
        "/api/history/functional-temporal?limit=8",
    )

    assert status_code == 200
    assert status["connected"] is True
    assert status["source_available"] is True
    assert status["historian_backend"] == "sqlite_emulator"
    assert status["persistence"] == PERSISTENCE
    assert status["source_mode"] == SOURCE_MODE
    assert status["source_classification"] == "controlled_synthetic_demo"
    assert status["emulated"] is True
    assert status["physical_state_authority"] is False
    assert status["production_authority"] is False

    assert history_code == 200
    assert history["count"] == 8
    assert history["emulated"] is True
    store.close()


def test_http_emulator_refuses_external_historian_writes(tmp_path: Path) -> None:
    store = EmulatedHistorianStore(
        tmp_path / "historian.sqlite3",
        config_path=CONFIG,
        retention_cycles=96,
    )
    store.append_next_cycle()
    runtime = EmulatorRuntimeState()
    runtime.mark_success()

    code, payload = _request(store, runtime, "POST", "/api/outcomes")

    assert code == 405
    assert payload["accepted"] is False
    assert payload["reason_code"] == "AUTHORITY.EMULATED_HISTORIAN_HTTP_READ_ONLY"
    assert payload["equipment_effect"] == "none"
    store.close()


def test_unimplemented_emulated_localization_fails_closed(tmp_path: Path) -> None:
    store = EmulatedHistorianStore(
        tmp_path / "historian.sqlite3",
        config_path=CONFIG,
        retention_cycles=96,
    )
    store.append_next_cycle()
    runtime = EmulatorRuntimeState()
    runtime.mark_success()

    code, payload = _request(
        store,
        runtime,
        "GET",
        "/api/history/conditions/localize",
    )

    assert code == 503
    assert payload["disposition"] == "UNAVAILABLE"
    assert payload["reason_code"] == "EVIDENCE.EMULATED_LOCALIZATION_NOT_IMPLEMENTED"
    store.close()


def test_generator_advances_live_retained_history(tmp_path: Path) -> None:
    store = EmulatedHistorianStore(
        tmp_path / "historian.sqlite3",
        config_path=CONFIG,
        retention_cycles=96,
    )
    runtime = EmulatorRuntimeState()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_generator,
        args=(store, runtime),
        kwargs={"interval_seconds": 0.03, "stop_event": stop_event},
        daemon=True,
    )
    thread.start()
    try:
        time.sleep(0.12)
    finally:
        stop_event.set()
        thread.join(timeout=1)

    assert store.retained_cycle_count() >= 2
    state = runtime.get()
    assert state["source_available"] is True
    assert state["reason_code"] == "EVIDENCE.EMULATED_HISTORIAN_STREAMING"
    store.close()


def test_status_separates_retained_store_from_stream_source_health(
    tmp_path: Path,
) -> None:
    store = EmulatedHistorianStore(
        tmp_path / "historian.sqlite3",
        config_path=CONFIG,
        retention_cycles=96,
    )
    store.append_next_cycle()
    runtime = EmulatorRuntimeState()
    runtime.mark_failure(HistorianEmulatorError("synthetic failure"))

    payload = status_payload(
        store,
        runtime,
        interval_seconds=2.0,
        started_at=datetime(2026, 9, 28, 22, 0, tzinfo=UTC),
    )

    assert payload["connected"] is True
    assert payload["source_available"] is False
    assert payload["retained_cycle_count"] == 1
    assert payload["reason_code"] == "EVIDENCE.EMULATED_HISTORIAN_SOURCE_UNAVAILABLE"
    assert payload["error"] == "HistorianEmulatorError"
    store.close()
