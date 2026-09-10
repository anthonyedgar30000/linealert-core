from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_preserved_pr102_baselines_exist():
    plant = DOCS / "triage" / "plant-canvas-v102.html"
    guide = DOCS / "troubleshooting-guide-reference-v102.html"
    assert plant.exists()
    assert guide.exists()
    assert "The plant keeps moving while LineAlert watches." in read(plant)
    assert "LABELING TROUBLESHOOTING GUIDE" in read(guide)


def test_public_routes_attach_shared_session_adapters():
    plant_wrapper = read(DOCS / "triage" / "index.html")
    guide_wrapper = read(DOCS / "troubleshooting-guide.html")

    assert "plant-canvas-v102.html" in plant_wrapper
    assert "../demo-session.js" in plant_wrapper
    assert "./session-adapter.js" in plant_wrapper

    assert "troubleshooting-guide-reference-v102.html" in guide_wrapper
    assert "./demo-session.js" in guide_wrapper
    assert "./guide-session-adapter.js" in guide_wrapper


def test_shared_session_contract_carries_workflow_and_evidence_state():
    shared = read(DOCS / "demo-session.js")
    plant_adapter = read(DOCS / "triage" / "session-adapter.js")
    guide_adapter = read(DOCS / "guide-session-adapter.js")

    assert "linealert.synthetic.demo-session.v1" in shared
    assert "synthetic_demo_only" in shared
    assert "BroadcastChannel" in shared
    assert "localStorage" in shared

    for field in (
        "simAbs",
        "currentIncident",
        "recommendationTitle",
        "latestTrial",
        "verification",
        "decisionHistoryHtml",
        "handledIncidentIds",
    ):
        assert field in plant_adapter

    assert "NO ACTIVE DETECTED ISSUE · REFERENCE MODE" in guide_adapter
    assert "CURRENT DETECTED ISSUE · SHARED LIVE DEMO STATE" in guide_adapter
    assert "RECOVERY OBSERVED · REFERENCE MODE" in guide_adapter
    assert "recommendationTitle" in guide_adapter
    assert "latestTrial" in guide_adapter
    assert "productionVerification" in guide_adapter


def test_static_sync_preserves_linealert_boundaries():
    doc = read(DOCS / "shared-demo-session.md")
    for boundary in (
        "Browser session snapshot != plant record.",
        "Telemetry != diagnosis.",
        "Recommendation != authorization or equipment command.",
        "Historical pattern != current root cause.",
        "Five-container response != safe production change.",
    ):
        assert boundary in doc
