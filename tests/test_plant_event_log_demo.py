from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PROFILES = ROOT / "profiles"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_event_log_page_and_shared_navigation_exist():
    page = read(DOCS / "event-log.html")
    plant = read(DOCS / "triage" / "index.html")
    guide = read(DOCS / "troubleshooting-guide.html")
    nav = read(DOCS / "event-log-nav.js")

    assert "Plant Event Log" in page
    assert "Find message, event ID, incident, work order" in page
    assert "plant-event-model.js" in page
    assert "event-journal.js" in page
    assert "event-log-view.js" in page
    assert "event-log-nav.js" in plant
    assert "event-log-nav.js" in guide
    assert "Event Log" in nav


def test_roll_change_is_separate_context_not_incident_claim():
    model = read(DOCS / "plant-event-model.js")
    context = read(DOCS / "triage" / "event-context-adapter.js")
    guide_context = read(DOCS / "guide-event-context-adapter.js")

    assert "Alignment variability emerging" in model
    assert "Alignment variability after roll change" not in model
    assert "Label roll replaced and changeover record completed" in model
    assert "preceded_by_change_does_not_establish_cause" in model
    assert "preceded by change ≠ caused by change" in context
    assert "preceded by change ≠ caused by change" in guide_context


def test_event_log_preserves_source_identity_and_bounded_history():
    model = read(DOCS / "plant-event-model.js")
    journal = read(DOCS / "event-journal.js")
    view = read(DOCS / "event-log-view.js")
    profile = read(PROFILES / "synthetic-plant-event-log-v1.json")
    doc = read(DOCS / "plant-event-log.md")

    for token in (
        "synthetic-operator/changeover",
        "synthetic-telemetry/labeler2",
        "synthetic-cmms/plant",
        "synthetic-maintenance/dispatch",
        "linealert/deterministic",
        "clockQuality",
        "classification",
    ):
        assert token in model or token in journal

    assert "const MAX=200" in journal
    assert ".slice(0,250)" in view
    assert '"interactive_journal_max_events": 200' in profile
    assert "Event order != causal proof." in doc
    assert "bounded selected time window" in doc


def test_calendar_profile_no_longer_encodes_roll_change_in_incident_name():
    profile = read(PROFILES / "synthetic-shift-incident-calendar-v1.json")
    assert '"alignment_variability": 10' in profile
    assert '"alignment_after_roll_change": 10' not in profile
    assert "preceding_changeover_context" in profile
    assert "preceded by change != caused by change" in profile
