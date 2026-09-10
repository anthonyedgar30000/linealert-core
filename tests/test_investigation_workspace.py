import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PROFILE = ROOT / "profiles" / "synthetic-labeler2-investigation-v1.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_plant_canvas_links_to_evolving_investigation():
    wrapper = read(DOCS / "triage" / "index.html")
    adapter = read(DOCS / "triage" / "investigation-link-adapter.js")

    assert "./investigation-link-adapter.js" in wrapper
    assert "Open evolving investigation" in adapter
    assert "../investigation/" in adapter
    assert "Working explanations" in adapter
    assert "root_cause_status" not in adapter


def test_investigation_page_uses_shared_session_and_event_journal():
    page = read(DOCS / "investigation" / "index.html")

    assert "../demo-session.js" in page
    assert "../event-journal.js" in page
    assert "../investigation-model.js" in page
    assert "CURRENT WORKING PICTURE" in page
    assert "BEST NEXT BOUNDED STEP" in page
    assert "How the investigation changed" in page
    assert "terminal causal verdict" in page
    assert "root cause" not in page.lower()


def test_investigation_profile_keeps_multiple_working_explanations():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    assert profile["classification"] == "synthetic_demo_only"
    ids = [item["id"] for item in profile["working_hypotheses"]]
    assert ids == ["roll_web_path", "guide_spacing", "timing_controls"]
    assert profile["next_step_principle"].startswith("Prefer observation-only")
    assert "most_supported" in profile["standing_vocabulary"]
    assert "plausible" in profile["standing_vocabulary"]
    assert "lower_priority" in profile["standing_vocabulary"]
    assert all("root cause" not in item.lower() for item in profile["boundaries"])


def test_investigation_model_reranks_without_causal_terminal_state():
    model = read(DOCS / "investigation-model.js")

    assert "most_supported" in model
    assert "plausible" in model
    assert "less_supported" in model
    assert "eventsForIncident" in model
    assert "latestTrial" in model
    assert "productionVerification" in model
    assert "recoveryObserved" in model
    assert "Operating behavior remained stable" in model
    assert "root_cause_status" not in model
    assert "root cause" not in model.lower()


def test_investigation_workspace_preserves_linealert_boundaries():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    boundaries = profile["boundaries"]

    for boundary in (
        "working explanation != diagnosis",
        "investigation priority != causal probability",
        "test response != causal proof",
        "intervention followed by improvement != proof of mechanism",
        "recommendation != authorized action",
        "synthetic demo evidence != physical machine evidence",
    ):
        assert boundary in boundaries
