import json
from pathlib import Path

from linealert_core.evidence_hierarchy import (
    classify_observation,
    evaluate_claim_evidence,
)

PROFILE = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "profiles"
        / "evidence-hierarchy-v1.json"
    ).read_text(encoding="utf-8")
)


def observation(
    observation_id: str,
    category: str,
    claim_id: str,
    *,
    supports: bool = True,
    failure_domain: str = "controller",
    scope: str = "commissioned_machine",
    semantic_admitted: bool = True,
    quality: str = "good",
    fresh: bool = True,
    binding_verified: bool = True,
    calibration_state: str = "current",
    acceptance_plan_id: str | None = None,
    outcome_result: str | None = None,
) -> dict[str, object]:
    return {
        "observation_id": observation_id,
        "category": category,
        "supported_claims": [claim_id],
        "supports": supports,
        "failure_domain": failure_domain,
        "scope": scope,
        "semantic_admitted": semantic_admitted,
        "quality": quality,
        "fresh": fresh,
        "binding_verified": binding_verified,
        "calibration_state": calibration_state,
        "acceptance_plan_id": acceptance_plan_id,
        "outcome_result": outcome_result,
    }


def assess(claim_id: str, *items: dict[str, object]) -> dict[str, object]:
    return evaluate_claim_evidence(
        claim_id=claim_id,
        observations=list(items),
        profile=PROFILE,
    )


def test_unknown_value_remains_level_zero() -> None:
    result = classify_observation(
        {"observation_id": "unknown-1", "category": "unknown"},
        claim_id="physical.bottle_arrival",
        profile=PROFILE,
    )

    assert result["base_level"] == 0
    assert result["admissible"] is False
    assert result["reason_code"] == "EVIDENCE.HIERARCHY_UNKNOWN"


def test_controller_command_establishes_relevant_level_one_claim() -> None:
    result = assess(
        "controller.label_command",
        observation(
            "command-1",
            "controller_intent",
            "controller.label_command",
        ),
    )

    assert result["status"] == "SUPPORTED"
    assert result["evidence_level"] == 1


def test_verified_field_input_establishes_level_two() -> None:
    result = assess(
        "physical.wrapper_entry_detection",
        observation(
            "photoeye-1",
            "verified_field_input",
            "physical.wrapper_entry_detection",
            failure_domain="photoeye-channel",
        ),
    )

    assert result["status"] == "SUPPORTED"
    assert result["evidence_level"] == 2


def test_independent_camera_observation_establishes_level_three() -> None:
    result = assess(
        "physical.label_present",
        observation(
            "camera-1",
            "camera_observation",
            "physical.label_present",
            failure_domain="vision-system",
        ),
    )

    assert result["status"] == "SUPPORTED"
    assert result["evidence_level"] == 3


def test_independent_sources_derive_level_four() -> None:
    claim_id = "physical.bottle_arrived_at_wrapper"
    result = assess(
        claim_id,
        observation(
            "photoeye-1",
            "verified_field_input",
            claim_id,
            failure_domain="photoeye-channel",
        ),
        observation(
            "camera-1",
            "camera_observation",
            claim_id,
            failure_domain="vision-system",
        ),
    )

    assert result["status"] == "SUPPORTED"
    assert result["evidence_level"] == 4
    assert result["reason_code"] == "EVIDENCE.HIERARCHY_INDEPENDENTLY_CORROBORATED"


def test_shared_failure_domain_does_not_establish_level_four() -> None:
    claim_id = "physical.bottle_arrived_at_wrapper"
    result = assess(
        claim_id,
        observation(
            "tag-1",
            "device_feedback",
            claim_id,
            failure_domain="plc-input-card",
        ),
        observation(
            "tag-2",
            "device_feedback",
            claim_id,
            failure_domain="plc-input-card",
        ),
    )

    assert result["status"] == "SUPPORTED"
    assert result["evidence_level"] == 2


def test_verified_outcome_under_acceptance_plan_establishes_level_five() -> None:
    result = assess(
        "product.label_placement_accepted",
        observation(
            "qa-1",
            "verified_outcome",
            "product.label_placement_accepted",
            failure_domain="qa-inspection",
            acceptance_plan_id="QA-LABEL-05",
            outcome_result="accepted",
        ),
    )

    assert result["status"] == "SUPPORTED"
    assert result["evidence_level"] == 5


def test_contradiction_is_preserved_without_voting() -> None:
    claim_id = "physical.label_present"
    result = assess(
        claim_id,
        observation(
            "plc-feedback",
            "device_feedback",
            claim_id,
            supports=True,
            failure_domain="plc-output-feedback",
        ),
        observation(
            "camera-1",
            "camera_observation",
            claim_id,
            supports=False,
            failure_domain="vision-system",
        ),
    )

    assert result["status"] == "CONTRADICTED"
    assert result["reason_code"] == "EVIDENCE.HIERARCHY_CONTRADICTION_PRESERVED"
    assert result["supporting_observation_ids"] == ["plc-feedback"]
    assert result["opposing_observation_ids"] == ["camera-1"]


def test_simulator_scope_cannot_support_physical_claim() -> None:
    result = assess(
        "physical.motor_speed",
        observation(
            "sim-rpm",
            "controller_internal_state",
            "physical.motor_speed",
            scope="simulator_only",
        ),
    )

    assert result["status"] == "INSUFFICIENT"
    item = result["observations"][0]
    assert item["reason_code"] == "EVIDENCE.HIERARCHY_SIMULATOR_PHYSICAL_CLAIM_REFUSED"


def test_claim_irrelevant_evidence_is_refused() -> None:
    item = observation(
        "command-1",
        "controller_intent",
        "controller.label_command",
    )
    result = classify_observation(
        item,
        claim_id="physical.label_present",
        profile=PROFILE,
    )

    assert result["admissible"] is False
    assert result["reason_code"] == "EVIDENCE.HIERARCHY_CLAIM_IRRELEVANT"


def test_stale_or_uncalibrated_evidence_is_refused() -> None:
    stale = assess(
        "physical.pressure",
        observation(
            "pressure-1",
            "device_feedback",
            "physical.pressure",
            fresh=False,
        ),
    )
    uncalibrated = assess(
        "physical.pressure",
        observation(
            "pressure-2",
            "device_feedback",
            "physical.pressure",
            calibration_state="expired",
        ),
    )

    assert stale["status"] == "INSUFFICIENT"
    assert stale["observations"][0]["reason_code"] == "EVIDENCE.HIERARCHY_STALE"
    assert uncalibrated["status"] == "INSUFFICIENT"
    assert (
        uncalibrated["observations"][0]["reason_code"]
        == "EVIDENCE.HIERARCHY_CALIBRATION_UNACCEPTABLE"
    )


def test_level_never_grants_action_authority() -> None:
    result = assess(
        "product.label_placement_accepted",
        observation(
            "qa-1",
            "verified_outcome",
            "product.label_placement_accepted",
            acceptance_plan_id="QA-LABEL-05",
            outcome_result="accepted",
        ),
    )

    assert result["authorized_action"] is False
