from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT_ROOT / "ui" / "app" / "page.tsx"
LEGACY_CANVAS = PROJECT_ROOT / "ui" / "app" / "plant-canvas" / "page.tsx"
WORKSPACE_STYLE = PROJECT_ROOT / "ui" / "app" / "service-workspace.module.css"


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
    assert "not promoted to a verified source record" in page
    assert "not authorization to adjust the machine" in page


def test_manual_plant_context_uses_bounded_v1_verification_states() -> None:
    page = WORKSPACE.read_text(encoding="utf-8")

    assert 'value="plant_relay_only"' in page
    assert 'value="technician_viewed_source"' in page
    assert 'value="technician_retained_copy"' in page
    assert 'value="direct_source_retrieval"' not in page
    assert "Reported clock quality" in page
    assert "Original wording or bounded summary" in page
    assert "Browser-session entry only" in page


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
