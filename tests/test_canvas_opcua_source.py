from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canvas_loads_opcua_source_adapter_after_shared_journal():
    index = (ROOT / "docs" / "triage" / "index.html").read_text(encoding="utf-8")

    journal = index.index("../event-journal.js")
    adapter = index.index("./opcua-source-adapter.js")

    assert journal < adapter


def test_canvas_opcua_adapter_requires_qualified_read_only_labeler_source():
    script = (ROOT / "docs" / "triage" / "opcua-source-adapter.js").read_text(encoding="utf-8")

    assert "fetch('/api/telemetry'" in script
    assert "linealert-labeler2-observable-v1" in script
    assert "payload.asset_id!==ASSET" in script
    assert "payload.source_kind!=='simulator'" in script
    assert "payload.source_scope!=='simulator_only'" in script
    assert "payload.read_only!==true" in script
    assert "payload.semantic_admission.admitted!==true" in script


def test_canvas_opcua_mode_suppresses_browser_machine_generation_and_fails_closed():
    script = (ROOT / "docs" / "triage" / "opcua-source-adapter.js").read_text(encoding="utf-8")

    assert "maybeTriggerIncident=function()" in script
    assert "if(everActivated)return;" in script
    assert "live=function(delta)" in script
    assert "SOURCE UNAVAILABLE · FAIL CLOSED" in script
    assert "will not fall back to browser-generated machine evidence" in script
    assert "calendar incident fast-forward is disabled" in script


def test_canvas_opcua_trial_waits_for_external_source_evidence():
    script = (ROOT / "docs" / "triage" / "opcua-source-adapter.js").read_text(encoding="utf-8")

    assert "WAITING FOR EXTERNAL OPC UA DIAGNOSTIC BATCH" in script
    assert "OPC UA diagnostic batch captured" in script
    assert "Test response ≠ causal proof." in script


def test_public_home_labels_browser_build_as_scenario_preview():
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")

    assert "Scenario preview" in page
    assert "no physical equipment connection" in page
