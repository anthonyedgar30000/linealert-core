from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_canvas_loads_opcua_source_adapter_after_shared_journal():
    index = (ROOT / "docs" / "triage" / "index.html").read_text(encoding="utf-8")

    journal = index.index("../event-journal.js")
    source_adapter = index.index("./opcua-source-adapter.js")
    guide_adapter = index.index("./guide-control-adapter.js")

    assert journal < source_adapter < guide_adapter


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


def test_guide_control_adapter_verifies_before_restore_and_uses_simulator_control_channel():
    script = (ROOT / "docs" / "triage" / "guide-control-adapter.js").read_text(
        encoding="utf-8"
    )

    assert "Verify guide / spacing against approved setup reference" in script
    assert "fetch('/api/demo-control'" in script
    assert "stop_for_diagnostic" in script
    assert "inspect_guide" in script
    assert "restore_guide" in script
    assert "observation_id:guideObservation.observation_id" in script
    assert "run_diagnostic_batch" in script
    assert "resume_production" in script
    assert "synthetic_human_observation" not in script  # classification comes from control result
    assert "No guide correction indicated" in script
    assert "fresh OPC UA observations" in script


def test_public_home_labels_browser_build_as_scenario_preview():
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")

    assert "Scenario preview" in page
    assert "no physical equipment connection" in page
