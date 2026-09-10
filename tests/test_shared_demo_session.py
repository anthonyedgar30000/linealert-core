from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PROFILE = ROOT / "profiles" / "synthetic-labeler-multi-iteration-trials-v1.json"


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
    assert "./trial-discipline-adapter.js" in plant_wrapper
    assert "./maintenance-response-adapter.js" in plant_wrapper
    assert "./session-adapter.js" in plant_wrapper
    assert "./recovery-fast-forward-adapter.js" in plant_wrapper
    assert plant_wrapper.index("./trial-discipline-adapter.js") < plant_wrapper.index(
        "./maintenance-response-adapter.js"
    )
    assert plant_wrapper.index("./maintenance-response-adapter.js") < plant_wrapper.index(
        "./session-adapter.js"
    )
    assert plant_wrapper.index("./session-adapter.js") < plant_wrapper.index(
        "./recovery-fast-forward-adapter.js"
    )

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
        "discipline",
        "verification",
        "decisionHistoryHtml",
        "handledIncidentIds",
    ):
        assert field in plant_adapter

    assert "LineAlertTrialDiscipline.snapshot" in plant_adapter
    assert "LineAlertTrialDiscipline.restore" in plant_adapter
    assert "NO ACTIVE DETECTED ISSUE · REFERENCE MODE" in guide_adapter
    assert "CURRENT DETECTED ISSUE · SHARED LIVE DEMO STATE" in guide_adapter
    assert "RECOVERY OBSERVED · REFERENCE MODE" in guide_adapter
    assert "recommendationTitle" in guide_adapter
    assert "latestTrial" in guide_adapter
    assert "productionVerification" in guide_adapter


def test_diagnostic_mode_does_not_imply_maintenance_dispatch():
    adapter = read(DOCS / "triage" / "maintenance-response-adapter.js")

    assert "maintenanceEta=qualifiedAvailabilityEta" in adapter
    assert "dispatchRecorded:false" in adapter
    assert "MAINTENANCE SUPPORT" in adapter
    assert "Not dispatched" in adapter
    assert "No maintenance dispatch is recorded for this concern" in adapter
    assert "synthetic_crew_occupancy" in adapter
    assert "mode==='diagnostic'" not in adapter.split(
        "maintenanceEta=qualifiedAvailabilityEta"
    )[0]


def test_post_recovery_fast_forward_starts_from_clean_live_projection():
    adapter = read(DOCS / "triage" / "recovery-fast-forward-adapter.js")

    assert "const baseCompleteRecovery=completeRecovery" in adapter
    assert "const baseSpeedClick=button.onclick" in adapter
    assert "function clearFastForwardState" in adapter
    assert "fast=false" in adapter
    assert "fastTarget=null" in adapter
    assert "fastEvent=null" in adapter
    assert "recoveryObserved=false" in adapter
    assert "currentIncident=null" in adapter
    assert "leaveRecoveredEpisodeForAdvance();" in adapter
    assert "baseSpeedClick.call(button)" in adapter
    assert "handledIncidentIds.clear" not in adapter
    assert "Preserve handledIncidentIds" in adapter


def test_trial_discipline_requires_explicit_restore_before_next_material_change():
    discipline = read(DOCS / "triage" / "trial-discipline-adapter.js")

    assert "stacking has not been earned yet" in discipline
    assert "Restore previous setting → arm 5-container verification" in discipline
    assert "No automatic equipment reset occurred" in discipline
    assert "Restore required before another material change" in discipline
    assert "Verified intermediate state retained" in discipline
    assert "state.completedTrials++" in discipline
    assert "iteration++" not in discipline
    assert "state.pendingExperimental&&MATERIAL_ACTIONS.has(actionKey)" in discipline
    assert "state.restoreContext&&MATERIAL_ACTIONS.has(actionKey)" in discipline


def test_synthetic_profile_declares_earned_stacking_semantics():
    profile = read(PROFILE)

    assert '"automatic_restore": false' in profile
    assert '"stack_unverified_changes": false' in profile
    assert '"restore-previous-setting"' in profile
    assert "retained verified intermediate state" in profile
    assert "LineAlert restore recommendation != automatic equipment restore" in profile


def test_static_sync_preserves_linealert_boundaries():
    doc = read(DOCS / "shared-demo-session.md")
    for boundary in (
        "Browser session snapshot != plant record.",
        "Telemetry != diagnosis.",
        "Recommendation != authorization or equipment command.",
        "Diagnostic state != maintenance dispatch.",
        "Historical pattern != current root cause.",
        "Five-container response != safe production change.",
    ):
        assert boundary in doc
