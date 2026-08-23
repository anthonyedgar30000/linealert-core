import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from linealert_core.semantic_admission import evaluate_semantic_admission

PROFILE = json.loads(
    (
        Path(__file__).parents[1] / "profiles" / "microsoft-opc-plc-proxy-v1.semantic-bindings.json"
    ).read_text(encoding="utf-8")
)


def snapshot(now: datetime) -> dict:
    return {
        "profile": "microsoft-opc-plc-proxy-v1",
        "source_id": "microsoft-opc-plc-local",
        "asset_id": "SIM-OPCPLC-01",
        "read_only": True,
        "connected": True,
        "signals": {
            "rpm": {
                "value": 120.0,
                "unit": "rpm",
                "node_id": "nsu=http://microsoft.com/Opc/OpcPlc/;s=FastDouble1",
                "quality": "good",
                "source_timestamp": (now - timedelta(milliseconds=100)).isoformat(),
            },
            "pressure_psi": {"quality": "good"},
            "arrival_ms": {"quality": "good"},
            "raw_timing_proxy": {"quality": "good"},
        },
    }


def test_only_declared_rpm_proxy_is_admitted() -> None:
    now = datetime(2026, 8, 23, 5, 0, tzinfo=UTC)
    result = evaluate_semantic_admission(snapshot(now), PROFILE, now=now)

    assert result["admitted_count"] == 1
    assert result["total_count"] == 4
    assert result["scope"] == "simulator_only"
    assert result["signals"]["rpm"]["admitted"] is True
    assert result["signals"]["rpm"]["semantic"] == "simulated_motor_speed_proxy"
    assert result["signals"]["pressure_psi"]["admitted"] is False
    assert result["signals"]["arrival_ms"]["admitted"] is False
    assert result["signals"]["raw_timing_proxy"]["admitted"] is False


def test_node_identity_mismatch_fails_closed() -> None:
    now = datetime(2026, 8, 23, 5, 0, tzinfo=UTC)
    candidate = snapshot(now)
    candidate["signals"]["rpm"]["node_id"] = "ns=2;s=OtherNode"

    result = evaluate_semantic_admission(candidate, PROFILE, now=now)

    assert result["admitted_count"] == 0
    assert result["signals"]["rpm"]["reason_code"] == "EVIDENCE.SEMANTIC_NODE_ID_MISMATCH"


def test_unit_mismatch_fails_closed() -> None:
    now = datetime(2026, 8, 23, 5, 0, tzinfo=UTC)
    candidate = snapshot(now)
    candidate["signals"]["rpm"]["unit"] = "hz"

    result = evaluate_semantic_admission(candidate, PROFILE, now=now)

    assert result["admitted_count"] == 0
    assert result["signals"]["rpm"]["reason_code"] == "EVIDENCE.SEMANTIC_UNIT_MISMATCH"


def test_stale_signal_fails_closed() -> None:
    now = datetime(2026, 8, 23, 5, 0, tzinfo=UTC)
    candidate = snapshot(now)
    candidate["signals"]["rpm"]["source_timestamp"] = (now - timedelta(seconds=2)).isoformat()

    result = evaluate_semantic_admission(candidate, PROFILE, now=now)

    assert result["admitted_count"] == 0
    assert result["signals"]["rpm"]["reason_code"] == "EVIDENCE.SEMANTIC_FRESHNESS_REFUSED"


def test_bad_quality_and_scope_mismatch_fail_closed() -> None:
    now = datetime(2026, 8, 23, 5, 0, tzinfo=UTC)
    bad_quality = snapshot(now)
    bad_quality["signals"]["rpm"]["quality"] = "bad"
    wrong_asset = copy.deepcopy(snapshot(now))
    wrong_asset["asset_id"] = "OTHER-ASSET"

    quality_result = evaluate_semantic_admission(bad_quality, PROFILE, now=now)
    scope_result = evaluate_semantic_admission(wrong_asset, PROFILE, now=now)

    assert quality_result["admitted_count"] == 0
    assert quality_result["signals"]["rpm"]["reason_code"] == "EVIDENCE.SEMANTIC_QUALITY_REFUSED"
    assert scope_result["admitted_count"] == 0
    assert (
        scope_result["signals"]["rpm"]["reason_code"] == "EVIDENCE.SEMANTIC_SNAPSHOT_SCOPE_MISMATCH"
    )
