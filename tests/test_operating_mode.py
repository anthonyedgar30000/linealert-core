import copy
import json
from pathlib import Path

from linealert_core.operating_mode import (
    enforce_operating_mode,
    evaluate_operating_mode,
    load_operating_mode_profile,
)

PROFILE = load_operating_mode_profile(
    Path(__file__).resolve().parents[1] / "profiles" / "operating-modes-v1.json"
)


def assessment(mode: str, sources: list[str]) -> dict:
    return evaluate_operating_mode(
        configured_mode=mode,
        source_kinds=sources,
        profile=PROFILE,
    )


def semantic_payload() -> dict:
    return {
        "reason_code": "EVIDENCE.OPCUA_SAMPLE_QUALIFIED",
        "semantic_admission": {
            "admitted_count": 1,
            "scope": "simulator_only",
            "reason_code": "EVIDENCE.SEMANTIC_ADMISSION_PARTIAL",
            "signals": {
                "rpm": {
                    "admitted": True,
                    "scope": "simulator_only",
                    "reason_code": "EVIDENCE.SEMANTIC_BINDING_ADMITTED",
                }
            },
        },
    }


def test_demo_mode_admits_only_simulator_source() -> None:
    result = assessment("demo_emulation", ["simulator"])

    assert result["source_admitted"] is True
    assert result["scope"] == "simulator_only"
    assert result["reason_code"] == "EVIDENCE.OPERATING_MODE_SOURCE_ADMITTED"
    assert result["authorized_action"] is False


def test_physical_modes_refuse_simulator_source() -> None:
    for mode in ("physical_commissioning", "physical_operational"):
        result = assessment(mode, ["simulator"])

        assert result["source_admitted"] is False
        assert result["reason_code"] == "EVIDENCE.OPERATING_MODE_SOURCE_REFUSED"


def test_demo_mode_refuses_physical_source() -> None:
    result = assessment("demo_emulation", ["physical"])

    assert result["source_admitted"] is False
    assert result["reason_code"] == "EVIDENCE.OPERATING_MODE_SOURCE_REFUSED"


def test_physical_modes_admit_physical_source_without_granting_action() -> None:
    for mode in ("physical_commissioning", "physical_operational"):
        result = assessment(mode, ["physical"])

        assert result["source_admitted"] is True
        assert result["authorized_action"] is False


def test_unknown_mode_fails_closed() -> None:
    result = assessment("automatic", ["physical"])

    assert result["source_admitted"] is False
    assert result["scope"] == "none"
    assert result["reason_code"] == "EVIDENCE.OPERATING_MODE_UNKNOWN"


def test_mixed_sources_fail_closed_in_every_declared_mode() -> None:
    for mode in PROFILE["modes"]:
        result = assessment(mode, ["simulator", "physical"])

        assert result["source_admitted"] is False
        assert result["reason_code"] == "EVIDENCE.OPERATING_MODE_MIXED_SOURCES_REFUSED"


def test_refused_mode_disables_existing_semantic_admission() -> None:
    payload = semantic_payload()
    refused = assessment("physical_operational", ["simulator"])

    result = enforce_operating_mode(copy.deepcopy(payload), refused)

    assert result["reason_code"] == "EVIDENCE.OPERATING_MODE_SOURCE_REFUSED"
    assert result["semantic_admission"]["admitted_count"] == 0
    assert result["semantic_admission"]["scope"] == "disabled"
    assert result["semantic_admission"]["signals"]["rpm"]["admitted"] is False
    assert (
        result["semantic_admission"]["signals"]["rpm"]["reason_code"]
        == "EVIDENCE.OPERATING_MODE_SOURCE_REFUSED"
    )


def test_profile_is_versioned_and_serializable() -> None:
    assert PROFILE["schema_version"] == "linealert.operating-mode-profile.v1"
    assert PROFILE["default_mode"] == "demo_emulation"
    json.dumps(PROFILE)
