from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REASONING_PAGE = PROJECT_ROOT / "ui" / "app" / "reasoning" / "page.tsx"
REASONING_CLIENT = (
    PROJECT_ROOT / "ui" / "app" / "reasoning" / "reasoning-client.tsx"
)
START_HYBRID = PROJECT_ROOT / "scripts" / "start-hybrid.ps1"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


def test_reasoning_inputs_surfaces_live_emulation_without_timescale_claim() -> None:
    page = REASONING_CLIENT.read_text(encoding="utf-8")

    assert "LIVE EMULATION" in page
    assert "Local emulated historian" in page
    assert "SQLite-backed deterministic synthetic history" in page
    assert "not TimescaleDB or physical plant history" in page
    assert "EMULATED SOURCE LIVE" in page
    assert "Historian backend" in page
    assert "Source classification" in page
    assert "Latest scenario phase" in page
    assert "Latest cycle" in page
    assert "controlled synthetic emulation" in page
    assert "not verified physical plant history" in page


def test_reasoning_inputs_displays_measurement_and_envelope_context() -> None:
    page = REASONING_CLIENT.read_text(encoding="utf-8")

    assert "record.details?.value" in page
    assert "record.details.min_value" in page
    assert "record.details.max_value" in page
    assert "record.details.scenario_phase" in page
    assert "Evidence IDs" in page
    assert "Reasons" in page


def test_hybrid_launcher_has_explicit_emulated_historian_mode() -> None:
    script = START_HYBRID.read_text(encoding="utf-8")

    assert "[switch]$UseEmulatedHistorian" in script
    assert "Choose either -SkipHistorian or -UseEmulatedHistorian" in script
    assert "linealert_core.historian_emulator_service" in script
    assert "historian-emulator-v1\\historian.sqlite3" in script
    assert "Emulated historian: http://localhost:8767/api/status" in script
    assert "emulated historian != TimescaleDB != verified physical history" in script


def test_emulated_historian_has_dedicated_cli_entrypoint() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")

    assert (
        'linealert-historian-emulator = '
        '"linealert_core.historian_emulator_service:main"'
    ) in pyproject


def test_reasoning_page_server_renders_initial_historian_state() -> None:
    page = REASONING_PAGE.read_text(encoding="utf-8")

    assert 'export const dynamic = "force-dynamic"' in page
    assert "http://127.0.0.1:8767" in page
    assert 'fetch(new URL("/api/status", historianBaseUrl)' in page
    assert (
        'fetch(new URL("/api/history/functional-temporal?limit=8", historianBaseUrl)'
        in page
    )
    assert "EVIDENCE.HISTORIAN_UNAVAILABLE" in page
    assert "ReasoningInputsClient" in page


def test_reasoning_client_polls_after_server_initial_state() -> None:
    client = REASONING_CLIENT.read_text(encoding="utf-8")

    assert "initialStatus" in client
    assert "initialHistory" in client
    assert "initialReachable" in client
    assert 'fetch("/api/historian/status"' in client
    assert 'fetch("/api/historian/functional-temporal?limit=8"' in client


def test_reasoning_timestamps_are_hydration_deterministic() -> None:
    client = REASONING_CLIENT.read_text(encoding="utf-8")

    assert "parsed.toISOString()" in client
    assert 'iso.slice(0, 10) + " " + iso.slice(11, 19) + " UTC"' in client
    assert "toLocaleString" not in client
    assert "toLocaleDateString" not in client
    assert "toLocaleTimeString" not in client
