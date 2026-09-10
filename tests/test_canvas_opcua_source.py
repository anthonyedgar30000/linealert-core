from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_canvas_loads_opcua_orchestration_after_shared_journal_and_source_adapter():
    index = (ROOT / "docs" / "triage" / "index.html").read_text(encoding="utf-8")

    journal = index.index("../event-journal.js")
    source_adapter = index.index("./opcua-source-adapter.js")
    render_ownership = index.index("./opcua-render-ownership-adapter.js")
    orchestration = index.index("./opcua-plant-orchestration-adapter.js")
    guide_adapter = index.index("./guide-control-adapter.js")

    assert journal < source_adapter < render_ownership < orchestration < guide_adapter


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
    assert "SOURCE DISCONNECTED · FAIL CLOSED" in script
    assert "browser-generated machine evidence will not take over" in script
    assert "calendar incident fast-forward is disabled" in script


def test_canvas_distinguishes_connection_from_evidence_admission_and_bridge_state():
    script = (ROOT / "docs" / "triage" / "opcua-source-adapter.js").read_text(encoding="utf-8")

    assert "function markConnectedUnqualified(payload)" in script
    assert "function markDisconnected(payload)" in script
    assert "function markBridgeUnavailable(reason)" in script
    assert "if(payload&&payload.connected===true)" in script
    assert "if(payload&&payload.connected===false)" in script
    assert "connected · evidence unqualified" in script
    assert "SOURCE · LABELER 2 OPC UA EMULATOR · DISCONNECTED" in script
    assert "SOURCE · LOCAL OPC UA BRIDGE · UNAVAILABLE" in script
    assert "OPC UA connection state is not inferred from this browser error" in script
    assert "availabilityState==='qualified'||availabilityState==='connected_unqualified'" in script
    assert "admitted:availabilityState==='qualified'" in script


def test_opcua_render_ownership_reapplies_source_machine_labels_after_baseline_renderer():
    script = (
        ROOT / "docs" / "triage" / "opcua-render-ownership-adapter.js"
    ).read_text(encoding="utf-8")

    assert "const browserUpdateModeLabels=updateModeLabels" in script
    assert "const result=browserUpdateModeLabels()" in script
    assert "if(!status||!status.everActivated)return result" in script
    assert "if(status.availabilityState==='qualified')applyQualifiedMachineLabels(status)" in script
    assert "Context · no mapped OPC UA signal" in script
    assert "Source reports production" in script
    assert "LABELER 2 RUNNING · OPC UA CONNECTED" in script
    assert "EVIDENCE UNQUALIFIED · INTERPRETATION PAUSED" in script
    assert "SOURCE DISCONNECTED · FAIL CLOSED" in script
    assert "BRIDGE UNAVAILABLE · FAIL CLOSED" in script


def test_canvas_opcua_trial_waits_for_external_source_evidence():
    script = (ROOT / "docs" / "triage" / "opcua-source-adapter.js").read_text(encoding="utf-8")

    assert "WAITING FOR EXTERNAL OPC UA DIAGNOSTIC BATCH" in script
    assert "OPC UA diagnostic batch captured" in script
    assert "Test response ≠ causal proof." in script


def test_opcua_source_status_exposes_qualified_run_state_to_workflow_adapters():
    script = (ROOT / "docs" / "triage" / "opcua-source-adapter.js").read_text(encoding="utf-8")

    assert "runStateCode:latest?numeric(latest,'run_state_code'):null" in script
    assert "sourceSequence:latest?numeric(latest,'emulator_sequence'):null" in script


def test_source_orchestration_owns_fast_forward_and_source_event_ingestion():
    script = (ROOT / "docs" / "triage" / "opcua-plant-orchestration-adapter.js").read_text(
        encoding="utf-8"
    )

    assert "fetch('/api/plant-events?after='" in script
    assert "fast_forward_to_next_concern" in script
    assert "Fast-forward to next concern precursor" in script
    assert "pendingTarget" in script
    assert "sourceSequence" in script
    assert "source_owned_plant_event" not in script  # supplied by source event fields
    assert "clockQuality:'deterministic_simulator_sequence'" in script
    assert "Stop Labeler 2 for bounded diagnostic" in script
    assert "LABELER 2 STOPPED · OPC UA CONNECTED" in script


def test_source_event_context_can_replace_browser_generated_roll_change_context():
    script = (ROOT / "docs" / "triage" / "event-context-adapter.js").read_text(encoding="utf-8")

    assert "LineAlertOpcuaPlantOrchestration" in script
    assert "latestRollChangeBefore" in script
    assert "sourceOwnedContext(inc)||model.precedingContext(inc)" in script
    assert "preceded by change ≠ caused by change" in script


def test_event_context_does_not_overwrite_recovered_headline():
    script = (ROOT / "docs" / "triage" / "event-context-adapter.js").read_text(encoding="utf-8")

    assert "function activeGuideIncident()" in script
    assert "&&incident===true" in script
    assert "if(activeGuideIncident())" in script


def test_event_journal_can_preserve_source_clock_quality():
    script = (ROOT / "docs" / "event-journal.js").read_text(encoding="utf-8")

    assert "clockQuality:input.clockQuality||'synthetic_session_clock'" in script
    assert "classification:input.classification||'synthetic_demo_only'" in script


def test_local_event_log_suppresses_browser_labeler_machine_events_when_source_events_exist():
    script = (ROOT / "docs" / "event-log-view.js").read_text(encoding="utf-8")

    assert "source_owned_plant_event===true" in script
    assert "browserLabelerMachineEvent" in script


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


def test_guide_workflow_is_gated_by_qualified_opcua_run_state_not_browser_mode():
    script = (ROOT / "docs" / "triage" / "guide-control-adapter.js").read_text(
        encoding="utf-8"
    )

    assert "function sourceRunState()" in script
    assert "runStateCode" in script
    assert "if(sourceRunState()!==1)return;" in script
    assert "if(sourceRunState()!==0)return;" in script
    assert "if(runState===1)" in script
    assert "if(runState!==0)return;" in script
    assert "Waiting for OPC UA stopped state" in script
    assert "Inspection remains blocked until qualified OPC UA reports run_state_code 0" in script
    assert (
        "Production verification starts only after qualified OPC UA reports production running"
        in script
    )
    assert "if(mode==='production')" not in script
    assert "if(mode!=='diagnostic'||trialInProgress" not in script


def test_public_home_labels_browser_build_as_scenario_preview():
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")

    assert "Scenario preview" in page
    assert "no physical equipment connection" in page
