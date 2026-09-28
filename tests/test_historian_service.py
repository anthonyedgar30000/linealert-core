from __future__ import annotations

import pytest

from linealert_core.historian_service import (
    HistorianServiceStatus,
    functional_temporal_selection_spec_from_query,
    history_time_from_query,
    measurement_from_payload,
)


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


def test_history_time_from_query_requires_timezone_aware_iso8601() -> None:
    parsed = history_time_from_query("2026-09-14T15:42:00Z", "from_time")

    assert parsed is not None
    assert parsed.isoformat() == "2026-09-14T15:42:00+00:00"
    assert history_time_from_query(None, "to_time") is None

    with pytest.raises(ValueError, match="timezone-aware"):
        history_time_from_query("2026-09-14T15:42:00", "from_time")
    with pytest.raises(ValueError, match="ISO 8601"):
        history_time_from_query("not-a-time", "from_time")


def test_functional_temporal_selection_spec_from_query_preserves_explicit_scope() -> None:
    query = {
        "reference_label": ["Approved reference cycle"],
        "reference_cycle_id": ["commissioned-cycle-42"],
        "reference_phase_id": ["LABEL_PRESENTED"],
        "reference_record_kind": ["GUARD"],
        "reference_from_time": ["2026-03-12T14:29:00Z"],
        "reference_to_time": ["2026-03-12T14:31:00Z"],
        "reference_limit": ["250"],
    }

    spec = functional_temporal_selection_spec_from_query(
        query,
        prefix="reference",
        asset_id="LABELER-DEMO-01",
        default_limit=1000,
    )

    assert spec.label == "Approved reference cycle"
    assert spec.asset_id == "LABELER-DEMO-01"
    assert spec.cycle_id == "commissioned-cycle-42"
    assert spec.phase_id == "LABEL_PRESENTED"
    assert spec.record_kind is not None
    assert spec.record_kind.value == "GUARD"
    assert spec.limit == 250
    assert spec.from_time is not None
    assert spec.from_time.isoformat() == "2026-03-12T14:29:00+00:00"
    assert spec.to_time is not None
    assert spec.to_time.isoformat() == "2026-03-12T14:31:00+00:00"


def test_functional_temporal_selection_spec_from_query_rejects_missing_label() -> None:
    with pytest.raises(ValueError, match="reference_label is required"):
        functional_temporal_selection_spec_from_query(
            {"reference_cycle_id": ["cycle-42"]},
            prefix="reference",
            asset_id="LABELER-DEMO-01",
            default_limit=1000,
        )


def test_functional_temporal_selection_spec_from_query_rejects_invalid_kind_and_limit() -> None:
    with pytest.raises(ValueError, match="reference_record_kind is invalid"):
        functional_temporal_selection_spec_from_query(
            {
                "reference_label": ["Reference"],
                "reference_cycle_id": ["cycle-42"],
                "reference_record_kind": ["UNKNOWN_KIND"],
            },
            prefix="reference",
            asset_id="LABELER-DEMO-01",
            default_limit=1000,
        )

    with pytest.raises(ValueError, match="reference_limit must be an integer"):
        functional_temporal_selection_spec_from_query(
            {
                "reference_label": ["Reference"],
                "reference_cycle_id": ["cycle-42"],
                "reference_limit": ["many"],
            },
            prefix="reference",
            asset_id="LABELER-DEMO-01",
            default_limit=1000,
        )
