from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from linealert_core.labeler_demo_bridge import (
    ALLOWED_DEMO_CONTROLS,
    LABELER_NODE_MAPPINGS,
    PROFILE_ID,
    SOURCE_ID,
    LabelerSnapshot,
    _control_target_url,
    _qualified_signal,
)


class GoodStatus:
    def is_good(self):
        return True

    def is_bad(self):
        return False

    def __str__(self):
        return "Good"


def data_value(value):
    return SimpleNamespace(
        StatusCode=GoodStatus(),
        SourceTimestamp=datetime(2026, 9, 10, 12, 0, tzinfo=UTC),
        Value=SimpleNamespace(Value=value),
    )


def test_labeler_bridge_uses_explicit_read_only_allowlist():
    node_ids = [mapping.node_id for mapping in LABELER_NODE_MAPPINGS]

    assert len(node_ids) == len(set(node_ids))
    assert all(node_id.startswith("nsu=urn:linealert:emulator:labeler2;s=") for node_id in node_ids)
    assert {mapping.signal for mapping in LABELER_NODE_MAPPINGS} >= {
        "run_state_code",
        "line_speed_cpm",
        "presentation_interval_stddev_ms",
        "camera_observed_containers",
        "camera_aligned_containers",
        "accepted_containers",
        "roll_change_recent",
    }
    assert all("GuideOffset" not in node_id for node_id in node_ids)


def test_labeler_bridge_qualifies_declared_types_and_preserves_timestamp():
    by_signal = {mapping.signal: mapping for mapping in LABELER_NODE_MAPPINGS}

    speed = _qualified_signal(
        by_signal["line_speed_cpm"],
        data_value(78.2),
        received_timestamp=datetime(2026, 9, 10, 12, 0, 1, tzinfo=UTC),
        observation_id="obs-speed",
    )
    roll = _qualified_signal(
        by_signal["roll_change_recent"],
        data_value(True),
        received_timestamp=datetime(2026, 9, 10, 12, 0, 1, tzinfo=UTC),
        observation_id="obs-roll",
    )

    assert speed["quality"] == "good"
    assert speed["value"] == 78.2
    assert speed["source_timestamp"] == "2026-09-10T12:00:00+00:00"
    assert roll["quality"] == "good"
    assert roll["value"] is True


def test_labeler_snapshot_fails_closed_and_keeps_source_identity_when_unavailable():
    snapshot = LabelerSnapshot()
    snapshot.replace(
        {
            "schema_version": "linealert.observation.snapshot.v1",
            "connected": True,
            "profile": PROFILE_ID,
            "source_id": SOURCE_ID,
            "source_kind": "simulator",
            "source_scope": "simulator_only",
            "asset_id": "Labeler 2",
            "read_only": True,
            "signals": {
                "line_speed_cpm": {
                    "value": 78.0,
                    "quality": "good",
                    "source_timestamp": "2026-09-10T12:00:00+00:00",
                }
            },
        }
    )

    stale = snapshot.mark_unavailable(
        reason_code="EVIDENCE.OPCUA_CONNECTION_UNAVAILABLE",
        error="ConnectionError",
    )

    assert stale["connected"] is False
    assert stale["profile"] == PROFILE_ID
    assert stale["source_id"] == SOURCE_ID
    assert stale["source_kind"] == "simulator"
    assert stale["source_scope"] == "simulator_only"
    assert stale["asset_id"] == "Labeler 2"
    assert stale["read_only"] is True
    assert stale["signals"]["line_speed_cpm"]["value"] == 78.0
    assert stale["signals"]["line_speed_cpm"]["quality"] == "stale"
    assert stale["signals"]["line_speed_cpm"]["reason_code"] == "EVIDENCE.TELEMETRY_STALE"


def test_labeler_bridge_rejects_wrong_declared_value_type():
    bool_mapping = next(m for m in LABELER_NODE_MAPPINGS if m.signal == "roll_change_recent")
    result = _qualified_signal(
        bool_mapping,
        data_value(1),
        received_timestamp=datetime(2026, 9, 10, 12, 0, 1, tzinfo=UTC),
        observation_id="obs-bad",
    )

    assert result["quality"] == "bad"
    assert result["value"] is None
    assert result["reason_code"] == "EVIDENCE.OPCUA_VALUE_TYPE_MISMATCH"


def test_demo_control_proxy_is_explicit_and_loopback_only():
    assert set(ALLOWED_DEMO_CONTROLS) == {
        "stop_for_diagnostic",
        "inspect_guide",
        "restore_guide",
        "run_diagnostic_batch",
        "resume_production",
    }
    assert _control_target_url("http://127.0.0.1:4842", "inspect_guide") == (
        "http://127.0.0.1:4842/control/inspect-guide"
    )
    with pytest.raises(ValueError, match="unknown simulator control action"):
        _control_target_url("http://127.0.0.1:4842", "set_anything")
    with pytest.raises(ValueError, match="loopback HTTP"):
        _control_target_url("https://example.com", "inspect_guide")
