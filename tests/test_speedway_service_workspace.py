from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT_ROOT / "ui" / "app" / "page.tsx"
LEGACY_CANVAS = PROJECT_ROOT / "ui" / "app" / "plant-canvas" / "page.tsx"
WORKSPACE_STYLE = PROJECT_ROOT / "ui" / "app" / "service-workspace.module.css"
SERVICE_CASE_STATUS_ROUTE = (
    PROJECT_ROOT / "ui" / "app" / "api" / "service-cases" / "status" / "route.ts"
)
SERVICE_CASE_ROUTE = (
    PROJECT_ROOT
    / "ui"
    / "app"
    / "api"
    / "service-cases"
    / "[serviceCaseId]"
    / "route.ts"
)
PLANT_CONTEXT_ROUTE = (
    PROJECT_ROOT
    / "ui"
    / "app"
    / "api"
    / "service-cases"
    / "[serviceCaseId]"
    / "plant-context"
    / "route.ts"
)
START_HYBRID = PROJECT_ROOT / "scripts" / "start-hybrid.ps1"


def test_speedway_workspace_is_primary_frontend_surface() -> None:
    page = WORKSPACE.read_text(encoding="utf-8")

    assert "SPEEDWAY SERVICE WORKSPACE" in page
    assert "What changed before Speedway was called?" in page
    assert "WHY SPEEDWAY WAS CALLED" in page
    assert "PRE-INCIDENT RECONSTRUCTION" in page
    assert "First detected departure" in page
    assert "WHAT CHANGED" in page
    assert "WHAT HELD" in page
    assert "MISSING DISCRIMINATING CONTEXT" in page
    assert "WORKING EXPLANATIONS" in page
    assert "NEXT BOUNDED TECHNICIAN CHECK" in page


def test_workspace_preserves_service_case_epistemic_boundaries() -> None:
    page = WORKSPACE.read_text(encoding="utf-8")

    assert "First detected departure ≠ root cause" in page
    assert "temporal precedence ≠ causation" in page
    assert "recommendation ≠ authorized action" in page
    assert "plant_reported_context" in page
    assert "local persistence does not make it a" in page
    assert "verified source record" in page
    assert "not authorization to adjust the machine" in page


def test_manual_plant_context_uses_bounded_v1_verification_states() -> None:
    page = WORKSPACE.read_text(encoding="utf-8")

    assert 'value="plant_relay_only"' in page
    assert 'value="technician_viewed_source"' in page
    assert 'value="technician_retained_copy"' in page
    assert 'value="direct_source_retrieval"' not in page
    assert "Reported clock quality" in page
    assert "Original wording or bounded summary" in page
    assert "Persist reported context" in page
    assert "Reported time kind" in page
    assert 'type="datetime-local"' in page
    assert "persisted locally on the LineAlert host" in page
    assert "direct CMMS ingestion" in page


def test_legacy_plant_canvas_is_preserved_but_secondary() -> None:
    workspace = WORKSPACE.read_text(encoding="utf-8")
    legacy = LEGACY_CANVAS.read_text(encoding="utf-8")

    assert 'href="/plant-canvas"' in workspace
    assert "Legacy Plant Canvas" in workspace
    assert "LINEALERT · PLANT CANVAS · SYNTHETIC DEMO" in legacy
    assert 'href="/">Service workspace</Link>' in legacy


def test_workspace_has_dedicated_responsive_styles() -> None:
    styles = WORKSPACE_STYLE.read_text(encoding="utf-8")

    assert ".timeline" in styles
    assert ".contextForm" in styles
    assert ".twoColumn" in styles
    assert "@media(max-width:980px)" in styles


def test_workspace_uses_local_persistence_api_and_disables_unsaved_fallback() -> None:
    page = WORKSPACE.read_text(encoding="utf-8")

    assert 'fetch("/api/service-cases/status"' in page
    assert 'fetch("/api/service-cases/" + encodeURIComponent(fallbackCase.id)' in page
    assert '"/plant-context"' in page
    assert "Local persistence is unavailable; nothing was saved." in page
    assert "Browser-session entry only" not in page


def test_service_case_api_proxies_only_to_loopback_local_store() -> None:
    status_route = SERVICE_CASE_STATUS_ROUTE.read_text(encoding="utf-8")
    case_route = SERVICE_CASE_ROUTE.read_text(encoding="utf-8")
    context_route = PLANT_CONTEXT_ROUTE.read_text(encoding="utf-8")

    for route in (status_route, case_route, context_route):
        assert "http://127.0.0.1:8768" in route
        assert "LINEALERT_SERVICE_CASE_URL" in route
        assert "Cache-Control" in route
        assert "no-store" in route

    assert 'method: "POST"' in context_route
    assert "SERVICE_CASE.LOCAL_STORE_UNAVAILABLE" in context_route


def test_hybrid_startup_launches_loopback_service_case_persistence() -> None:
    script = START_HYBRID.read_text(encoding="utf-8")

    assert "linealert_core.service_case_service" in script
    assert "speedway_service_case_workspace_seed_v1.json" in script
    assert "service-cases-v1" in script
    assert "127.0.0.1 -Port 8768" in script
    assert "Service-case persistence: http://localhost:8768/api/status" in script
