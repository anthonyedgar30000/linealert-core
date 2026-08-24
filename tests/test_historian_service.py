from __future__ import annotations

import pytest

from linealert_core.historian_service import HistorianServiceStatus, measurement_from_payload


def _condition_payload() -> dict[str, object]:
    return {
        "signal": "label_presentation_delay_ms",
        "value": 550.0,
        "unit": "ms",
        "min_value": 50.0,
        "max_value": 350.0,
        "asset_id": "LABELER-DEMO-01",
        "rule_id": "label-presentation-delay",
        "correlation_id": "drift-cycle-2010",
        "source_timestamp": "2026-08-24T12:00:00+00:00",
        "start_timestamp": "2026-08-24T11:59:59.450000+00:00",
        "end_timestamp": "2026-08-24T12:00:00+00:00",
        "start_event_id": "command-2010",
        "end_event_id": "peel-2010",
        "start_source_id": "plc-labeler-demo",
        "end_source_id": "plc-labeler-demo",
        "topology_from": "LabelFeedCommand",
        "topology_to": "LabelAtPeelPoint",
        "temporal_rule_status": "late",
        "semantic": "label presentation delay",
        "scope": "label-application-station",
        "relationship_id": "relationship:label-presentation-delay",
        "observation_id": "LABELER-DEMO-01:drift-cycle-2010:label_presentation_delay_ms:2026",
        "quality": "good",
        "reason_code": "EVIDENCE.RELATIONSHIP_DELAY_MEASURED",
        "clock_evidence": {
            "start_clock_quality": "synchronized",
            "end_clock_quality": "synchronized",
            "basis": "same_source_relative_interval",
            "retained_uncertainty": "same source clock",
        },
    }


def test_measurement_from_payload_preserves_admitted_relationship_evidence() -> None:
    measurement = measurement_from_payload(_condition_payload())

    assert measurement.observation.value == 550.0
    assert measurement.observation.min_value == 50.0
    assert measurement.observation.max_value == 350.0
    assert measurement.observation.relationship_id == "relationship:label-presentation-delay"
    assert measurement.observation.temporal_rule_status == "late"
    assert measurement.clock_evidence.basis == "same_source_relative_interval"


def test_measurement_from_payload_rejects_incomplete_condition() -> None:
    payload = _condition_payload()
    del payload["relationship_id"]

    with pytest.raises(ValueError, match="relationship_id"):
        measurement_from_payload(payload)


def test_historian_service_status_returns_detached_payload() -> None:
    status = HistorianServiceStatus()
    status.update(connected=True, source_available=True, latest_condition_count=10)

    first = status.get()
    first["connected"] = False

    assert status.get()["connected"] is True
    assert status.get()["latest_condition_count"] == 10
