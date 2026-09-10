import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PROFILES = ROOT / "profiles"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_physics_profile_uses_explicit_units_equations_and_boundaries():
    profile = json.loads(read(PROFILES / "synthetic-roll-physics-signature-v1.json"))
    params = profile["synthetic_parameters"]

    assert profile["classification"] == "synthetic_demo_only"
    assert params["rpm"] == 960
    assert math.isclose(params["rpm"] / 60, 16.0)

    omega = 2 * math.pi * (params["rpm"] / 60)
    force = (
        params["effective_imbalance_mass_kg"]
        * params["healthy_eccentricity_m"]
        * omega**2
    )
    tension = params["drive_torque_nm"] / params["roll_radius_m"]
    current = params["drive_torque_nm"] / params["motor_torque_constant_nm_per_a"]

    assert 0 < force < 1
    assert math.isclose(tension, 5.0)
    assert 1.0 < current < 2.0
    assert "physics-informed synthetic model != OEM machine model" in profile["boundaries"]
    assert "signature match != diagnosis" in profile["boundaries"]
    assert "historical pattern != current root cause" in profile["boundaries"]


def test_browser_kernel_contains_deterministic_physics_relationships():
    model = read(DOCS / "physics-informed-roll-model.js")

    for token in (
        "rotationalHz",
        "angularVelocityRadS",
        "imbalanceForceN",
        "webTensionN",
        "motorCurrentA",
        "healthyFeatures",
        "problemFeatures",
        "detectionSeconds",
        "m*e*omega^2",
        "torque / roll_radius",
        "torque / Kt",
    ):
        assert token in model

    boundary = (
        "real structure mass, stiffness, damping, mounting and resonance "
        "are not commissioned"
    )
    assert "vibrationTransferGainMmSPerN" in model
    assert boundary in model


def test_event_model_emits_coupled_signature_before_concern_supporting_evidence():
    event_model = read(DOCS / "plant-event-model.js")

    message = (
        "Coupled rotational/tension signature moved outside synthetic healthy "
        "settling reference"
    )
    assert "LineAlertRollPhysics" in event_model
    assert "physics.episode" in event_model
    assert message in event_model
    assert "rotationalFrequencyHz" in event_model
    assert "imbalanceForceN" in event_model
    assert "vibration1xMmS" in event_model
    assert "webTensionPeakToPeakN" in event_model
    assert "motorCurrentPeakToPeakA" in event_model
    assert "model_match_is_supporting_evidence_not_diagnosis_or_root_cause_proof" in event_model


def test_plant_canvas_and_event_log_load_physics_before_event_model():
    plant = read(DOCS / "triage" / "index.html")
    event_log = read(DOCS / "event-log.html")
    adapter = read(DOCS / "triage" / "physics-signature-adapter.js")

    assert plant.index("physics-informed-roll-model.js") < plant.index(
        "plant-event-model.js"
    )
    assert event_log.index("physics-informed-roll-model.js") < event_log.index(
        "plant-event-model.js"
    )
    assert "physics-signature-adapter.js" in plant
    assert "PHYSICS-INFORMED SYNTHETIC SIGNATURE" in adapter
    assert "Show calculator relationships" in adapter
    assert "Model match ≠ diagnosis" in adapter


def test_event_log_profile_registers_signature_without_causal_claim():
    profile = json.loads(read(PROFILES / "synthetic-plant-event-log-v1.json"))
    signature = profile["physics_informed_signature"]

    assert signature["event_class"] == "SIGNATURE"
    assert "vibration_1x_mm_s" in signature["channels"]
    assert "web_tension_peak_to_peak_n" in signature["channels"]
    assert "motor_current_peak_to_peak_a" in signature["channels"]
    assert signature["boundary"] == (
        "physics-informed model match != diagnosis or current root-cause proof"
    )
