import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_guide_verification_and_restore_have_separate_authority_classes():
    profile = load("profiles/synthetic-labeler2-action-authority-v1.json")
    verify = profile["actions"]["verify-guide-spacing"]
    restore = profile["actions"]["restore-guide-spacing-to-reference"]

    assert verify["change_class"] == "verification_only"
    assert "Do not adjust" in verify["operator_scope"]
    assert restore["change_class"] == "bounded_material_change"
    assert restore["authorization"] == "standing_operator_authority"
    assert "Only after a current out-of-reference observation" in restore["operator_scope"]
    assert "fresh bounded machine evidence" in restore["verification_requirement"]


def test_route_profile_checks_before_conditional_restore():
    profile = load("profiles/speedway-labeler-troubleshooting-v1.routes.json")
    route = profile["procedures"]["LINEALERT.DEMO.LABEL_ALIGNMENT_OFF"]

    assert route["default_check"].startswith("Verify guide / spacing")
    assert route["default_intervention"].startswith("If a current observation shows")
    assert "Historical similarity does not establish" in route["standard_change_match"]["basis"]
    assert route["standard_change_match"]["verification"].startswith("Verify first.")
